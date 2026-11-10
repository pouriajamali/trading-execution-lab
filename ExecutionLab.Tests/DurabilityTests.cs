using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Security.Claims;
using System.Security.Cryptography;
using System.IdentityModel.Tokens.Jwt;
using System.Text.Json;
using ExecutionLab;
using ExecutionLab.Api;
using ExecutionLab.Persistence;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.TestHost;
using Microsoft.Data.Sqlite;
using Microsoft.IdentityModel.Tokens;
using Xunit;

public sealed class DurabilityTests : IDisposable
{
    private readonly string path = Path.Combine(Path.GetTempPath(), $"execution-lab-{Guid.NewGuid():N}.sqlite");
    private DurableGate Store() => new(path, 10);
    private DurableGate Ready()
    {
        var store = Store();
        Assert.True(store.Apply("snapshot", new Snapshot("ignored", 111, 0, [])).Decision.Accepted);
        Assert.True(store.Apply("resume", new Resume("ignored", 999)).Decision.Accepted);
        return store;
    }

    [Fact]
    public void ReopenAndRetryPreservesOriginalReceiptWithoutNewEffects()
    {
        var store = Ready();
        var command = new Reserve("ignored", 222, "a", 4);
        var original = store.Apply("reserve-a", command);
        var reopened = Store();
        var replay = reopened.Apply("reserve-a", command with { Sequence = 777 });
        Assert.True(replay.Replayed);
        Assert.Equal(original.Decision.State.Sequence, replay.Decision.State.Sequence);
        Assert.Equal(4, reopened.ReadState().ReservedExposure);
        Assert.Equal(3, reopened.PendingAudit().Count);
        Assert.Throws<IdempotencyConflictException>(() => reopened.Apply("reserve-a", command with { Quantity = 5 }));
    }

    [Fact]
    public void HistoricalRetryDoesNotRollbackLaterCommittedState()
    {
        var store = Ready();
        var original = store.Apply("first", new Reserve("", 0, "a", 3));
        Assert.True(store.Apply("later", new Reserve("", 0, "b", 2)).Decision.Accepted);
        var replay = Store().Apply("first", new Reserve("", 0, "a", 3));
        Assert.True(replay.Replayed);
        Assert.Equal(original.Decision.State.Sequence, replay.Decision.State.Sequence);
        Assert.Equal(3, replay.Decision.State.ReservedExposure);
        Assert.Equal(4, Store().ReadState().Sequence);
        Assert.Equal(5, Store().ReadState().ReservedExposure);
        Assert.Equal(4, store.PendingAudit().Count);
    }

    [Fact]
    public void DeniedCommandStillCommitsStateReceiptAndAudit()
    {
        var store = Ready();
        Assert.False(store.Apply("too-large", new Reserve("", 0, "a", 11)).Decision.Accepted);
        Assert.Equal(3, Store().ReadState().Sequence);
        Assert.Equal(3, store.PendingAudit().Count);
        var next = Store().Apply("fits", new Reserve("", 0, "b", 10));
        Assert.True(next.Decision.Accepted);
        Assert.Equal(4, next.Decision.State.Sequence);
    }

    [Fact]
    public void FailureBeforeCommitRollsBackAllThreeWritesAndAllowsRetry()
    {
        var store = Ready();
        var command = new Reserve("", 0, "a", 4);
        var before = ReadDatabase("reserve");
        AssertDatabaseState(before, 2, 0, 0, 0, 2, []);
        AssertMissingReceipt(before);
        Assert.Throws<IOException>(() => store.ApplyForTest("reserve", command, () => throw new IOException("injected")));
        Assert.Equal(before, ReadDatabase("reserve"));
        Assert.Equal(2, Store().ReadState().Sequence);
        Assert.Equal(0, store.ReadState().ReservedExposure);
        Assert.Equal(2, store.PendingAudit().Count);
        var retry = Store().Apply("reserve", command);
        Assert.False(retry.Replayed);
        Assert.True(retry.Decision.Accepted);
        Assert.Equal(3, store.PendingAudit().Count);
        var committed = ReadDatabase("reserve");
        AssertDatabaseState(committed, 3, 0, 4, 4, 3, [("a", 4)]);
        AssertStoredReceipt(committed, 3, 0, 4, 4, [("a", 4)]);
    }

