using ExecutionLab.Api;
using ExecutionLab.Persistence;

var keyText = Environment.GetEnvironmentVariable("EXECUTION_LAB_KEY_BASE64")
    ?? throw new InvalidOperationException("Set EXECUTION_LAB_KEY_BASE64 locally; never commit a key.");
var dbPath = Environment.GetEnvironmentVariable("EXECUTION_LAB_DB")
    ?? throw new InvalidOperationException("Set EXECUTION_LAB_DB to a disposable synthetic SQLite file.");
var builder = WebApplication.CreateBuilder(args);
GateApi.Configure(builder, Convert.FromBase64String(keyText));
var app = builder.Build();
GateApi.Map(app, new DurableGate(dbPath, 10));
// Deliberately fail-closed: a fresh database is stopped/unreconciled. The local
// tests seed a synthetic snapshot/resume; HTTP cannot authorize restart or fill.
app.Run("http://127.0.0.1:5087");
