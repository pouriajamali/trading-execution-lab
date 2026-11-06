# v0.5.2-preview.1 — launcher runtime preflight

The local launcher now checks its selected `dotnet` host before requesting an
operator code, generating a key or creating a temporary database directory.
It requires x64 and stable Microsoft.AspNetCore.App / Microsoft.NETCore.App
10.0.14 or a later 10.0 patch. Missing/insufficient frameworks, another host
architecture or failed inspection produce an actionable prerequisite error.
Explicit `-Dotnet` paths, including spaces, remain supported. CLI output language
is set only during inspection and the caller's value is restored.

The runtime prerequisites were already documented; this release improves the
failure sequence. It does not install a runtime or change PATH/security settings.
The package remains framework-dependent, synthetic and loopback-only.

`python scripts/check_launcher.py --work <fresh-directory>` checks 16 controlled
host cases in harness and standalone-input-stub modes, including patch/architecture
rejections, compatible patches, child exit 17, environment restoration and owned
cleanup. `--launcher <extracted-path>/Start-OperatorPanel.ps1` checks a downloaded
launcher using the same controlled host. These probes are not an interactive
console or real-runtime compatibility proof. The existing Windows/Linux pipeline
also executes each actual packaged .NET API against HTTP/SQLite before release.

No order-risk, idempotency, transaction, authentication or browser protocol
behavior changed. The 56 C# and 11 protocol cases remain the same. No new benchmark,
latency claim or independent novice study is included. Earlier browser-tool limits
are not replaced by a claim of fresh rendered-UI verification.

Windows x64 and Ubuntu 24.04/glibc x64 archives plus exact-commit source are
published through the existing preview pipeline. Binaries remain unsigned;
Git/SSH provenance is separate from Authenticode. Earlier release assets and
recorded measurements remain historical and unchanged.
