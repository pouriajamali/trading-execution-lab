using System.Collections.Immutable;
using System.Threading.Channels;
using ExecutionLab;
using ExecutionLab.Hosting;
using Xunit;

public sealed class HostingTests
{
    private static TaskCompletionSource Signal() => new(TaskCreationOptions.RunContinuationsAsynchronously);
    private static Task Bounded(Task task) => task.WaitAsync(TimeSpan.FromSeconds(10), TestContext.Current.CancellationToken);
    private static Task<Decision> Send(SerializedExecutionSession session, GateEvent input) =>
        session.SubmitAsync(input, TestContext.Current.CancellationToken);
    private static async Task Ready(SerializedExecutionSession session)
    {
        Assert.True((await Send(session, new Snapshot("snapshot", 0, 0, []))).Accepted);
        Assert.True((await Send(session, new Resume("resume", 999))).Accepted);
    }

    [Fact]
    public async Task ConcurrentReservationsCannotOversubscribe()
    {
        await using var session = new SerializedExecutionSession(10, capacity: 1);
        await Ready(session);
        var results = await Task.WhenAll(Enumerable.Range(0, 100).Select(i =>
            Task.Run(() => Send(session, new Reserve($"event-{i}", 0, $"order-{i}", 1)), TestContext.Current.CancellationToken)));
        Assert.Equal(10, results.Count(r => r.Accepted));
        Assert.All(results, r => Assert.InRange(r.State.ReservedExposure, 0, 10));
        Assert.Equal(Enumerable.Range(3, 100).Select(n => (long)n), results.Select(r => r.State.Sequence).Order());
        var final = results.MaxBy(r => r.State.Sequence)!.State;
        Assert.Equal(10, final.ReservedExposure);
        Assert.Equal(102, final.SeenEvents.Count);
    }

    [Fact]
    public async Task DenialIsConsumedBeforeNextCancellation()
    {
        await using var session = new SerializedExecutionSession(10);
        var snapshot = new Snapshot("snapshot", 77, 6, [new SnapshotOrder("a", 4)]);
        await Send(session, snapshot);
        await Send(session, new Resume("resume", 99));
        var denied = await Send(session, new Reserve("denied", 900, "b", 1));
        Assert.False(denied.Accepted);
        Assert.Equal(3, denied.State.Sequence);
        var cancelled = await Send(session, new RequestCancel("cancel", 901, "a"));
        Assert.True(cancelled.Accepted);
        Assert.True(cancelled.State.Reconciled);
        Assert.True(cancelled.State.Orders["a"].CancelRequested);
        Assert.Equal(4, cancelled.State.Sequence);
        Assert.Equal(77, snapshot.Sequence); // caller's immutable input is untouched
    }

    [Fact]
    public async Task DuplicateEnvelopeDoesNotConsumeLocalSequence()
    {
        await using var session = new SerializedExecutionSession(10);
        await Ready(session);
        var input = new Reserve("same-event", 0, "a", 1);
        var first = await Send(session, input);
        var duplicate = await Send(session, input);
        Assert.False(duplicate.Accepted);
        Assert.Same(first.State, duplicate.State);
        var next = await Send(session, new Reserve("next", 0, "b", 1));
        Assert.Equal(4, next.State.Sequence);
        Assert.Equal(2, next.State.ReservedExposure);
    }

    [Fact]
    public async Task CancelledAdmissionDoesNotConsumeState()
    {
        await using var session = new SerializedExecutionSession(10);
        await Ready(session);
        using var cancellation = new CancellationTokenSource();
        cancellation.Cancel();
        await Assert.ThrowsAnyAsync<OperationCanceledException>(() =>
            session.SubmitAsync(new Reserve("cancelled", 0, "a", 1), cancellation.Token));
        var result = await Send(session, new Reserve("valid", 0, "b", 1));
        Assert.Equal(3, result.State.Sequence);
        Assert.Equal(1, result.State.Pending);
    }

    [Fact]
    public async Task DisposalDrainsAdmittedWorkAndRejectsNewAdmission()
    {
        var session = new SerializedExecutionSession(100, capacity: 100);
        await Ready(session);
        // Capacity admits these writes before Dispose closes the writer.
        var pending = Enumerable.Range(0, 50).Select(i =>
            Send(session, new Reserve($"e{i}", 0, $"o{i}", 1))).ToArray();
        await session.DisposeAsync();
        var results = await Task.WhenAll(pending);
        Assert.All(results, r => Assert.True(r.Accepted));
        await Assert.ThrowsAsync<ChannelClosedException>(() =>
            Send(session, new Reserve("late", 0, "late", 1)));
        await session.DisposeAsync();
    }

