using System.IdentityModel.Tokens.Jwt;
using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Security.Claims;
using System.Text;
using System.Text.Json;
using ExecutionLab;
using ExecutionLab.Api;
using ExecutionLab.Persistence;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.TestHost;
using Microsoft.Data.Sqlite;
using Microsoft.IdentityModel.Tokens;
using Xunit;

// Source-authored compatibility fixtures, not claimed captures from a historical binary.
public sealed class TechRefreshCompatibilityTests : IDisposable
{
    private readonly string path = Path.Combine(Path.GetTempPath(), $"execution-refresh-{Guid.NewGuid():N}.sqlite");
    private const string Input = """{"OrderId":"legacy-order","Quantity":2,"EventId":"legacy-key","Sequence":0}""";
    private const string Fingerprint = "4E2C87EF9076CD870435E6C1681746E2ACF3D216A3FC7DBFD20A4A7FEBF3FFEA";
    private const string State = """{"Position":0,"Orders":{"legacy-order":{"Remaining":2,"CancelRequested":false}},"SeenEvents":["snapshot","resume","legacy-key"],"SeenExecutions":[],"UsedOrderIds":["legacy-order"],"Sequence":3,"Reconciled":true,"Stopped":false,"Pending":2,"ReservedExposure":2}""";
    private const string Receipt = """{"Accepted":true,"Reason":"Applied","State":{"Position":0,"Orders":{"legacy-order":{"Remaining":2,"CancelRequested":false}},"SeenEvents":["snapshot","resume","legacy-key"],"SeenExecutions":[],"UsedOrderIds":["legacy-order"],"Sequence":3,"Reconciled":true,"Stopped":false,"Pending":2,"ReservedExposure":2}}""";
    private const string WireReplay = """{"accepted":true,"reason":"Applied","sequence":3,"exposure":2,"replayed":true}""";
    private const string Schema = """
        CREATE TABLE gate(id INTEGER PRIMARY KEY CHECK(id=1), exposure_limit INTEGER NOT NULL, state TEXT NOT NULL);
        CREATE TABLE receipts(id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, decision TEXT NOT NULL);
        CREATE TABLE outbox(id TEXT PRIMARY KEY, payload TEXT NOT NULL, delivered INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE inbox(id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL);
        CREATE TABLE projection(id INTEGER PRIMARY KEY CHECK(id=1), applied INTEGER NOT NULL);
        """;

    [Fact]
    public void LiteralLegacyReceiptAndFingerprintRemainCompatible()
    {
        var normalized = new Reserve("legacy-key", 0, "legacy-order", 2);
        Assert.Equal(Input, JsonSerializer.Serialize(normalized));
        Assert.Equal(Fingerprint, Convert.ToHexString(
            System.Security.Cryptography.SHA256.HashData(Encoding.UTF8.GetBytes("Reserve:" + Input))));
        SeedLiteralDatabase();
        var before = ReadRows();
        var store = new DurableGate(path, 10);
        var replay = store.Apply("legacy-key", normalized with { EventId = "ignored", Sequence = 999 });
        Assert.True(replay.Replayed);
        Assert.True(replay.Decision.Accepted);
        Assert.Equal(3, replay.Decision.State.Sequence);
        Assert.Equal(2, replay.Decision.State.ReservedExposure);
        Assert.Equal(before, ReadRows());
        foreach (var changed in new[] { normalized with { Quantity = 1 }, normalized with { OrderId = "other" } })
        {
            Assert.Throws<IdempotencyConflictException>(() => store.Apply("legacy-key", changed));
            Assert.Equal(before, ReadRows());
        }
        Assert.Equal(Receipt, Assert.Single(store.PendingAudit()).Payload);
        Assert.Equal(before, ReadRows());
    }

