using System.Net;
using Microsoft.AspNetCore.DataProtection;
using ExecutionLab;
using ExecutionLab.Api;
using ExecutionLab.Persistence;

var keyText = Environment.GetEnvironmentVariable("EXECUTION_LAB_KEY_BASE64")
    ?? throw new InvalidOperationException("Set EXECUTION_LAB_KEY_BASE64 locally; never commit a key.");
var dbPath = Environment.GetEnvironmentVariable("EXECUTION_LAB_DB")
    ?? throw new InvalidOperationException("Set EXECUTION_LAB_DB to a disposable synthetic SQLite file.");
const int limit = 10;
var signingKey = Convert.FromBase64String(keyText);
var panelEnabled = Environment.GetEnvironmentVariable("EXECUTION_LAB_PANEL") == "1";
var operatorCode = panelEnabled
    ? Environment.GetEnvironmentVariable("EXECUTION_LAB_OPERATOR_CODE") ?? ""
    : "";
if (panelEnabled && (operatorCode.Length is < 16 or > 128))
    throw new InvalidOperationException("Set an operator code of 16–128 characters for the local panel.");
var builder = WebApplication.CreateBuilder(args);
// Explicit Kestrel endpoints override Run(url). Reject them before creating a
// database rather than allowing configuration to widen the loopback boundary.
if (builder.Configuration.GetSection("Kestrel:Endpoints").GetChildren().Any())
    throw new InvalidOperationException("Configured Kestrel endpoints are not permitted in this loopback sample.");
builder.Services.AddDataProtection().UseEphemeralDataProtectionProvider();
GateApi.Configure(builder, signingKey);
if (panelEnabled) PanelApi.Configure(builder);
var app = builder.Build();
var seed = panelEnabled && Environment.GetEnvironmentVariable("EXECUTION_LAB_PANEL_SEED_NEW") == "1";
if (seed)
{
    // Refuse to seed any pre-existing database. A demo never resets stored state.
    using var fresh = File.Open(dbPath, FileMode.CreateNew, FileAccess.Write);
}
var store = new DurableGate(dbPath, limit);
if (seed)
{
    store.Apply("demo-snapshot", new Snapshot("demo-snapshot", 0, 4, [new("demo-working", 3)]));
    store.Apply("demo-resume", new Resume("demo-resume", 0));
}
// Applies to API-only mode as well as static assets and panel endpoints.
app.Use(async (context, next) =>
{
    if (context.Connection.RemoteIpAddress is not { } remote || !IPAddress.IsLoopback(remote) ||
        context.Request.Host.Host is not ("127.0.0.1" or "localhost"))
    {
        context.Response.StatusCode = StatusCodes.Status400BadRequest;
        return;
    }
    context.Response.Headers.ContentSecurityPolicy = "default-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'";
    context.Response.Headers["Referrer-Policy"] = "no-referrer";
    await next();
});
if (panelEnabled)
{
    app.UseDefaultFiles();
    app.UseStaticFiles();
    PanelApi.Map(app, store, limit, signingKey, operatorCode);
}
GateApi.Map(app, store);
// Deliberately fail-closed: a fresh database is stopped/unreconciled. The local
// tests seed a synthetic snapshot/resume; HTTP cannot authorize restart or fill.
app.Run("http://127.0.0.1:5087");