    [Fact]
    public async Task IndependentConnectionsSerializeCompetingReservations()
    {
        Ready();
        var tasks = Enumerable.Range(0, 20).Select(i => Task.Run(() =>
            Store().Apply($"request-{i}", new Reserve("", 0, $"order-{i}", 1)), TestContext.Current.CancellationToken));
        var results = await Task.WhenAll(tasks).WaitAsync(TimeSpan.FromSeconds(30), TestContext.Current.CancellationToken);
        Assert.Equal(10, results.Count(r => r.Decision.Accepted));
        Assert.Equal(22, Store().ReadState().Sequence);
        Assert.Equal(10, Store().ReadState().ReservedExposure);
        Assert.Equal(22, Store().PendingAudit().Count);
    }

    [Fact]
    public async Task ConcurrentSameKeyHasOneCommittedEffect()
    {
        Ready();
        var results = await Task.WhenAll(Enumerable.Range(0, 12).Select(_ => Task.Run(() =>
            Store().Apply("same", new Reserve("", 0, "a", 1)), TestContext.Current.CancellationToken)));
        Assert.Single(results, r => !r.Replayed);
        Assert.Equal(1, Store().ReadState().ReservedExposure);
        Assert.Equal(3, Store().PendingAudit().Count);
    }

    [Fact]
    public void RedeliveryAfterConsumerCommitDoesNotRepeatProjectionEffect()
    {
        var store = Ready();
        var message = store.PendingAudit()[0];
        Assert.True(store.ConsumeAudit(message));
        // Simulate failure after consumer commit, before outbox acknowledgement.
        var restarted = Store();
        Assert.Contains(restarted.PendingAudit(), m => m.Id == message.Id);
        Assert.False(restarted.ConsumeAudit(message));
        Assert.Equal(1, restarted.AppliedAuditCount());
        Assert.Throws<IdempotencyConflictException>(() => restarted.ConsumeAudit(message with { Payload = "different" }));
        restarted.MarkAuditDelivered(message.Id);
        Assert.DoesNotContain(Store().PendingAudit(), m => m.Id == message.Id);
        Assert.Equal(1, Store().AppliedAuditCount());
    }

    [Fact]
    public void PersistedLimitCannotBeSilentlyChanged()
    {
        Ready();
        Assert.Throws<InvalidOperationException>(() => new DurableGate(path, 11));
        Assert.Equal(2, Store().ReadState().Sequence);
    }