    [Fact]
    public async Task WireAndSchemaStayStableAcrossRestart()
    {
        SeedLiteralDatabase();
        var schema = ReadSchema();
        Assert.Equal(new[]
        {
            "gate:id:INTEGER:0:1", "gate:exposure_limit:INTEGER:1:0", "gate:state:TEXT:1:0",
            "inbox:id:TEXT:0:1", "inbox:fingerprint:TEXT:1:0",
            "outbox:id:TEXT:0:1", "outbox:payload:TEXT:1:0", "outbox:delivered:INTEGER:1:0",
            "projection:id:INTEGER:0:1", "projection:applied:INTEGER:1:0",
            "receipts:id:TEXT:0:1", "receipts:fingerprint:TEXT:1:0", "receipts:decision:TEXT:1:0"
        }, schema);
        var key = Enumerable.Range(1, 32).Select(x => (byte)x).ToArray(); // Test-only synthetic key.
        var now = DateTime.UtcNow;
        var token = new JwtSecurityTokenHandler().WriteToken(new JwtSecurityToken(GateApi.Issuer, GateApi.Audience,
            [new Claim("sub", "literal-compatibility"), new Claim("role", "operator")],
            now.AddSeconds(-1), now.AddMinutes(2),
            new SigningCredentials(new SymmetricSecurityKey(key), SecurityAlgorithms.HmacSha256)));
        async Task<WebApplication> Open()
        {
            var builder = WebApplication.CreateBuilder();
            builder.WebHost.UseTestServer();
            GateApi.Configure(builder, key);
            var app = builder.Build();
            GateApi.Map(app, new DurableGate(path, 10));
            try { await app.StartAsync(TestContext.Current.CancellationToken); return app; }
            catch { await app.DisposeAsync(); throw; }
        }
        async Task<HttpResponseMessage> Send(HttpClient client, string id, string order, long quantity)
        {
            using var request = new HttpRequestMessage(HttpMethod.Post, "/reservations");
            request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
            request.Headers.Add("Idempotency-Key", id);
            request.Content = JsonContent.Create(new ReserveRequest(order, quantity));
            return await client.SendAsync(request, TestContext.Current.CancellationToken);
        }
        await using (var app = await Open())
        {
            using var client = app.GetTestClient();
            var before = ReadRows();
            using var replay = await Send(client, "legacy-key", "legacy-order", 2);
            Assert.Equal(HttpStatusCode.OK, replay.StatusCode);
            Assert.Equal(WireReplay, await replay.Content.ReadAsStringAsync());
            Assert.Equal(before, ReadRows());
            using var next = await Send(client, "new-key", "new-order", 1);
            Assert.Equal(HttpStatusCode.OK, next.StatusCode);
            Assert.Equal("""{"accepted":true,"reason":"Applied","sequence":4,"exposure":3,"replayed":false}""",
                await next.Content.ReadAsStringAsync());
        }
        await using (var reopened = await Open())
        {
            using var client = reopened.GetTestClient();
            var before = ReadRows();
            using var replay = await Send(client, "legacy-key", "legacy-order", 2);
            Assert.Equal(HttpStatusCode.OK, replay.StatusCode);
            Assert.Equal(WireReplay, await replay.Content.ReadAsStringAsync());
            Assert.Equal(before, ReadRows());
            foreach (var intent in new[] { ("legacy-order", 1L), ("other", 2L) })
            {
                using var conflict = await Send(client, "legacy-key", intent.Item1, intent.Item2);
                Assert.Equal(HttpStatusCode.Conflict, conflict.StatusCode);
                Assert.Equal("""{"error":"Key already used for different content."}""",
                    await conflict.Content.ReadAsStringAsync());
                Assert.Equal(before, ReadRows());
            }
            var current = new DurableGate(path, 10).ReadState();
            Assert.Equal(4, current.Sequence);
            Assert.Equal(3, current.ReservedExposure);
            Assert.Equal(2, new DurableGate(path, 10).PendingAudit().Count);
            Assert.Equal(schema, ReadSchema());
        }
    }

    private SqliteConnection Connect(bool readOnly = false)
    {
        var db = new SqliteConnection(new SqliteConnectionStringBuilder
        {
            DataSource = path, Pooling = false, DefaultTimeout = 10, Mode = readOnly ? SqliteOpenMode.ReadOnly : SqliteOpenMode.ReadWriteCreate
        }.ToString());
        db.Open();
        return db;
    }

    private void SeedLiteralDatabase()
    {
        using var db = Connect();
        using var command = db.CreateCommand();
        command.CommandText = Schema + """
            INSERT INTO gate VALUES(1,10,$state);
            INSERT INTO receipts VALUES('legacy-key',$fingerprint,$receipt);
            INSERT INTO outbox VALUES('legacy-key',$receipt,0);
            INSERT INTO projection VALUES(1,0);
            """;
        command.Parameters.AddWithValue("$state", State);
        command.Parameters.AddWithValue("$fingerprint", Fingerprint);
        command.Parameters.AddWithValue("$receipt", Receipt);
        command.ExecuteNonQuery();
    }

    private string[] ReadRows()
    {
        using var db = Connect(true);
        var rows = new List<string>();
        foreach (var table in new[] { "gate", "inbox", "outbox", "projection", "receipts" })
        {
            using var command = db.CreateCommand();
            command.CommandText = $"SELECT * FROM {table} ORDER BY id";
            using var reader = command.ExecuteReader();
            while (reader.Read())
                rows.Add(table + ":" + string.Join("|", Enumerable.Range(0, reader.FieldCount).Select(i => reader.GetValue(i).ToString())));
        }
        return rows.ToArray();
    }

    private string[] ReadSchema()
    {
        using var db = Connect(true);
        using var list = db.CreateCommand();
        list.CommandText = "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name";
        using var reader = list.ExecuteReader();
        var names = new List<string>();
        while (reader.Read()) names.Add(reader.GetString(0));
        reader.Close();
        Assert.Equal(new[] { "gate", "inbox", "outbox", "projection", "receipts" }, names);
        var columns = new List<string>();
        foreach (var table in names)
        {
            using var command = db.CreateCommand();
            command.CommandText = $"PRAGMA table_info({table})";
            using var info = command.ExecuteReader();
            while (info.Read())
                columns.Add($"{table}:{info.GetString(1)}:{info.GetString(2)}:{info.GetInt64(3)}:{info.GetInt64(5)}");
        }
        return columns.ToArray();
    }

    public void Dispose()
    {
        foreach (var suffix in new[] { "", "-wal", "-shm", "-journal" }) File.Delete(path + suffix);
    }
}
