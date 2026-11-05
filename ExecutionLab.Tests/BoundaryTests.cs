using System.IdentityModel.Tokens.Jwt;
using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Security.Claims;
using System.Security.Cryptography;
using ExecutionLab;
using ExecutionLab.Api;
using ExecutionLab.Persistence;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.TestHost;
using Microsoft.IdentityModel.Tokens;
using Xunit;

public sealed class BoundaryTests : IDisposable
{
    private readonly string path = Path.Combine(Path.GetTempPath(), $"execution-boundary-{Guid.NewGuid():N}.sqlite");
    private readonly byte[] key = RandomNumberGenerator.GetBytes(32);
    private DurableGate Store() => new(path, 10);
    private DurableGate Ready()
    {
        var store = Store();
        store.Apply("snapshot", new Snapshot("", 0, 4, [new("working", 3)]));
        store.Apply("resume", new Resume("", 0));
        return store;
    }
    private string Token(string subject = "synthetic-operator", string role = "operator") =>
        new JwtSecurityTokenHandler().WriteToken(new JwtSecurityToken(GateApi.Issuer, GateApi.Audience,
            [new Claim("sub", subject), new Claim("role", role)], DateTime.UtcNow.AddSeconds(-1),
            DateTime.UtcNow.AddMinutes(2), new SigningCredentials(new SymmetricSecurityKey(key), SecurityAlgorithms.HmacSha256)));
    private async Task<WebApplication> Api(DurableGate store, bool panel = false)
    {
        var builder = WebApplication.CreateBuilder();
        builder.WebHost.UseTestServer();
        GateApi.Configure(builder, key);
        if (panel) PanelApi.Configure(builder);
        var app = builder.Build();
        if (panel) PanelApi.Map(app, store, 10, key, "SYNTHETIC-TEST-OPERATOR-CODE");
        GateApi.Map(app, store);
        await app.StartAsync(TestContext.Current.CancellationToken);
        return app;
    }
    private async Task<HttpResponseMessage> Post(HttpClient client, string json, string id = "request")
    {
        using var request = new HttpRequestMessage(HttpMethod.Post, "/reservations");
        request.Headers.Add("Idempotency-Key", id);
        request.Content = new StringContent(json, System.Text.Encoding.UTF8, "application/json");
        return await client.SendAsync(request, TestContext.Current.CancellationToken);
    }

    [Theory]
    [InlineData("")]
    [InlineData("   ")]
    public async Task EmptySubjectCannotAuthorizeAnOperator(string subject)
    {
        var store = Ready();
        await using var app = await Api(store);
        using var client = app.GetTestClient();
        client.DefaultRequestHeaders.Authorization = new("Bearer", Token(subject));
        using var response = await Post(client, "{\"orderId\":\"new\",\"quantity\":2}");
        Assert.Equal(HttpStatusCode.Forbidden, response.StatusCode);
        Assert.Equal(7, store.ReadState().ReservedExposure);
        Assert.Equal(2, store.PendingAudit().Count);
    }

    [Theory]
    [InlineData("{\"orderId\":\"new\",\"quantity\":-1}")]
    [InlineData("{\"orderId\":\"new\",\"quantity\":1.5}")]
    [InlineData("{\"orderId\":\"new\",\"quantity\":9223372036854775808}")]
    [InlineData("{\"orderId\":null,\"quantity\":2}")]
    [InlineData("null")]
    public async Task InvalidHttpBodiesDoNotWriteAnyTransactionalEffects(string json)
    {
        var store = Ready();
        await using var app = await Api(store);
        using var client = app.GetTestClient();
        client.DefaultRequestHeaders.Authorization = new("Bearer", Token());
        using var response = await Post(client, json);
        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
        Assert.Equal(2, Store().ReadState().Sequence);
        Assert.Equal(7, Store().ReadState().ReservedExposure);
        Assert.Equal(2, Store().PendingAudit().Count);
    }

    [Fact]
    public async Task OverflowDecisionPersistsAHaltAndHistoricalReceipt()
    {
        var store = Ready();
        await using var app = await Api(store);
        using var client = app.GetTestClient();
        client.DefaultRequestHeaders.Authorization = new("Bearer", Token());
        const string body = "{\"orderId\":\"overflow\",\"quantity\":9223372036854775807}";
        using var response = await Post(client, body);
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        var decision = (await response.Content.ReadFromJsonAsync<DecisionResponse>(TestContext.Current.CancellationToken))!;
        Assert.False(decision.Accepted);
        Assert.Contains("overflow", decision.Reason);
        var state = Store().ReadState();
        Assert.True(state.Stopped);
        Assert.False(state.Reconciled);
        Assert.Equal(7, state.ReservedExposure);
        Assert.Equal(3, store.PendingAudit().Count);
        using var retry = await Post(client, body);
        Assert.True((await retry.Content.ReadFromJsonAsync<DecisionResponse>(TestContext.Current.CancellationToken))!.Replayed);
        Assert.Equal(3, Store().PendingAudit().Count);
    }

