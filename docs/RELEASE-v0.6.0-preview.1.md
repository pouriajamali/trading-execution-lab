# v0.6.0-preview.1 — .NET11 local operator panel

Six managed projects target net11.0, SDK 11.0.100, C# 15.0 and stable Core/ASP.NET11.0.0,
with patch-only roll-forward and framework-dependent win-x64/linux-x64 packages.
JWT and TestHost use11.0.0; SQLite10.0.14, xUnit4.0.2 and frontend pins are retained.
The original 57 tests remain; two source-authored literal cases additionally cover
persisted receipts, fingerprints, wire shape and the five-table schema.

## Actual local validation

Both Windows and Ubuntu 24.04/ext4/WSL2 independently passed SDK/runtime qualification,
Release Measurements build,59 C# tests (zero failed, skipped or not-run),11 protocol
tests, TypeScript/Vite build and 16 controlled launcher scenarios in both modes.
Controlled launcher scenarios use controlled host output; they are not16 OS installs.
Windows 26H2/build 26300 is an explicitly accepted experimental host; official vendor
support is unconfirmed. A private SDK supplies the observed runtime on each host;
no runtime-only machine installation or browser UI interaction is claimed.

Both platforms completed all14 dependency-factory commands: six graphs, strict
NuGet all/online validation of33 exact original archives, six real two-RID
lock/asset restores and an applicable complete current advisory-snapshot audit.
Linux uses signed existing locks in locked mode. After the previous Windows
advisory snapshot expired, only the applicable audit command was refreshed
against the current complete snapshot; exact admitted graphs, original signature
reports and six unchanged locks/assets were retained without replay. Historical independent-PKI
UNKNOWN fields remain distinct. Official Node 24/PowerShell 7 were materialized
only in the private project; exact locked npm originals were SRI-checked and npm
install/tests/build ran offline. No global installation or trust/security change.

Native delivery requires22 extracted-package HTTP/SQLite checks across four owned
processes for each exact archive, including direct loaded CoreCLR 11.0.0 and packaged
SQLite module observation. The downloadable BUILD-MANIFEST.json binds payload
hashes, source commit/tree, RID, SDK and framework requirements. Public release
metadata records the completed native archive checks and archive hashes.

## Download, provenance and scope

Use the [preview release](https://github.com/pouriajamali/trading-execution-lab/releases/tag/v0.6.0-preview.1)
and [quick start](QUICKSTART.md). Install x64 ASP.NET Core Runtime11.0.0 or a later
11.0 patch and PowerShell 7. Packages are framework-dependent; no SDK/Node/Python is
needed to run them. Extract the entire matching archive.

The release contains matching Windows/Linux packages, exact-commit source ZIP,
SHA256SUMS.txt, its SSH signature and portfolio-signing.pub. Check every checksum
and verify the signature in SSH namespace file against the independently known
key fingerprint SHA256:AgU5bZlJSjUu0KsWMmVEEr+BfXpcMVNroTA33bHcQdU,
principal pouriajamali. SSH provenance is distinct from Authenticode; application
binaries are unsigned. Earlier tags/assets/signatures remain immutable.

GitHub Actions was not run per owner instruction. Actual local native tests,
known-key signatures and direct GitHub preview publication replace that delivery
mechanism without weakening branch protection or validation. Kernel4 GiB/two CPU/
64-task limits, Linux swap0, canonical atomic ownership and actual terminal
teardown remain enforced. Prior failed attempts, sole-owner Ubuntu recovery and
explicit bounded continuation windows remain in private delivery receipts; no
failed attempt is converted into a pass. No performance claim is added.

Independent synthetic loopback-only sample: no exchange, broker, real account,
market feed or live order control. The separately hosted browser demo is unchanged.
