# Model scope and limits

## Contract

One instrument, one non-negative direction, integer lots and one serialized,
normalized input stream. Caller-supplied normalized facts and snapshots are
trusted inputs. The sequence belongs to this model; it is **not a TT/CME wire
feed sequence**. A real adapter must resolve independent channels, timestamps,
reset boundaries, authoritative snapshots and execution-ID payload consistency.

Immutable state and typed events prioritize inspection. Envelope IDs, execution IDs and used order IDs are retained within
the in-memory session without a bounded retention policy. The core itself has no
persistence. The optional SQLite control-plane wrapper has a separately tested
transaction/reopen contract, not an exchange-state recovery guarantee.
Stop-on-anomaly is this example's teaching policy,
not a universal policy for trading systems.

## Outside the implementation

- Shorts/netting, pricing, margin and multi-account aggregation.
- Synchronization of callers using the core directly, authoritative broker
  recovery and bounded ID-store/database retention.
- Broker rejection/replacement races, exchange packet decoding and real adapters.
- External order cancellation or position close-out. Disconnect/stop does not
  imply either action occurred; real actions require confirmed external responses.
- Exchange certification/conformance, including CME conformance.

## Evidence boundary

The repository is not a TT adapter, a reconstruction of a private project or
evidence of historical production incidents/performance. It contains no SDK
integration, credentials, real account/market data, external network calls or order
submission. The optional API binds only to loopback; integration tests use an
in-memory HTTP test server. The .NET 10 target and dependencies describe this public
sample, not a workplace stack.

The additive host serializes admitted commands through one consumer and assigns
its own cursor; it does not validate upstream ordering across feeds. Its bounded
channel limits buffered entries, not all waiting tasks/payloads or growing ID
stores. Admission cancellation is different from undoing an admitted event.
Dispose closes admission and drains work; it does not submit broker commands.
Internal friend-assembly barriers exist only for deterministic tests and cannot
be supplied through the public constructor.

Finite local measurements now record core/host event durations, process allocation
and GC counts. The method states its workload, timer probe and boundaries. They
are not exchange latency, a workplace result, a general speedup or a production
readiness claim. The 24 core + 9 hosting tests establish the tested behavior under
these assumptions. CI results remain separate from production correctness.

## Transactional control-plane scope

Nine additional integration cases cover actual SQLite transactions and the JWT
HTTP pipeline. One database owns one synthetic long-only gate and a fixed exposure
limit; all authorized operators share it. There is no account/tenant isolation,
external identity provider or OAuth authorization server,
broker dispatcher, schema-upgrade system, production SLO or HFT timing claim.
The local HMAC key is supplied privately at runtime; tests generate random keys.

Audit outbox and inbox commits are separate: redelivery is allowed. Only the
inbox/counter effect is transactional and deduplicated. A historical retry receipt
is not a current risk snapshot and cannot authorize new external execution.
Persisting a previously reconciled model state does not reconcile a live account.
Failure tests inject exceptions/omit acknowledgement; power-loss, disk corruption,
cross-machine partitions and broker failure behavior have not been tested.

## Audited local panel boundary (v0.5.1-preview.1)

The opt-in local-code endpoint issues a short-lived token, not an external IdP.
All operators share the same fictitious gate. There is no tenant/account order
ownership. The audited runtime release retains 56 C# cases (24 original model,
9 original host, 23 transaction/API/boundary cases) plus 11 protocol tests.

The React client verifies closed session/state/receipt shapes, at most 1MiB of
actual UTF-8 response bytes, at most 10,000 active orders, <=64-code-unit IDs,
safe nonnegative JavaScript integers, unique IDs and exact exposure sums.
Unrepresentable Int64 values and inconsistent/unknown DTOs fail closed as
unverified responses. This is a bounded display profile, not bounded store
retention. A last request/key survives reauthentication only in the same tab;
reload or closure loses it.

Actual-package probes use installed ASP.NET Core runtimes, real loopback HTTP
and disposable SQLite. Process reopen and a pre-commit exception are separate
from power loss/crash-in-the-middle. The UI has no fill/cancel/resume controls;
those invariants are exercised through typed local tests. Audit is at-least-once
redelivery with deduplicated inbox effects, not exactly-once delivery.

## Source-only response-loss regression (10 November 2026)

The source suite adds one TestServer response-suppression case and strengthens
the existing pre-commit rollback case: 57 C# cases passed locally on Windows
with SDK 10.0.404 / actual runtime 10.0.15, with zero failures or skips. Fresh
read-only SQL checks literal state, target-key receipt and outbox payloads;
reopening without reseeding and historical replay must preserve later state.
Valid changed-intent requests must conflict without new effects. The handler
first receives the actual completed API response and observes the commit, then
withholds it from the caller. It does not simulate a TCP disconnect or kill.

Runtime/API/UI, package and project pins, CI SDK 10.0.403, previous tag evidence
and v0.5.2-preview.1 binary assets are unchanged. This Windows source result does
not establish hosted exact-commit Windows/Linux CI; that gate remains pending.
The earlier browser audit remains historical evidence; no new browser, native
package, crash, power-loss or broker test is claimed for this source-only change.

The current correctness workflow does not rerun profiling. Original raw
measurements and their measured-source boundary are retained.
