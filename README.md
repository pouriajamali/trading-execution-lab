# Trading Execution Lab — C# order state and reserved exposure

[![C# synthetic invariants](https://github.com/pouriajamali/trading-execution-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/pouriajamali/trading-execution-lab/actions/workflows/ci.yml)

[Try the browser demo](https://pouriajamali.site/demo/operator-panel/) · [Download the local panel](https://github.com/pouriajamali/trading-execution-lab/releases/tag/v0.5.2-preview.1) · [Engineering proof](docs/CASE-STUDY.md) · [Scope](SCOPE.md)

Explore order-risk decisions and retry-safe request processing in C#/.NET.
The sample combines an order-state model, a single-writer host and an ASP.NET Core
API that commits SQLite state, an idempotency receipt and an audit outbox together.
The current .NET suite has 56 cases; the original 24 model cases remain intact.

## Architecture review

Read the [architecture case study](docs/ARCHITECTURE-CASE-STUDY.md) for the decision, rejected alternatives, failure examples, frozen-release evidence and short English/Persian introductions. Follow the [30-minute four-project review](https://github.com/pouriajamali/trading-execution-lab/blob/main/docs/FLAGSHIP-REVIEW.md) for a guided discussion. The [evidence index](docs/FLAGSHIP-EVIDENCE.json) separates runtime/tag CI from later documentation commits.

## What this audit proves

The [case study](docs/CASE-STUDY.md) maps decisions to source, named tests and
exact-release package checks. A pre-commit exception rolls back state, receipt
and audit together; a lost/unverifiable response is an **unknown receipt**.
Same-key replay preserves the original result. The UI labels failed refreshes
stale and blocks new requests until an unresolved receipt is checked. The
signed-token policy rejects empty subjects. Historical measurements remain
unchanged; no new profiling dataset was generated for this audit.

## Try it in one minute

Open the [browser demo](https://pouriajamali.site/demo/operator-panel/) with no
installation or account. Start with 4 filled lots and 3 working lots against a
10-lot limit:

1. Reserve 2 lots: exposure becomes 9.
2. Replay the same request: exposure stays at 9.
3. Submit another 2 lots with a new order ID: the gate denies it.

The browser demo uses a synthetic JavaScript model. The downloadable local panel
below runs against the actual .NET API and SQLite sample; they are separate
implementations. For the transaction and recovery decisions, follow the
[reviewer guide](https://pouriajamali.site/work/engineering-evidence/).

## Check the C# implementation

With the .NET 10 SDK, run this from a fresh source checkout:

```sh
dotnet run --project ExecutionLab.Tests/ExecutionLab.Tests.csproj -c Release
```

**Expected result:** the verification runner exits successfully after checking
order risk, host admission and durable API behavior. A repeated request returns
its original receipt; it does not reserve exposure again. Start with
[the transaction tests](ExecutionLab.Tests/DurabilityTests.cs) to inspect that
boundary. For a reproducible issue or a focused change, see
[Contributing](CONTRIBUTING.md).

## Operator Panel preview

The opt-in [React and TypeScript panel](OperatorPanel) uses the same .NET API
and SQLite gate as the existing reservation sample. Sign in locally, read the
current exposure and working orders, evaluate a synthetic reservation and replay
the same request to inspect its original receipt. The live state and a receipt
are shown separately because a historical replay can differ from current state.

**Windows / Ubuntu quick start.** Download the matching x64 archive and checksums
from [v0.5.2-preview.1](https://github.com/pouriajamali/trading-execution-lab/releases/tag/v0.5.2-preview.1):
[Windows ZIP](https://github.com/pouriajamali/trading-execution-lab/releases/download/v0.5.2-preview.1/trading-execution-lab-v0.5.2-preview.1-win-x64.zip) ·
[Ubuntu/glibc tar.gz](https://github.com/pouriajamali/trading-execution-lab/releases/download/v0.5.2-preview.1/trading-execution-lab-v0.5.2-preview.1-linux-x64.tar.gz) ·
[SHA256SUMS](https://github.com/pouriajamali/trading-execution-lab/releases/download/v0.5.2-preview.1/SHA256SUMS.txt).
Extract the whole folder. Install x64 **ASP.NET Core Runtime 10.0.14 or a later
10.0 patch** and **PowerShell 7**; these packages are framework-dependent.
No SDK, Node.js or Python is required to run the panel. Before asking for an
operator code or creating temporary state, the launcher checks the selected
`dotnet` host for x64 and the required stable 10.0.14-or-later 10.0 frameworks.
A failure explains the prerequisite; it does not install software or change PATH.

Windows: `pwsh -NoProfile -File .\Start-OperatorPanel.ps1`

Ubuntu: `pwsh -NoProfile -File ./Start-OperatorPanel.ps1`

Choose a run-only operator code, then open <http://127.0.0.1:5087/panel/>.
A new ID and 2 lots move 7→9; replay stays9; a different ID and2 lots are denied.
Use Ctrl+C to stop. See [prerequisites and troubleshooting](docs/QUICKSTART.md).
Unsigned developer preview; audited targets are Windows x64 and Ubuntu24.04/glibc
x64. Other distributions, ARM, musl and macOS are unverified.

**Build from source.** With Node.js 24 and the .NET 10 SDK, run:

```sh
npm --prefix OperatorPanel ci
npm --prefix OperatorPanel test
npm --prefix OperatorPanel run build
dotnet publish ExecutionLab.Api/ExecutionLab.Api.csproj -c Release --no-self-contained -p:UseAppHost=false -o artifacts/operator-panel
pwsh -File scripts/Start-OperatorPanel.ps1 -PublishedDirectory artifacts/operator-panel
```

The launcher creates a fresh disposable SQLite file and a per-run signing key.
The optional operator-code endpoint is rate limited and issues a 15-minute token
held in browser memory. The API is loopback-only and keeps the default halted
behavior unless a new, explicitly synthetic database is seeded. A saved database
cannot be reseeded. The launcher starts fresh each run and removes only its own
temporary directory on normal/finally exit; forced termination can leave it behind.
There are no exchange credentials, broker
adapters or real-order controls.

## Inspect transactional delivery and API contracts

- [DurableGate](ExecutionLab.Persistence/DurableGate.cs) commits returned state,
  an idempotency receipt and an audit outbox row in one SQLite transaction.
  Separate connections serialize competing reservations. Retrying the same key
  returns its original receipt; changed content conflicts instead of reserving twice.
- [API](ExecutionLab.Api/GateApi.cs) validates JWT signature, issuer, audience,
  expiry and operator role before a bounded reservation request reaches storage.
- [Integration tests](ExecutionLab.Tests/DurabilityTests.cs) run the actual HTTP
  pipeline and a fresh on-disk database: reopen/retry, pre-commit rollback,
  concurrent connections, conflicting keys, risk-denial persistence and audit
  redelivery after consumer commit/before acknowledgement.
- [Design decision and reproduction](docs/decisions/0002-transactional-control-plane.md)
  explains transaction ownership, historical receipts, authentication choices and
  the tradeoffs. The outbox contains **audit facts**, not exchange commands.
  Its illustrative local inbox/counter is not a RabbitMQ transport.

## Inspect the separate in-memory host and historical measurements

- [SerializedExecutionSession](ExecutionLab.Hosting/SerializedExecutionSession.cs):
  multiple producers, one state owner, `FullMode.Wait`, admission-only cancellation
  and drain-on-close. Caller sequences are replaced by a **local** cursor; this
  is neither exchange sequencing nor reconstruction of cross-feed causality.
- [Deterministic hosting tests](ExecutionLab.Tests/HostingTests.cs): concurrent
  reservations cannot exceed the exposure limit; controlled barriers cover blocked writers,
  cancellation before/after admission, draining and worker-failure propagation.
- [Architecture decision](docs/decisions/0001-single-writer.md): ownership choices,
  alternatives and the cost of asynchronous coordination.
- [Measurement method](docs/MEASUREMENTS.md) and [raw local report](docs/measurements/windows-local-20261102/report.json):
  direct core versus one-/four-producer hosting; per-batch p50/p95/p99, process-wide
  allocation and GC counts, clock probe, source hashes and raw event ticks. These
  measure an independent synthetic workload, **not TT/CME or workplace latency**.

## Decisions worth inspecting

- **Reserve before submission.** A new reservation is accepted only when filled
  position plus outstanding quantity plus the proposed quantity does not exceed
  the limit. Requesting cancellation keeps capacity reserved; confirmation
  releases only the unfilled remainder. Fills arriving during cancellation count.
- **Separate rejection from missing data.** A valid but risk-denied command
  consumes its normalized envelope without reserving quantity. The next valid
  event therefore does not create a false gap. Inspect
  [`RiskDenialDoesNotCreateFalseSequenceGap`](https://github.com/pouriajamali/trading-execution-lab/blob/v0.2.0/ExecutionLab.Tests/OrderGateTests.cs#L27):
  sequence 3 is risk-denied; cancellation at sequence 4 still applies to the
  reconciled state. Invalid envelopes and stale duplicates are not consumed.
- **Deduplicate at two levels.** Envelope IDs and execution IDs serve different
  purposes. A redelivered fill with a new envelope advances sequence without
  double-counting quantity. Order IDs are not reused within an in-memory session.
- **Recovery is an explicit gate.** A sequence gap, unknown fill, unsolicited
  cancellation or arithmetic overflow blocks new reservations and requires a
  fresh authoritative snapshot baseline followed by explicit resume. A snapshot
  does not automatically restart trading.
- **Keep external effects separate.** Disconnect/stop blocks local reservations;
  it does not cancel broker orders or flatten a real position. Those operations
  need adapters and confirmed responses. The model deliberately supplies neither.

## Run

Requires the **.NET 10 SDK (LTS)**, including the .NET 10 runtime. Tests use
**xUnit v3 4.0.2** from NuGet. API, TestHost and SQLite use Microsoft packages
**10.0.14**; the core library still has no external package dependency.

```sh
dotnet run --project ExecutionLab.Tests/ExecutionLab.Tests.csproj --configuration Release
dotnet run --project ExecutionLab.Measurements/ExecutionLab.Measurements.csproj --configuration Release -- --output artifacts/measurement
```

The target is a reproducible sample target, not historical employer runtime
usage. No real TT or C++ SDK version is inferred. [SCOPE.md](SCOPE.md) records the
single-stream model, retention limits and unimplemented adapter responsibilities.

## Verification and release history

- **v0.5.2-preview.1:** selected-host runtime preflight before prompt/key/temp;
  16 controlled launcher cases plus existing actual-package Windows/Linux checks.
  See [release notes](docs/RELEASE-v0.5.2-preview.1.md). Core/API behavior and
  historical measurements are unchanged.
- **v0.5.1-preview.1:** stale/unknown receipt UI, bounded closed DTO validation,
  handler-level form guard, nonblank JWT subject, loopback configuration guard
  and launcher exit/environment/cleanup fixes.56 C# cases, 11 protocol tests
  and matching-OS extracted-package HTTP/SQLite checks. See the
  [claim/test map](docs/CASE-STUDY.md). API/UI share version 0.5.1-preview.1; original
  core/host code and historical measurement bytes remain unchanged.
- **v0.4.0:** transactional state/receipt/audit outbox and inbox, JWT-protected
  control-plane API, 9 new integration cases. No core/host behavior change.
  Reproduction needs no account, cloud service, broker, network port or committed
  secret: tests use TestServer, temporary SQLite files and random ephemeral keys.
- **v0.3.0:** additive host/measurement projects and 9 hosting cases; core
  model and 24 original cases unchanged. Local Windows SDK 10.0.403/runtime 10.0.14:
  33 passed, 0 skips; finite measurement contract passed for all 15 batches. The CI
  badge links to Windows/Linux correctness runs. Historical v0.3 runs retain
  their measurement artifacts; current CI checks actual packages without fresh profiling.
  Inspect the exact release commit and downloadable source when assessing delivery.
- **v0.2.0:** source-only release; `net10.0` and SDK 10 on Ubuntu/Windows CI. Order
  model and 24 cases unchanged. Historical local Windows check on 28 October 2026:
  SDK 10.0.403 / runtime 10.0.14, all 24 cases passed, zero skips. Use the exact
  release-commit workflow to assess cloud results; local success is separate.
- **v0.1.0:** original .NET 8 sample, retained as a historical source release.

The original v0.2.0 model remains available. The suite checks the documented fixtures
and assumptions, not production correctness. The queue capacity bounds buffered
entries; waiting producer tasks and session ID stores are not a bounded-memory claim.
Separately labelled JavaScript portfolio examples remain educational.

## Contributing and license

Bug reports with a small synthetic reproduction are welcome. See
[CONTRIBUTING.md](CONTRIBUTING.md) for setup, tests and useful report details.
Original sample material is available under the [MIT license](LICENSE).
Third-party dependencies retain their respective licenses. Existing tagged
release archives are historical artifacts; this documentation update does not
replace them or change the code inside those archives.

## Verify release provenance

See the [public key, expected fingerprint and POSIX/PowerShell verification guide](https://github.com/pouriajamali/trading-execution-lab/blob/main/PROVENANCE.md)
before trusting release downloads. SSH checksum provenance is separate from OS
binary signing and does not change the MIT license or prevent copying. This
documentation update preserves existing release archives, tags and signatures.

## Attribution

Independent synthetic portfolio material created with AI assistance in October–November
2026 for Pouria Jamali. No employer/private-project source, real account/market
data or broker connection is included.
