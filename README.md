# Trading Execution Lab — C# order state and reserved exposure

[![C# synthetic invariants](https://github.com/pouriaquant91/trading-execution-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/pouriaquant91/trading-execution-lab/actions/workflows/ci.yml)

[Reviewer guide](https://pouriajamali.site/work/engineering-evidence/) · [Source releases](https://github.com/pouriaquant91/trading-execution-lab/releases) · [Model boundaries](SCOPE.md)

A C# event/state model makes exposure reservations, cancellation races and
recovery gates inspectable. Immutable state, typed events and 24 test cases let a
reviewer trace why a command was accepted, denied or stopped for reconciliation.
An additive bounded-channel host now demonstrates concurrent admission, single-writer
state ownership and shutdown/cancellation contracts. The original 24 model cases
remain intact, alongside 9 hosting cases (**33 total**).

## Inspect the new host and measurements

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
  [`RiskDenialDoesNotCreateFalseSequenceGap`](https://github.com/pouriaquant91/trading-execution-lab/blob/v0.2.0/ExecutionLab.Tests/OrderGateTests.cs#L27):
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
**xUnit v3 4.0.2** from NuGet; the library has no external package dependency.

```sh
dotnet run --project ExecutionLab.Tests/ExecutionLab.Tests.csproj --configuration Release
dotnet run --project ExecutionLab.Measurements/ExecutionLab.Measurements.csproj --configuration Release -- --output artifacts/measurement
```

The target is a reproducible sample target, not historical employer runtime
usage. No real TT or C++ SDK version is inferred. [SCOPE.md](SCOPE.md) records the
single-stream model, retention limits and unimplemented adapter responsibilities.

## Verification and release history

- **v0.3.0:** additive host/measurement projects and 9 hosting cases; core
  model and 24 original cases unchanged. Local Windows SDK 10.0.403/runtime 10.0.14:
  33 passed, 0 skips; finite measurement contract passed for all 15 batches. The CI
  badge links to Windows/Linux correctness runs and per-run measurement artifacts.
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

## Attribution

Independent synthetic portfolio material created with AI assistance in October
2026 for Pouria Jamali. No employer/private-project source, real account/market
data or broker connection is included.
