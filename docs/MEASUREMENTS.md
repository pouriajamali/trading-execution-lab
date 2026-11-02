# Reproducing the local C# measurements

Run from the repository root with the .NET 10 SDK:

```sh
dotnet run --project ExecutionLab.Measurements/ExecutionLab.Measurements.csproj --configuration Release -- --output artifacts/measurement
```

The finite workload uses one synthetic long-only instrument. Each batch runs 1,000
Reserve/Fill pairs, ending at position 1,000 with no pending orders. There are 2 warmup
runs per scenario and 5 measured batches for direct core application, one-producer
hosting and four-producer hosting. All final-state checks must pass. There is no
latency threshold or performance gate; CI's shared-machine measurements are not
comparable to a dedicated host.

`events.csv` contains 30,000 raw Stopwatch tick deltas. `report.json` records source
hashes, runtime/OS/architecture, clock frequency/probe, process allocation, GC
collection changes and nearest-rank percentiles for each 2,000-event batch.

## What the timers include

- **Direct core:** `OrderGate.Apply` through its returned decision; no event
  construction, channel or task completion in that event duration.
- **Hosted:** `SubmitAsync` through observation of its result, including admission,
  queueing, application and task scheduling. Multiple producers maintain their
  own Reserve-before-Fill dependency; cross-producer order is not fixed.
- **Allocation:** process-wide bytes allocated during each batch after baseline
  state and timing-buffer initialization, including construction/tasks/bookkeeping.
  It is not an allocation-per-`Apply` or zero-allocation hot-path measurement.

The per-event observer has overhead. A separate 1,000-sample clock probe is reported
without subtracting it. Values near clock resolution are not meaningful evidence
of sub-tick speed. The model's in-memory ID stores grow across each finite session;
these tests do not establish stable long-running memory use.

The retained Windows report was recorded on 2 November 2026 with runtime .NET 10.0.14.
It is one local observation, not a production baseline, TT SDK benchmark, exchange
round trip, proof of HFT suitability, or corroboration of employer timing figures.
Inspect the raw per-batch distributions instead of extrapolating a single p99.