    [Fact]
    public async Task HttpPipelineValidatesTokenRoleInputIdempotencyAndRiskDenial()
    {
        var store = Ready();
        byte[] key = RandomNumberGenerator.GetBytes(64);
        var builder = WebApplication.CreateBuilder();
        builder.WebHost.UseTestServer();
        GateApi.Configure(builder, key);
        await using var app = builder.Build();
        GateApi.Map(app, store);
        await app.StartAsync(TestContext.Current.CancellationToken);
        using var client = app.GetTestClient();
        async Task<HttpResponseMessage> Send(string? token, string id = "http", long quantity = 2)
        {
            using var request = new HttpRequestMessage(HttpMethod.Post, "/reservations");
            if (token is not null) request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
            request.Headers.Add("Idempotency-Key", id);
            request.Content = JsonContent.Create(new ReserveRequest("http-order", quantity));
            return await client.SendAsync(request, TestContext.Current.CancellationToken);
        }
        string Token(string role, byte[] signingKey, string? audience = null, DateTime? expires = null,
            string? issuer = null, bool includeSubject = true, string algorithm = SecurityAlgorithms.HmacSha256)
        {
            var end = expires ?? DateTime.UtcNow.AddMinutes(2);
            var claims = new List<Claim> { new("role", role) };
            if (includeSubject) claims.Add(new("sub", "synthetic-operator"));
            var token = new JwtSecurityToken(issuer ?? GateApi.Issuer, audience ?? GateApi.Audience,
                claims, end.AddMinutes(-5), end, new SigningCredentials(new SymmetricSecurityKey(signingKey), algorithm));
            return new JwtSecurityTokenHandler().WriteToken(token);
        }
        Assert.Equal(HttpStatusCode.Unauthorized, (await Send(null)).StatusCode);
        Assert.Equal(HttpStatusCode.Unauthorized, (await Send(Token("operator", RandomNumberGenerator.GetBytes(32)))).StatusCode);
        Assert.Equal(HttpStatusCode.Unauthorized, (await Send(Token("operator", key, "wrong-audience"))).StatusCode);
        Assert.Equal(HttpStatusCode.Unauthorized, (await Send(Token("operator", key, issuer: "wrong-issuer"))).StatusCode);
        Assert.Equal(HttpStatusCode.Unauthorized, (await Send(Token("operator", key, algorithm: SecurityAlgorithms.HmacSha384))).StatusCode);
        Assert.Equal(HttpStatusCode.Unauthorized, (await Send(Token("operator", key, expires: DateTime.UtcNow.AddMinutes(-1)))).StatusCode);
        Assert.Equal(HttpStatusCode.Forbidden, (await Send(Token("reader", key))).StatusCode);
        Assert.Equal(HttpStatusCode.Forbidden, (await Send(Token("operator", key, includeSubject: false))).StatusCode);
        Assert.Equal(2, store.ReadState().Sequence);
        var valid = Token("operator", key);
        Assert.Equal(HttpStatusCode.BadRequest, (await Send(valid, quantity: 0)).StatusCode);
        Assert.Equal(HttpStatusCode.BadRequest, (await Send(valid, id: "bad:key")).StatusCode);
        var accepted = await Send(valid);
        Assert.Equal(HttpStatusCode.OK, accepted.StatusCode);
        Assert.True((await accepted.Content.ReadFromJsonAsync<DecisionResponse>(TestContext.Current.CancellationToken))!.Accepted);
        var replay = await Send(valid);
        Assert.True((await replay.Content.ReadFromJsonAsync<DecisionResponse>(TestContext.Current.CancellationToken))!.Replayed);
        Assert.Equal(HttpStatusCode.Conflict, (await Send(valid, quantity: 3)).StatusCode);
        var denied = await Send(valid, id: "over-limit", quantity: 11);
        Assert.False((await denied.Content.ReadFromJsonAsync<DecisionResponse>(TestContext.Current.CancellationToken))!.Accepted);
        Assert.Equal(4, Store().ReadState().Sequence);
        Assert.Equal(2, Store().ReadState().ReservedExposure);
    }

    [Fact]
    public async Task LocalPanelRequiresLoginAndReadsTheSameSyntheticGate()
    {
        var cancellation = TestContext.Current.CancellationToken;
        var store = Ready();
        var signingKey = RandomNumberGenerator.GetBytes(32);
        var code = Convert.ToHexString(RandomNumberGenerator.GetBytes(16));
        var builder = WebApplication.CreateBuilder();
        builder.WebHost.UseTestServer();
        GateApi.Configure(builder, signingKey);
        PanelApi.Configure(builder);
        await using var app = builder.Build();
        PanelApi.Map(app, store, 10, signingKey, code);
        GateApi.Map(app, store);
        await app.StartAsync(cancellation);
        using var client = app.GetTestClient();
        Assert.Equal(HttpStatusCode.Unauthorized, (await client.GetAsync("/panel/api/state", cancellation)).StatusCode);
        using var wrong = await client.PostAsJsonAsync("/panel/api/session", new OperatorLogin("wrong-operator-code"), cancellation);
        Assert.Equal(HttpStatusCode.Unauthorized, wrong.StatusCode);
        using var login = await client.PostAsJsonAsync("/panel/api/session", new OperatorLogin(code), cancellation);
        Assert.Equal(HttpStatusCode.OK, login.StatusCode);
        Assert.True(login.Headers.CacheControl?.NoStore);
        using var loginJson = System.Text.Json.JsonDocument.Parse(await login.Content.ReadAsStringAsync(cancellation));
        client.DefaultRequestHeaders.Authorization = new("Bearer", loginJson.RootElement.GetProperty("token").GetString());
        using var request = new HttpRequestMessage(HttpMethod.Post, "/reservations");
        request.Headers.Add("Idempotency-Key", "panel-test");
        request.Content = JsonContent.Create(new ReserveRequest("sample", 3));
        using var decision = await client.SendAsync(request, cancellation);
        Assert.True((await decision.Content.ReadFromJsonAsync<DecisionResponse>(cancellation))!.Accepted);
        using var state = await client.GetAsync("/panel/api/state", cancellation);
        Assert.Equal(HttpStatusCode.OK, state.StatusCode);
        Assert.True(state.Headers.CacheControl?.NoStore);
        using var stateJson = System.Text.Json.JsonDocument.Parse(await state.Content.ReadAsStringAsync(cancellation));
        Assert.Equal(3, stateJson.RootElement.GetProperty("exposure").GetInt64());
        Assert.Equal(3, stateJson.RootElement.GetProperty("sequence").GetInt64());
        Assert.Equal("sample", stateJson.RootElement.GetProperty("orders")[0].GetProperty("id").GetString());
    }

