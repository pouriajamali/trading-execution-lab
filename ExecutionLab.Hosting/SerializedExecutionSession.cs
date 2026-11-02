using System.Threading.Channels;

namespace ExecutionLab.Hosting;

// Friend-assembly seam for deterministic scheduler tests; unavailable through the
// public constructor. No hook runs in the public measurement or normal host path.
internal sealed record SessionTestHooks(Func<GateEvent, Task>? BeforeApply = null,
    Action<GateEvent>? AfterAdmission = null);

/// <summary>
/// Synthetic multi-producer host for ONE instrument/direction and ONE local stream.
/// Not a TT/CME adapter. Input.Sequence is deliberately replaced with a local cursor
/// at the single consumer; admission order does not reconstruct external causality.
/// </summary>
public sealed class SerializedExecutionSession : IAsyncDisposable
{
    private sealed record Pending(GateEvent Input, TaskCompletionSource<Decision> Completion);
    private readonly Channel<Pending> queue;
    private readonly long limit;
    private readonly Task worker;
    private readonly SessionTestHooks? hooks;
    private GateState state;

    public SerializedExecutionSession(long exposureLimit, int capacity = 64, GateState? initialState = null)
        : this(exposureLimit, capacity, initialState, null) { }

    internal SerializedExecutionSession(long exposureLimit, int capacity, GateState? initialState, SessionTestHooks? hooks)
    {
        ArgumentOutOfRangeException.ThrowIfNegative(exposureLimit);
        ArgumentOutOfRangeException.ThrowIfNegativeOrZero(capacity);
        limit = exposureLimit;
        state = initialState ?? GateState.Empty;
        this.hooks = hooks;
        queue = Channel.CreateBounded<Pending>(new BoundedChannelOptions(capacity)
        {
            SingleReader = true,
            SingleWriter = false,
            FullMode = BoundedChannelFullMode.Wait,
            AllowSynchronousContinuations = false
        });
        worker = Task.Run(ProcessAsync);
    }

    /// <summary>
    /// Cancellation controls admission only. Once admitted, an event is processed
    /// and its result observed; cancelling the caller never silently drops an event.
    /// Concurrent admission has no fairness or stable cross-producer ordering promise.
    /// </summary>
    public async Task<Decision> SubmitAsync(GateEvent input, CancellationToken admissionCancellation = default)
    {
        ArgumentNullException.ThrowIfNull(input);
        admissionCancellation.ThrowIfCancellationRequested();
        var completion = new TaskCompletionSource<Decision>(TaskCreationOptions.RunContinuationsAsynchronously);
        await queue.Writer.WriteAsync(new Pending(input, completion), admissionCancellation).ConfigureAwait(false);
        hooks?.AfterAdmission?.Invoke(input);
        return await completion.Task.ConfigureAwait(false);
    }

    private async Task ProcessAsync()
    {
        Exception? failure = null;
        try
        {
            await foreach (var pending in queue.Reader.ReadAllAsync().ConfigureAwait(false))
            {
                try
                {
                    if (hooks?.BeforeApply is { } beforeApply)
                        await beforeApply(pending.Input).ConfigureAwait(false);
                    var local = pending.Input with { Sequence = checked(state.Sequence + 1) };
                    var decision = OrderGate.Apply(state, local, limit);
                    // A denial may consume an event or halt the model. Never gate
                    // state adoption on Decision.Accepted.
                    state = decision.State;
                    pending.Completion.TrySetResult(decision);
                }
                catch (Exception error)
                {
                    pending.Completion.TrySetException(error);
                    failure = error;
                    break;
                }
            }
        }
        catch (Exception error)
        {
            failure = error;
        }
        finally
        {
            queue.Writer.TryComplete(failure);
            while (queue.Reader.TryRead(out var pending))
                pending.Completion.TrySetException(failure ?? new ChannelClosedException());
        }
        if (failure is not null)
            throw new InvalidOperationException("Synthetic execution session stopped after a host failure.", failure);
    }

    /// <summary>Closes admission and drains admitted work. No broker action occurs.</summary>
    public async ValueTask DisposeAsync()
    {
        queue.Writer.TryComplete();
        await worker.ConfigureAwait(false);
    }
}
