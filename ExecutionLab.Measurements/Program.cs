using System.Diagnostics;
using System.Globalization;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using ExecutionLab;
using ExecutionLab.Hosting;

const int pairsPerBatch = 1000, measuredBatches = 5, capacity = 64;
string output = args.Length == 2 && args[0] == "--output" ? args[1] : "artifacts/measurement";
Directory.CreateDirectory(output);
var rows = new List<object>();
var raw = new StringBuilder("scenario,batch,event_index,stopwatch_ticks\n");
double micros(long ticks) => ticks * 1_000_000d / Stopwatch.Frequency;
long quantile(long[] sorted, double p) => sorted[Math.Clamp((int)Math.Ceiling(p * sorted.Length) - 1, 0, sorted.Length - 1)];
object distribution(long[] ticks)
{
    var sorted = ticks.Order().ToArray();
    return new { samples = sorted.Length, p50_microseconds = micros(quantile(sorted, .50)),
        p95_microseconds = micros(quantile(sorted, .95)), p99_microseconds = micros(quantile(sorted, .99)),
        min_microseconds = micros(sorted[0]), max_microseconds = micros(sorted[^1]) };
}
GateEvent input(int producer, int pair, bool fill) => fill
    ? new Fill($"f-{producer}-{pair}", 0, $"o-{producer}-{pair}", $"x-{producer}-{pair}", 1)
    : new Reserve($"r-{producer}-{pair}", 0, $"o-{producer}-{pair}", 1);

async Task<(long[] Ticks, long Allocated, int[] Collections, long Elapsed)> run(bool hosted, int producers, int pairs)
{
    var timings = new long[pairs * 2];
    var initial = OrderGate.Apply(GateState.Empty, new Snapshot("snapshot", 1, 0, []), pairs).State;
    initial = OrderGate.Apply(initial, new Resume("resume", 2), pairs).State;
    var startCollections = Enumerable.Range(0, 3).Select(GC.CollectionCount).ToArray();
    long allocationStart = GC.GetTotalAllocatedBytes(precise: true);
    long start = Stopwatch.GetTimestamp();
    GateState final = initial;
    if (!hosted)
    {
        for (int pair = 0; pair < pairs; pair++)
        {
            foreach (bool fill in new[] { false, true })
            {
                var evt = input(0, pair, fill) with { Sequence = final.Sequence + 1 };
                long before = Stopwatch.GetTimestamp();
                var decision = OrderGate.Apply(final, evt, pairs);
                timings[pair * 2 + (fill ? 1 : 0)] = Stopwatch.GetTimestamp() - before;
                if (!decision.Accepted) throw new InvalidOperationException(decision.Reason);
                final = decision.State;
            }
        }
    }
    else
    {
        await using var session = new SerializedExecutionSession(pairs, capacity, initial);
        var lastStates = await Task.WhenAll(Enumerable.Range(0, producers).Select(producer => Task.Run(async () =>
        {
            GateState latest = initial;
            for (int pair = producer; pair < pairs; pair += producers)
            {
                foreach (bool fill in new[] { false, true })
                {
                    var evt = input(producer, pair, fill);
                    long before = Stopwatch.GetTimestamp();
                    var decision = await session.SubmitAsync(evt);
                    timings[pair * 2 + (fill ? 1 : 0)] = Stopwatch.GetTimestamp() - before;
                    if (!decision.Accepted) throw new InvalidOperationException(decision.Reason);
                    latest = decision.State;
                }
            }
            return latest;
        })));
        final = lastStates.MaxBy(s => s.Sequence)!;
    }
    long elapsed = Stopwatch.GetTimestamp() - start;
    long allocated = GC.GetTotalAllocatedBytes(precise: true) - allocationStart;
    var collections = Enumerable.Range(0, 3).Select(i => GC.CollectionCount(i) - startCollections[i]).ToArray();
    if (final.Position != pairs || final.Pending != 0 || final.Sequence != pairs * 2 + 2 || timings.Any(t => t < 0))
        throw new InvalidOperationException("Measurement workload failed its final-state contract.");
    return (timings, allocated, collections, elapsed);
}

var clock = new long[1000];
for (int i = 0; i < clock.Length; i++) { long before = Stopwatch.GetTimestamp(); clock[i] = Stopwatch.GetTimestamp() - before; }
foreach (var scenario in new[] { (Name: "direct-core", Host: false, Producers: 1),
    (Name: "channel-1-producer", Host: true, Producers: 1), (Name: "channel-4-producers", Host: true, Producers: 4) })
{
    for (int warmup = 0; warmup < 2; warmup++) await run(scenario.Host, scenario.Producers, 200);
    for (int batch = 0; batch < measuredBatches; batch++)
    {
        var result = await run(scenario.Host, scenario.Producers, pairsPerBatch);
        rows.Add(new { scenario = scenario.Name, batch, producers = scenario.Producers,
            pairs = pairsPerBatch, events = result.Ticks.Length, event_duration = distribution(result.Ticks),
            process_allocated_bytes = result.Allocated, generation_collections = result.Collections,
            batch_elapsed_microseconds = micros(result.Elapsed),
            verified_final_position = pairsPerBatch, verified_final_pending = 0 });
        for (int i = 0; i < result.Ticks.Length; i++)
            raw.Append(CultureInfo.InvariantCulture, $"{scenario.Name},{batch},{i},{result.Ticks[i]}\n");
    }
}
var sources = new[] { "ExecutionLab/OrderGate.cs", "ExecutionLab.Hosting/SerializedExecutionSession.cs",
    "ExecutionLab.Measurements/Program.cs", "ExecutionLab.Tests/HostingTests.cs" };
var report = new {
    recorded_at_utc = DateTimeOffset.UtcNow, runtime = RuntimeInformation.FrameworkDescription,
    os = RuntimeInformation.OSDescription, architecture = RuntimeInformation.ProcessArchitecture.ToString(),
    logical_processors = Environment.ProcessorCount, server_gc = System.Runtime.GCSettings.IsServerGC,
    environment_kind = Environment.GetEnvironmentVariable("GITHUB_ACTIONS") == "true" ? "shared-ci" : "local",
    clock_frequency = Stopwatch.Frequency, clock_is_high_resolution = Stopwatch.IsHighResolution,
    clock_probe = distribution(clock), warmup_runs_per_scenario = 2, measured_batches = measuredBatches,
    queue_capacity = capacity, percentile_method = "nearest rank; each batch separately; no clock subtraction",
    scope = "Synthetic one-instrument long-only Reserve/Fill pairs. Direct event timings cover Apply only; channel timings cover SubmitAsync through observed result, including admission/wait/scheduling. Event construction excluded from event timing. Process allocation covers the batch after baseline state/timing-buffer initialization, including event construction, tasks, host and bookkeeping; it is not hot-path allocation. ID stores grow across this finite session. No transport, SDK, market data, venue latency or production performance claim.",
    source_sha256 = sources.ToDictionary(path => path, path => Convert.ToHexStringLower(SHA256.HashData(File.ReadAllBytes(path)))),
    batches = rows
};
await File.WriteAllTextAsync(Path.Combine(output, "report.json"), JsonSerializer.Serialize(report, new JsonSerializerOptions { WriteIndented = true }) + "\n");
await File.WriteAllTextAsync(Path.Combine(output, "events.csv"), raw.ToString());
Console.WriteLine($"Measured 3 scenarios x {measuredBatches} batches x {pairsPerBatch * 2} events; all final-state checks passed. Output: {output}");
