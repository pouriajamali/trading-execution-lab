# Model scope and limits

## Contract

One instrument, one non-negative direction, integer lots and one serialized,
normalized input stream. Caller-supplied normalized facts and snapshots are
trusted inputs. The sequence belongs to this model; it is **not a TT/CME wire
feed sequence**. A real adapter must resolve independent channels, timestamps,
reset boundaries, authoritative snapshots and execution-ID payload consistency.

Immutable state and typed events prioritize inspection, not low allocation or
low latency. Envelope IDs, execution IDs and used order IDs are retained within
the in-memory session without a bounded retention policy. There is no persistence
or crash-recovery guarantee. Stop-on-anomaly is this example's teaching policy,
not a universal policy for trading systems.

## Outside the implementation

- Shorts/netting, pricing, margin and multi-account aggregation.
- Thread safety, durable recovery, durable outbox and bounded ID-store retention.
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

No benchmark, p99 latency, zero-incident record or production-readiness claim is
made. The 24 test cases establish only the tested model's behavior under these
assumptions. The CI badge links to workflow results; it does not establish
production correctness. Independent human review and discussion are welcome.