    [Fact]
    public async Task LostResponseAfterCommitReplaysOriginalReceiptWithoutChangingStateOrAudit()
    {
        var cancellation = TestContext.Current.CancellationToken;
        const string key = "m1-request";
        var store = Store();
        Assert.True(store.Apply("snapshot", new Snapshot("", 0, 4, [new("working", 3)])).Decision.Accepted);
        Assert.True(store.Apply("resume", new Resume("", 0)).Decision.Accepted);
        var seed = ReadDatabase(key);
        AssertDatabaseState(seed, 2, 4, 3, 7, 2, [("working", 3)]);
        AssertMissingReceipt(seed);

        byte[] signingKey = RandomNumberGenerator.GetBytes(32);
        var now = DateTime.UtcNow;
        var token = new JwtSecurityTokenHandler().WriteToken(new JwtSecurityToken(GateApi.Issuer, GateApi.Audience,
            [new Claim("sub", "synthetic-replay-test"), new Claim("role", "operator")], now.AddSeconds(-1),
            now.AddMinutes(2), new SigningCredentials(new SymmetricSecurityKey(signingKey), SecurityAlgorithms.HmacSha256)));
        async Task<WebApplication> Api(DurableGate gate)
        {
            var builder = WebApplication.CreateBuilder();
            builder.WebHost.UseTestServer();
            GateApi.Configure(builder, signingKey);
            var app = builder.Build();
            GateApi.Map(app, gate);
            try { await app.StartAsync(cancellation); return app; }
            catch { await app.DisposeAsync(); throw; }
        }
        async Task<HttpResponseMessage> Send(HttpClient client, string requestKey = key,
            string orderId = "m1-order", long quantity = 2)
        {
            using var request = new HttpRequestMessage(HttpMethod.Post, "/reservations");
            request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
            request.Headers.Add("Idempotency-Key", requestKey);
            request.Content = JsonContent.Create(new ReserveRequest(orderId, quantity));
            return await client.SendAsync(request, cancellation);
        }
        var expectedReceipt = new DecisionResponse(true, "Applied", 3, 9, true);
        async Task Replay(HttpClient client, DatabaseView unchanged)
        {
            using var reply = await Send(client);
            Assert.Equal(HttpStatusCode.OK, reply.StatusCode);
            Assert.Equal(expectedReceipt, await reply.Content.ReadFromJsonAsync<DecisionResponse>(cancellation));
            Assert.Equal(unchanged, ReadDatabase(key));
        }

        DatabaseView committed;
        await using (var app = await Api(store))
        {
            // Observe actual committed rows before suppressing the completed HTTP response.
            using var suppressor = new SuppressCommittedResponse(app.GetTestServer().CreateHandler(), () =>
            {
                var observed = ReadDatabase(key);
                AssertDatabaseState(observed, 3, 4, 5, 9, 3, [("working", 3), ("m1-order", 2)]);
                AssertStoredReceipt(observed, 3, 4, 5, 9, [("working", 3), ("m1-order", 2)]);
            });
            using var uncertainClient = new HttpClient(suppressor) { BaseAddress = new Uri("http://localhost") };
            var lost = await Assert.ThrowsAsync<HttpRequestException>(() => Send(uncertainClient));
            Assert.Equal("Injected response loss after committed endpoint response.", lost.Message);
            Assert.True(suppressor.Suppressed);
            committed = ReadDatabase(key);
            AssertDatabaseState(committed, 3, 4, 5, 9, 3, [("working", 3), ("m1-order", 2)]);
            AssertStoredReceipt(committed, 3, 4, 5, 9, [("working", 3), ("m1-order", 2)]);
            using var healthyClient = app.GetTestClient();
            await Replay(healthyClient, committed);

            using var later = await Send(healthyClient, "m1-later", "m1-later-order", 1);
            Assert.Equal(HttpStatusCode.OK, later.StatusCode);
            Assert.Equal(new DecisionResponse(true, "Applied", 4, 10, false),
                await later.Content.ReadFromJsonAsync<DecisionResponse>(cancellation));
            var laterRows = ReadDatabase("m1-later");
            AssertDatabaseState(laterRows, 4, 4, 6, 10, 4, [("working", 3), ("m1-order", 2), ("m1-later-order", 1)]);
            AssertStoredReceipt(laterRows, 4, 4, 6, 10, [("working", 3), ("m1-order", 2), ("m1-later-order", 1)]);
        }

        // A fresh host/store opens the same file. Deliberately do not seed again.
        await using var reopened = await Api(Store());
        using var reopenedClient = reopened.GetTestClient();
        var current = ReadDatabase(key);
        AssertDatabaseState(current, 4, 4, 6, 10, 4, [("working", 3), ("m1-order", 2), ("m1-later-order", 1)]);
        AssertStoredReceipt(current, 3, 4, 5, 9, [("working", 3), ("m1-order", 2)]);
        Assert.Equal(committed.Receipt, current.Receipt);
        Assert.Equal(committed.Fingerprint, current.Fingerprint);
        Assert.Equal(committed.Audit, current.Audit);
        for (var i = 0; i < 3; i++) await Replay(reopenedClient, current);

        // Both altered bodies are valid input; the same key must conflict before risk evaluation.
        foreach (var changed in new[] { new ReserveRequest("m1-order", 1), new ReserveRequest("m1-other-order", 2) })
        {
            using var conflict = await Send(reopenedClient, key, changed.OrderId!, changed.Quantity);
            Assert.Equal(HttpStatusCode.Conflict, conflict.StatusCode);
            Assert.Equal(current, ReadDatabase(key));
        }
        await Replay(reopenedClient, current);
    }