    [Fact]
    public async Task HostCursorOverflowFailsClosedInsteadOfLeavingCallerPending()
    {
        var initial = GateState.Empty with { Sequence = long.MaxValue };
        var session = new SerializedExecutionSession(10, initialState: initial);
        await Assert.ThrowsAsync<OverflowException>(() =>
            Send(session, new Stop("stop", 0)).WaitAsync(TimeSpan.FromSeconds(5), TestContext.Current.CancellationToken));
        var error = await Assert.ThrowsAsync<InvalidOperationException>(() => session.DisposeAsync().AsTask());
        Assert.IsType<OverflowException>(error.InnerException);
        await Assert.ThrowsAsync<ChannelClosedException>(() => Send(session, new Stop("late", 0)));
    }

    [Fact]
    public async Task FullBufferBlocksAdmissionAndCancellationDoesNotConsumeCursor()
    {
        var entered = Signal(); var release = Signal(); var secondAdmitted = Signal();
        var hooks = new SessionTestHooks(async e =>
        {
            if (e.EventId == "hold") { entered.TrySetResult(); await release.Task; }
        }, e => { if (e.EventId == "buffered") secondAdmitted.TrySetResult(); });
        await using var session = new SerializedExecutionSession(10, 1, null, hooks);
        await Ready(session);
        var first = Send(session, new Reserve("hold", 0, "a", 1));
        Task<Decision>? second = null;
        try
        {
            await Bounded(entered.Task);
            second = Send(session, new Reserve("buffered", 0, "b", 1));
            await Bounded(secondAdmitted.Task);
            using var cancelled = new CancellationTokenSource();
            var blocked = session.SubmitAsync(new Reserve("not-admitted", 0, "c", 1), cancelled.Token);
            Assert.False(blocked.IsCompleted); // consumer is explicitly held and capacity1 is full
            cancelled.Cancel();
            await Assert.ThrowsAnyAsync<OperationCanceledException>(() => Bounded(blocked));
        }
        finally { release.TrySetResult(); }
        Assert.True((await first).Accepted);
        Assert.True((await second!).Accepted);
        var next = await Send(session, new Reserve("next", 0, "d", 1));
        Assert.Equal(5, next.State.Sequence);
        Assert.Equal(3, next.State.Pending);
        Assert.DoesNotContain("not-admitted", next.State.SeenEvents);
    }

    [Fact]
    public async Task CancellingAfterAdmissionStillReturnsTheAppliedResult()
    {
        var admitted = Signal(); var entered = Signal(); var release = Signal();
        var hooks = new SessionTestHooks(async e =>
        {
            if (e.EventId == "hold") { entered.TrySetResult(); await release.Task; }
        }, e => { if (e.EventId == "hold") admitted.TrySetResult(); });
        await using var session = new SerializedExecutionSession(10, 1, null, hooks);
        await Ready(session);
        using var cancelled = new CancellationTokenSource();
        var pending = session.SubmitAsync(new Reserve("hold", 0, "a", 1), cancelled.Token);
        try
        {
            await Bounded(admitted.Task); await Bounded(entered.Task);
            cancelled.Cancel();
            Assert.False(pending.IsCompleted);
        }
        finally { release.TrySetResult(); }
        var result = await pending;
        Assert.True(result.Accepted);
        Assert.Equal(1, result.State.Pending);
    }

    [Fact]
    public async Task WorkerFailureSettlesCurrentBufferedAndWaitingSubmissions()
    {
        var entered = Signal(); var release = Signal(); var buffered = Signal();
        var hooks = new SessionTestHooks(async e =>
        {
            if (e.EventId == "fail")
            {
                entered.TrySetResult(); await release.Task;
                throw new InvalidOperationException("Injected test failure");
            }
        }, e => { if (e.EventId == "buffered") buffered.TrySetResult(); });
        var session = new SerializedExecutionSession(10, 1, null, hooks);
        await Ready(session);
        var current = Send(session, new Stop("fail", 0));
        Task<Decision>? queued = null, waiting = null;
        try
        {
            await Bounded(entered.Task);
            queued = Send(session, new Stop("buffered", 0));
            await Bounded(buffered.Task);
            waiting = Send(session, new Stop("waiting", 0));
            Assert.False(waiting.IsCompleted);
        }
        finally { release.TrySetResult(); }
        await Assert.ThrowsAsync<InvalidOperationException>(() => Bounded(current));
        await Assert.ThrowsAsync<InvalidOperationException>(() => Bounded(queued!));
        await Assert.ThrowsAsync<ChannelClosedException>(() => Bounded(waiting!));
        await Assert.ThrowsAsync<InvalidOperationException>(() => session.DisposeAsync().AsTask());
    }
}
