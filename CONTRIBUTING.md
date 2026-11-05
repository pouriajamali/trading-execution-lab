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

Keep each change focused. Explain the behavior before and after it, add a
regression case for a repaired invariant, and update the relevant design decision
when a contract changes. Changes to exchange connectivity, strategy logic or
real-account controls are outside this sample's current scope.
