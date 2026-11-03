using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Microsoft.Data.Sqlite;

namespace ExecutionLab.Persistence;

public sealed class IdempotencyConflictException() : Exception("Key reused with different content.");
public sealed record CommitResult(Decision Decision, bool Replayed);
public sealed record AuditMessage(string Id, string Payload);

/// <summary>
/// One synthetic gate per SQLite file. Transactions serialize local state changes;
/// the outbox carries audit facts, NEVER exchange order instructions.
/// </summary>
public sealed class DurableGate
{
    private readonly string connectionString;
    private readonly long limit;
    public DurableGate(string databasePath, long exposureLimit)
    {
        ArgumentOutOfRangeException.ThrowIfNegative(exposureLimit);
        limit = exposureLimit;
        connectionString = new SqliteConnectionStringBuilder
        {
            DataSource = Path.GetFullPath(databasePath), Pooling = false, DefaultTimeout = 10
        }.ToString();
        using var db = Open();
        Execute(db, null, """
            CREATE TABLE IF NOT EXISTS gate(id INTEGER PRIMARY KEY CHECK(id=1), exposure_limit INTEGER NOT NULL, state TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS receipts(id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, decision TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS outbox(id TEXT PRIMARY KEY, payload TEXT NOT NULL, delivered INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS inbox(id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS projection(id INTEGER PRIMARY KEY CHECK(id=1), applied INTEGER NOT NULL);
            """);
        using var tx = db.BeginTransaction(deferred: false);
        Execute(db, tx, "INSERT OR IGNORE INTO gate VALUES(1,$limit,$state)",
            ("$limit", limit), ("$state", JsonSerializer.Serialize(GateState.Empty)));
        using var read = Command(db, tx, "SELECT exposure_limit FROM gate WHERE id=1");
        if (Convert.ToInt64(read.ExecuteScalar()) != limit)
            throw new InvalidOperationException("Persisted exposure limit differs; no implicit configuration migration.");
        Execute(db, tx, "INSERT OR IGNORE INTO projection VALUES(1,0)");
        tx.Commit();
    }

    public CommitResult Apply(string key, GateEvent input) => ApplyForTest(key, input, null);

    // Failure injection is internal and runs before commit. Never exposed by HTTP.
    internal CommitResult ApplyForTest(string key, GateEvent input, Action? beforeCommit)
    {
        ArgumentNullException.ThrowIfNull(input);
        if (string.IsNullOrWhiteSpace(key) || key.Length > 128)
            throw new ArgumentException("Use a non-empty idempotency key of at most 128 characters.", nameof(key));
        if (input is not (Snapshot or Resume or Reserve or Fill or RequestCancel or ConfirmCancel or RejectOrder or Disconnect or Stop))
            throw new ArgumentException("Unsupported event type.", nameof(input));
        var normalized = input with { EventId = key, Sequence = 0 };
        var fingerprint = Hash(input.GetType().Name + ":" + JsonSerializer.Serialize(normalized, normalized.GetType()));
        using var db = Open();
        using var tx = db.BeginTransaction(deferred: false);
        using (var previous = Command(db, tx, "SELECT fingerprint,decision FROM receipts WHERE id=$id", ("$id", key)))
        using (var reader = previous.ExecuteReader())
        {
            if (reader.Read())
            {
                if (reader.GetString(0) != fingerprint) throw new IdempotencyConflictException();
                return new(JsonSerializer.Deserialize<Decision>(reader.GetString(1))!, true);
            }
        }
        var state = Read(db, tx);
        var decision = OrderGate.Apply(state, normalized with { Sequence = checked(state.Sequence + 1) }, limit);
        // False is not rollback: a denied command can consume its event/cursor.
        Execute(db, tx, "UPDATE gate SET state=$state WHERE id=1", ("$state", JsonSerializer.Serialize(decision.State)));
        var payload = JsonSerializer.Serialize(decision);
        Execute(db, tx, "INSERT INTO receipts VALUES($id,$hash,$decision)",
            ("$id", key), ("$hash", fingerprint), ("$decision", payload));
        Execute(db, tx, "INSERT INTO outbox(id,payload) VALUES($id,$payload)", ("$id", key), ("$payload", payload));
        beforeCommit?.Invoke();
        tx.Commit();
        return new(decision, false);
    }

    public GateState ReadState()
    {
        using var db = Open();
        return Read(db, null);
    }

    public IReadOnlyList<AuditMessage> PendingAudit()
    {
        using var db = Open();
        using var command = Command(db, null, "SELECT id,payload FROM outbox WHERE delivered=0 ORDER BY rowid");
        using var reader = command.ExecuteReader();
        var rows = new List<AuditMessage>();
        while (reader.Read()) rows.Add(new(reader.GetString(0), reader.GetString(1)));
        return rows;
    }

    /// <summary>False means duplicate delivery. Inbox + illustrative counter commit together.</summary>
    public bool ConsumeAudit(AuditMessage message)
    {
        if (string.IsNullOrWhiteSpace(message.Id)) throw new ArgumentException("Missing audit ID.");
        var fingerprint = Hash(message.Payload);
        using var db = Open();
        using var tx = db.BeginTransaction(deferred: false);
        using (var previous = Command(db, tx, "SELECT fingerprint FROM inbox WHERE id=$id", ("$id", message.Id)))
        {
            if (previous.ExecuteScalar() is string prior)
            {
                if (prior != fingerprint) throw new IdempotencyConflictException();
                return false;
            }
        }
        Execute(db, tx, "INSERT INTO inbox VALUES($id,$hash)", ("$id", message.Id), ("$hash", fingerprint));
        Execute(db, tx, "UPDATE projection SET applied=applied+1 WHERE id=1");
        tx.Commit();
        return true;
    }

    // A dispatcher calls this ONLY after the consumer commit. A failure between
    // the two commits causes redelivery; it does not provide exactly-once transport.
    public void MarkAuditDelivered(string id)
    {
        using var db = Open();
        Execute(db, null, "UPDATE outbox SET delivered=1 WHERE id=$id", ("$id", id));
    }
    public long AppliedAuditCount()
    {
        using var db = Open();
        using var command = Command(db, null, "SELECT applied FROM projection WHERE id=1");
        return Convert.ToInt64(command.ExecuteScalar());
    }
    private SqliteConnection Open()
    {
        var db = new SqliteConnection(connectionString);
        db.Open();
        return db;
    }
    private static GateState Read(SqliteConnection db, SqliteTransaction? tx)
    {
        using var command = Command(db, tx, "SELECT state FROM gate WHERE id=1");
        return JsonSerializer.Deserialize<GateState>((string)command.ExecuteScalar()!)!;
    }
    private static string Hash(string value) => Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(value)));
    private static SqliteCommand Command(SqliteConnection db, SqliteTransaction? tx, string sql,
        params (string Name, object Value)[] parameters)
    {
        var command = db.CreateCommand(); command.Transaction = tx; command.CommandText = sql;
        foreach (var (name, value) in parameters) command.Parameters.AddWithValue(name, value);
        return command;
    }
    private static void Execute(SqliteConnection db, SqliteTransaction? tx, string sql,
        params (string Name, object Value)[] parameters)
    {
        using var command = Command(db, tx, sql, parameters);
        command.ExecuteNonQuery();
    }
}
