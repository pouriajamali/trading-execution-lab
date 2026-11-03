using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Security.Claims;
using System.Security.Cryptography;
using System.IdentityModel.Tokens.Jwt;
using ExecutionLab;
using ExecutionLab.Api;
using ExecutionLab.Persistence;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.TestHost;
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
        Assert.Throws<IOException>(() => store.ApplyForTest("reserve", command, () => throw new IOException("injected")));
        Assert.Equal(2, Store().ReadState().Sequence);
        Assert.Equal(0, store.ReadState().ReservedExposure);
        Assert.Equal(2, store.PendingAudit().Count);
        var retry = Store().Apply("reserve", command);
        Assert.False(retry.Replayed);
        Assert.True(retry.Decision.Accepted);
        Assert.Equal(3, store.PendingAudit().Count);
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
        byte[] key = RandomNumberGenerator.GetBytes(32);
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
        string Token(string role, byte[] signingKey, string? audience = null, DateTime? expires = null)
        {
            var end = expires ?? DateTime.UtcNow.AddMinutes(2);
            var token = new JwtSecurityToken(GateApi.Issuer, audience ?? GateApi.Audience,
                [new Claim("sub", "synthetic-operator"), new Claim("role", role)],
                end.AddMinutes(-5), end, new SigningCredentials(new SymmetricSecurityKey(signingKey), SecurityAlgorithms.HmacSha256));
            return new JwtSecurityTokenHandler().WriteToken(token);
        }
        Assert.Equal(HttpStatusCode.Unauthorized, (await Send(null)).StatusCode);
        Assert.Equal(HttpStatusCode.Unauthorized, (await Send(Token("operator", RandomNumberGenerator.GetBytes(32)))).StatusCode);
        Assert.Equal(HttpStatusCode.Unauthorized, (await Send(Token("operator", key, "wrong-audience"))).StatusCode);
        Assert.Equal(HttpStatusCode.Unauthorized, (await Send(Token("operator", key, expires: DateTime.UtcNow.AddMinutes(-1)))).StatusCode);
        Assert.Equal(HttpStatusCode.Forbidden, (await Send(Token("reader", key))).StatusCode);
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

    public void Dispose()
    {
        foreach (var suffix in new[] { "", "-journal", "-wal", "-shm" }) File.Delete(path + suffix);
    }
}