    private sealed class SuppressCommittedResponse(HttpMessageHandler inner, Action observeCommit) : DelegatingHandler(inner)
    {
        public bool Suppressed { get; private set; }
        protected override async Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        {
            var response = await base.SendAsync(request, cancellationToken);
            if (Suppressed || request.Method != HttpMethod.Post ||
                !request.Headers.TryGetValues("Idempotency-Key", out var keys) || keys.Single() != "m1-request")
                return response;
            using (response)
            {
                Assert.Equal(HttpStatusCode.OK, response.StatusCode);
                // Buffer all bytes: an early backend/transport error must not masquerade as suppression.
                await response.Content.LoadIntoBufferAsync(cancellationToken);
                Assert.Equal(new DecisionResponse(true, "Applied", 3, 9, false),
                    await response.Content.ReadFromJsonAsync<DecisionResponse>(cancellationToken));
                observeCommit();
                Suppressed = true;
            }
            throw new HttpRequestException("Injected response loss after committed endpoint response.");
        }
    }

    private sealed record DatabaseView(string State, long Receipts, long Audits, long TargetReceipts,
        long TargetAudits, string? Receipt, string? Fingerprint, string? Audit, long? Delivered);

    private DatabaseView ReadDatabase(string key)
    {
        using var db = new SqliteConnection(new SqliteConnectionStringBuilder
        {
            DataSource = path, Mode = SqliteOpenMode.ReadOnly, Pooling = false
        }.ToString());
        db.Open();
        object? Read(string sql)
        {
            using var command = db.CreateCommand();
            command.CommandText = sql;
            command.Parameters.AddWithValue("$id", key);
            return command.ExecuteScalar();
        }
        return new((string)Read("SELECT state FROM gate WHERE id=1")!,
            (long)Read("SELECT count(*) FROM receipts")!, (long)Read("SELECT count(*) FROM outbox")!,
            (long)Read("SELECT count(*) FROM receipts WHERE id=$id")!, (long)Read("SELECT count(*) FROM outbox WHERE id=$id")!,
            (string?)Read("SELECT decision FROM receipts WHERE id=$id"), (string?)Read("SELECT fingerprint FROM receipts WHERE id=$id"),
            (string?)Read("SELECT payload FROM outbox WHERE id=$id"), (long?)Read("SELECT delivered FROM outbox WHERE id=$id"));
    }