    [Fact]
    public async Task RacingDifferentBodiesOnOneKeyCommitOnlyOneReceipt()
    {
        Ready();
        var left = Store(); var right = Store();
        using var start = new Barrier(2);
        Task<CommitResult?> Send(DurableGate store, long quantity) => Task.Run(() =>
        {
            if (!start.SignalAndWait(TimeSpan.FromSeconds(5))) throw new TimeoutException();
            try { return store.Apply("shared-key", new Reserve("", 0, "new", quantity)); }
            catch (IdempotencyConflictException) { return null; }
        }, TestContext.Current.CancellationToken);
        var results = await Task.WhenAll(Send(left, 1), Send(right, 2)).WaitAsync(TimeSpan.FromSeconds(15), TestContext.Current.CancellationToken);
        var winner = Assert.Single(results, x => x is not null)!;
        Assert.True(winner.Decision.Accepted);
        Assert.False(winner.Replayed);
        Assert.Equal(winner.Decision.State.ReservedExposure, Store().ReadState().ReservedExposure);
        Assert.Equal(3, Store().ReadState().Sequence);
        Assert.Equal(3, Store().PendingAudit().Count);
    }

    [Theory]
    [InlineData(true)]
    [InlineData(false)]
    public void CancelFillOrderingsRetainCapacityOrExplicitlyRequireReconciliation(bool fillFirst)
    {
        var store = Ready();
        Assert.True(store.Apply("cancel", new RequestCancel("", 0, "working")).Decision.Accepted);
        Assert.Equal(7, Store().ReadState().ReservedExposure);
        Assert.True(store.Apply("new", new Reserve("", 0, "other", 3)).Decision.Accepted);
        Assert.False(store.Apply("denied", new Reserve("", 0, "extra", 1)).Decision.Accepted);
        var fill = new Fill("", 0, "working", "execution", 1);
        var cancel = new ConfirmCancel("", 0, "working");
        if (fillFirst)
        {
            Assert.True(Store().Apply("fill", fill).Decision.Accepted);
            Assert.Equal(10, Store().ReadState().ReservedExposure);
            Assert.True(Store().Apply("confirmed", cancel).Decision.Accepted);
            Assert.Equal(8, Store().ReadState().ReservedExposure);
            Assert.False(Store().ReadState().Stopped);
        }
        else
        {
            Assert.True(Store().Apply("confirmed", cancel).Decision.Accepted);
            Assert.Equal(7, Store().ReadState().ReservedExposure);
            Assert.False(Store().Apply("fill", fill).Decision.Accepted);
            Assert.True(Store().ReadState().Stopped);
            Assert.False(Store().ReadState().Reconciled);
            Assert.False(Store().Apply("blocked", new Reserve("", 0, "after-anomaly", 1)).Decision.Accepted);
            Assert.Equal(7, Store().ReadState().ReservedExposure);
        }
    }

    [Fact]
    public async Task ConcurrentFillAndCancelCommitOneDocumentedOrderingWithoutReleasingEarly()
    {
        var store = Ready();
        store.Apply("cancel", new RequestCancel("", 0, "working"));
        Assert.Equal(7, Store().ReadState().ReservedExposure);
        store.Apply("other", new Reserve("", 0, "other", 3));
        using var start = new Barrier(2);
        var fillStore = Store(); var cancelStore = Store();
        Task<CommitResult> Send(DurableGate connection, string id, GateEvent input) => Task.Run(() =>
        {
            if (!start.SignalAndWait(TimeSpan.FromSeconds(5))) throw new TimeoutException();
            return connection.Apply(id, input);
        }, TestContext.Current.CancellationToken);
        var fill = Send(fillStore, "fill", new Fill("", 0, "working", "execution", 1));
        var cancel = Send(cancelStore, "confirmed", new ConfirmCancel("", 0, "working"));
        var results = await Task.WhenAll(fill, cancel).WaitAsync(TimeSpan.FromSeconds(15), TestContext.Current.CancellationToken);
        Assert.True(results[1].Decision.Accepted);
        var state = Store().ReadState();
        Assert.Equal(results[0].Decision.Accepted ? 8 : 7, state.ReservedExposure);
        Assert.Equal(!results[0].Decision.Accepted, state.Stopped);
        Assert.Equal(results[0].Decision.Accepted, state.Reconciled);
        Assert.All(results, result => Assert.InRange(result.Decision.State.ReservedExposure, 0, 10));
        Assert.Equal(6, Store().PendingAudit().Count);
        Assert.Equal(3, state.Orders["other"].Remaining);
    }

    [Fact]
    public async Task PanelLimitsLoginAttemptsAndRequiresOperatorForState()
    {
        var store = Ready();
        await using var app = await Api(store, panel: true);
        using var client = app.GetTestClient();
        client.DefaultRequestHeaders.Authorization = new("Bearer", Token(role: "reader"));
        using var denied = await client.GetAsync("/panel/api/state", TestContext.Current.CancellationToken);
        Assert.Equal(HttpStatusCode.Forbidden, denied.StatusCode);
        client.DefaultRequestHeaders.Authorization = null;
        for (var i = 0; i < 8; i++)
        {
            using var wrong = await client.PostAsJsonAsync("/panel/api/session", new OperatorLogin("wrong-synthetic-code"), TestContext.Current.CancellationToken);
            Assert.Equal(HttpStatusCode.Unauthorized, wrong.StatusCode);
            Assert.True(wrong.Headers.CacheControl?.NoStore);
        }
        using var limited = await client.PostAsJsonAsync("/panel/api/session", new OperatorLogin("SYNTHETIC-TEST-OPERATOR-CODE"), TestContext.Current.CancellationToken);
        Assert.Equal(HttpStatusCode.TooManyRequests, limited.StatusCode);
        Assert.Equal(2, store.PendingAudit().Count);
    }
    public void Dispose()
    {
        foreach (var suffix in new[] { "", "-journal", "-wal", "-shm" }) File.Delete(path + suffix);
    }
}
