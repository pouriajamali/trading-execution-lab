# v0.5.1-preview.1 — audited local operator panel

The local React/.NET panel now marks failed state reads stale and keeps an
unresolved request/key available for exact replay across relogin. A successful
HTTP200 is adopted only after bounded DTO validation; malformed JSON, invalid
shapes, unsafe numbers and inconsistent exposure remain unknown outcomes.
Both the visible button and form handler block a new unsafe request.

Signed JWTs with blank subjects are rejected. Configured Kestrel endpoints are
refused before creating a DB; loopback/Host guards cover API-only mode too.
The launcher propagates child exit, restores environment and removes only its
own generated temporary data on normal/finally exit.

Download the matching **framework-dependent** Windows x64 ZIP or Ubuntu/glibc
x64 tar.gz, verify `SHA256SUMS.txt`, and extract the entire folder. Install
**ASP.NET Core Runtime 10.0.14 or a later 10.0 patch** and **PowerShell 7**.
An SDK, Node.js and Python are unnecessary to run the panel. Start with
`pwsh -NoProfile -File ./Start-OperatorPanel.ps1` (Windows also accepts `.\`).
See the included README or the [quickstart](https://github.com/pouriajamali/trading-execution-lab/blob/v0.5.1-preview.1/docs/QUICKSTART.md).

Initial demo is 7 of 10 lots; reserve 2→9, replay→9, another new 2-lot request is denied.
This release's workflow tests 56 C# cases, 11 protocol cases, launcher contracts
and 22 real HTTP/SQLite checks on extracted packages on each matching OS.
Build manifests identify exact source/tree, runtime requirements, dependency
licenses and every payload hash. Release aggregation reuses executed archives.
The source commit/tag use the existing owner's SSH signing route when available;
the app binaries are unsigned developer previews. A detached checksum signature,
when supplied as a release asset, authenticates checksum bytes, not production fitness.

This is synthetic and loopback-only: no broker, exchange, market/account data,
live submission or real-order controls. All operators share one fictitious gate.
The JavaScript website demo remains a separate implementation. The UI does not
persist tokens/codes; a request key survives relogin only in the same tab, not
reload/closure. Forced process termination can leave temporary files.

Process reopen/exception rollback and inbox deduplication are **not** power-loss
durability, mid-commit crash testing or exactly-once transport. Core/host source,
old releases and historical measured bytes remain intact. No new profiling
dataset was generated; no production/HFT/latency/profit/novelty claim is made.

Independent synthetic material for Pouria Jamali, created with AI assistance.
See the [claim/test/limits case study](https://github.com/pouriajamali/trading-execution-lab/blob/v0.5.1-preview.1/docs/CASE-STUDY.md).
