# ADR 0001: one owner for execution state

Status: implemented in the independent synthetic host; not employer architecture.

## Constraint

Multiple producers may request state transitions. Each risk decision must observe
the state returned by the preceding consumed transition. Checking exposure and
reserving quantity against independently read snapshots would permit two callers
to reserve the same remaining capacity. `Accepted=false` is not a rollback signal.

## Decision

Use a bounded `System.Threading.Channels` queue with multiple writers, one reader
and `FullMode.Wait`. Only the consumer calls `OrderGate.Apply` and assigns `state`
from every returned decision. Completions run asynchronously. No state accessor
encourages a caller to implement its own check-then-act sequence.

The host assigns the model's next local cursor immediately before application.
The supplied event's `Sequence` is replaced; its original immutable object is not
modified. This orders local consumption only. Resolving independent feeds and
authoritative upstream sequencing belongs to a real adapter, which is absent.

Cancellation can reject admission while waiting for space. After admission, the
event still reaches the consumer and its caller observes the outcome. Disposal
closes admission, drains accepted work and joins the consumer. Unexpected consumer
failure faults the current/buffered requests and closes waiting writers.

## Alternatives

- Direct serialized calls remain simplest when one caller owns the entire stream;
  the measurements retain that reference path.
- A lock around the full state transition is a reasonable alternative for some
  synchronous callers. It was not benchmarked here; no performance claim against
  locks is made.
- Per-producer copies or check-before-enqueue were rejected because the decision
  and state adoption would no longer be one owned operation.
- Dropping queue items was rejected: losing a state transition is not acceptable
  within this sample's lossless admitted-command contract.

## Trade-off and evidence

Queueing, completions and scheduling add overhead to direct application. The
measurement report records that cost, rather than calling asynchronous code
inherently faster. 9 hosting cases include controlled barriers for blocked admission,
cancellation timing and worker failure, alongside concurrent exposure checks.
Capacity bounds buffered entries only; external callers can still create arbitrarily
many waiting tasks. Admission fairness, global memory bounds, persistence and
broker-side effects are outside this host.