    private static void AssertMissingReceipt(DatabaseView view)
    {
        Assert.Equal(0, view.TargetReceipts);
        Assert.Equal(0, view.TargetAudits);
        Assert.Null(view.Receipt);
        Assert.Null(view.Fingerprint);
        Assert.Null(view.Audit);
        Assert.Null(view.Delivered);
    }

    private static void AssertDatabaseState(DatabaseView view, long sequence, long position, long pending,
        long exposure, long total, (string Id, long Remaining)[] orders)
    {
        using var json = JsonDocument.Parse(view.State);
        AssertLiteralState(json.RootElement, sequence, position, pending, exposure, orders);
        Assert.Equal(total, view.Receipts);
        Assert.Equal(total, view.Audits);
    }

    private static void AssertStoredReceipt(DatabaseView view, long sequence, long position, long pending,
        long exposure, (string Id, long Remaining)[] orders)
    {
        Assert.Equal(1, view.TargetReceipts);
        Assert.Equal(1, view.TargetAudits);
        Assert.NotNull(view.Fingerprint);
        Assert.Equal(64, view.Fingerprint.Length);
        Assert.Equal(0, view.Delivered);
        Assert.NotNull(view.Receipt);
        Assert.Equal(view.Receipt, view.Audit);
        using var json = JsonDocument.Parse(view.Receipt);
        Assert.True(json.RootElement.GetProperty("Accepted").GetBoolean());
        Assert.Equal("Applied", json.RootElement.GetProperty("Reason").GetString());
        AssertLiteralState(json.RootElement.GetProperty("State"), sequence, position, pending, exposure, orders);
    }

    private static void AssertLiteralState(JsonElement state, long sequence, long position, long pending,
        long exposure, (string Id, long Remaining)[] orders)
    {
        Assert.Equal(sequence, state.GetProperty("Sequence").GetInt64());
        Assert.Equal(position, state.GetProperty("Position").GetInt64());
        Assert.Equal(pending, state.GetProperty("Pending").GetInt64());
        Assert.Equal(exposure, state.GetProperty("ReservedExposure").GetInt64());
        Assert.True(state.GetProperty("Reconciled").GetBoolean());
        Assert.False(state.GetProperty("Stopped").GetBoolean());
        var actualOrders = state.GetProperty("Orders");
        Assert.Equal(orders.Length, actualOrders.EnumerateObject().Count());
        foreach (var order in orders)
        {
            Assert.Equal(order.Remaining, actualOrders.GetProperty(order.Id).GetProperty("Remaining").GetInt64());
            Assert.False(actualOrders.GetProperty(order.Id).GetProperty("CancelRequested").GetBoolean());
        }
    }

    public void Dispose()
    {
        foreach (var suffix in new[] { "", "-journal", "-wal", "-shm" }) File.Delete(path + suffix);
    }
}
