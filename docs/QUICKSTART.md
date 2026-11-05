# Local operator panel — v0.5.1-preview.1

This is an independent **synthetic, loopback-only** C#/.NET sample. No broker,
exchange, real account, market feed or real-order control is connected.

## Install prerequisites

- Install the matching x64 **ASP.NET Core Runtime 10.0.14 or a later 10.0 patch** from the
  [official .NET downloads](https://dotnet.microsoft.com/en-us/download/dotnet/10.0).
  The plain .NET Runtime alone does not include `Microsoft.AspNetCore.App`.
- Install [PowerShell 7](https://learn.microsoft.com/powershell/scripting/install/installing-powershell).
- Packages are **framework-dependent**, not self-contained. An SDK, Node.js and
  Python are unnecessary to run the panel. Native OS prerequisites still apply.
  Audited targets are Windows x64 and Ubuntu 24.04/glibc x64. Alpine/musl, ARM,
  macOS and other distributions are unverified. The preview is unsigned.

Get the matching archive and `SHA256SUMS.txt` from the
[preview release](https://github.com/pouriajamali/trading-execution-lab/releases/tag/v0.5.1-preview.1).
Check its SHA256 before extracting the **whole folder**, including native SQLite
and `wwwroot` assets. `BUILD-MANIFEST.json` identifies its source commit and files.
Git commit/tag and any detached checksum signatures use SSH provenance signing;
they are distinct from Authenticode. The application binaries remain unsigned.

## Run

From the extracted folder on Windows:

```powershell
pwsh -NoProfile -File .\Start-OperatorPanel.ps1
```

On Ubuntu:

```sh
pwsh -NoProfile -File ./Start-OperatorPanel.ps1
```

Choose a run-only operator code of 16–128 characters at the secure prompt. Open
<http://127.0.0.1:5087/panel/> and enter that code. Keep port 5087 free; a bind
failure is an error, not a successful launch. Configured `Kestrel:Endpoints` are
rejected before database creation. This is not a public deployment recipe.

1. Initial synthetic state: 4 filled + 3 working = 7 of a 10-lot limit.
2. A new order ID and 2 lots produce **Accepted**, exposure 9.
3. **Replay last request** returns the original receipt, exposure stays 9.
4. Another new ID and 2 lots produce **Denied / Exposure limit**, exposure stays 9.

The panel distinguishes a receipt from the last fetched state. It does not poll;
use **Refresh state** to observe later changes. A failed fetch marks values stale
and blocks new requests. After a lost/unreadable response, the receipt is unknown:
replay the exact request before starting a new one. The in-memory request/key
survives sign-out/relogin in the same tab, but **not page reload or tab closure**.
Tokens and operator codes are not put in URLs, browser storage or application logs.
All authorized operators share one fictitious gate; there is no tenant isolation.

Use Ctrl+C to stop. The launcher restores the caller's five application
environment variables, clears its key buffer, removes its own generated temporary
database directory on normal/finally exit, and propagates the backend exit code.
Forced termination, host loss or a cleanup permission failure can leave that
temporary directory; no guaranteed cleanup after process kill is claimed.
Each new launch starts a **fresh** demo; it does not resume the previous demo DB.

## Troubleshooting

- Run `dotnet --list-runtimes`: both `Microsoft.NETCore.App 10.x` and
  `Microsoft.AspNetCore.App 10.x` must be installed for this architecture.
- `dotnet` and `pwsh` must be on PATH. For an explicit runtime host:
  `pwsh -File ./Start-OperatorPanel.ps1 -Dotnet /absolute/path/to/dotnet`.
- Use `127.0.0.1`, not a LAN address or reverse-proxy/public hostname.
- Keep keys/codes/tokens and non-synthetic data out of bug reports.

See [the engineering case study](https://github.com/pouriajamali/trading-execution-lab/blob/v0.5.1-preview.1/docs/CASE-STUDY.md)
for the claim-to-code/test mapping and evidence limits. The separately hosted
JavaScript browser demo is a different implementation, not a .NET runtime test.
