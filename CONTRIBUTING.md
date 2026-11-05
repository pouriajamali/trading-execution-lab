# Contributing

Start with the browser demo and the current README. The lab explores order-state,
exposure, admission and durable request-processing contracts. It is not a broker
adapter or an invitation to connect an account.

## Report a reproducible problem

Use an issue with:

- The commit or release, OS and .NET SDK/runtime version.
- The smallest sequence of synthetic events or API requests that shows the problem.
- Expected state/receipt and actual state/receipt.
- Relevant test output, with any tokens and personal data removed.

Do not upload employer code, real account identifiers, credentials, proprietary
strategies or private market data. For incorrect risk or recovery behavior,
describe the broken invariant as well as the visible symptom.

## Run the checks

With the .NET 10 SDK installed, from the repository root:

```sh
dotnet run --project ExecutionLab.Tests/ExecutionLab.Tests.csproj --configuration Release
```

For UI changes, use Node.js 24 and run the following too:

```sh
npm --prefix OperatorPanel ci
npm --prefix OperatorPanel test
npm --prefix OperatorPanel run build
```

For a release candidate, use a clean committed checkout. Python3.12 and
PowerShell7 run the finite package/launcher checks; they are development tools,
not prerequisites for the end-user panel. On the matching x64 OS:

```sh
python scripts/check_launcher.py --work artifacts/launcher
python scripts/package_panel.py --rid win-x64 --commit <full-HEAD> --work artifacts/build --out artifacts/delivery
```

Use `linux-x64` on Ubuntu24.04. Extract the actual generated archive to a fresh
directory, then run `scripts/check_package.py --package <extracted-root>
--commit <full-HEAD> --work <fresh-probe-directory>` with an installed ASP.NET
Core10.0.14+ runtime. Leave `127.0.0.1:5087` free. The runner refuses an occupied
port and owns only its four child processes/disposable test DB.

Existing measurements are historical evidence. The correctness workflow does
not run profiling; do not relabel the retained results as measurements of a new build.

Keep each change focused. Explain the behavior before and after it, add a
regression case for a repaired invariant, and update the relevant design decision
when a contract changes. Changes to exchange connectivity, strategy logic or
real-account controls are outside this sample's current scope.
