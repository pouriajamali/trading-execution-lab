# ADR 0002: transactional control-plane boundary

Status: accepted for an independent synthetic sample, 3 November 2026.

## Problem and choice

The in-memory single-writer host prevents concurrent local oversubscription but
does not survive a process restart. A request may commit and its HTTP response
may be lost. Replaying it must not reserve twice, while reusing its key for a
different payload must fail explicitly.

`DurableGate` uses one file-backed SQLite database and an immediate transaction
for the complete read/apply/write operation. Every committed request writes its
returned state, original receipt and audit outbox fact together. **A denied
decision still commits returned state** when the core consumes its envelope.
Keys identify normalized local requests, not TT/CME wire sequences. Payload
fingerprints include event type and content, excluding replaced local metadata.
The exposure limit is persisted; opening the same file with a different limit
fails instead of silently changing risk configuration.

An identical retry returns its original historical receipt. It does not mean
the state is still current; a caller must not adopt that receipt as a new baseline
or interpret it as permission to send a live exchange order. `ReadState` reads
the current local model. No exchange submission is implemented.

## Outbox and inbox

An outbox record is an audit fact, not an executable order command. The local
illustration passes it to an inbox with a counter projection. Inbox insertion
and counter increment share a transaction. A failure after this commit but before
the outbox acknowledgement results in redelivery and no repeated counter effect.
Different content for a previously consumed ID conflicts.

This is **at-least-once handoff**, not exactly-once delivery. The tests exercise
actual database transactions, independent connections and a reopened store;
failure injection is an exception before commit and an omitted acknowledgement,
not a power-loss or real-broker test. No RabbitMQ service is represented as tested.

## API/security boundary

`POST /reservations` requires a validated JWT with `sub` and `operator` role.
The HMAC algorithm is restricted; signature, issuer, audience, expiry and role
are exercised by actual ASP.NET Core TestServer requests. A random test key is
generated in memory. The local executable requires a private base64 key of at
least 256 bits and a disposable database path in environment variables. It binds
only to `127.0.0.1:5087`; it is not a public deployment recipe or production IdP.
All operators share one fictitious gate: authorization is not tenant isolation.

Fresh storage is stopped/unreconciled. There is intentionally no HTTP snapshot,
resume, fill or flatten endpoint. Tests seed a synthetic baseline through the
typed local library. An HTTP200 carries a decision, including a business denial;
400 is invalid input, 401 invalid/missing token, 403 insufficient role and 409
key/content conflict. Infrastructure failures are not converted into risk denial.

## Alternatives and costs

- In-memory dictionaries lose the receipt after restart and cannot atomically
  commit audit facts with state.
- A broker publish inside the state transaction is a dual-write failure window;
  the outbox preserves the audit record before handoff.
- SQL Server/PostgreSQL, external identity providers and a broker are relevant
  next integration targets, not interchangeable with this SQLite evidence.
- SQLite serializes writers and synchronous calls block request threads. This
  prioritizes a small inspectable contract, not a scalable API or low-latency
  execution path. Receipt/state/ID retention and schema migration remain unbounded.
- The demo places inbox and outbox tables in the same database but uses separate
  commits/connections. It does not reproduce two-service/network failure modes.

Run `dotnet run --project ExecutionLab.Tests/ExecutionLab.Tests.csproj -c Release`.
No cloud account, market data, broker, external HTTP port or persistent secret is
needed. See [Microsoft transactions](https://learn.microsoft.com/en-us/dotnet/standard/data/sqlite/transactions),
[JWT validation](https://learn.microsoft.com/en-us/aspnet/core/security/authentication/configure-jwt-bearer-authentication?view=aspnetcore-10.0)
and [HTTP integration testing](https://learn.microsoft.com/en-us/aspnet/core/test/integration-tests?view=aspnetcore-10.0).
