# Model scope and limits

## Contract

One instrument, one non-negative direction, integer lots and one serialized,
normalized input stream. Caller-supplied normalized facts and snapshots are
trusted inputs. The sequence belongs to this model; it is **not a TT/CME wire
feed sequence**. A real adapter must resolve independent channels, timestamps,
reset boundaries, authoritative snapshots and execution-ID payload consistency.

Immutable state and typed events prioritize inspection. Envelope IDs, execution IDs and used order IDs are retained within
the in-memory session without a bounded retention policy. There is no persistence
or crash-recovery guarantee. Stop-on-anomaly is this example's teaching policy,
not a universal policy for trading systems.

## Outside the implementation

- Shorts/netting, pricing, margin and multi-account aggregation.
- Synchronization of callers using the core directly, durable recovery, durable
  outbox and bounded ID-store retention.
- Broker rejection/replacement races, exchange packet decoding and real adapters.
- External order cancellation or position close-out. Disconnect/stop does not
  imply either action occurred; real actions require confirmed external responses.
- Exchange certification/conformance, including CME conformance.

## Evidence boundary

The repository is not a TT adapter, a reconstruction of a private project or
evidence of historical production incidents/performance. It contains no SDK
integration, credentials, real account/market data, network calls or order
submission. The .NET 10 target and NuGet test dependency describe this public
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
readiness claim. The24 core + 9 hosting tests establish the tested behavior under
these assumptions. CI results remain separate from production correctness.
