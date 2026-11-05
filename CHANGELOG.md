# Changes

## Unreleased - documentation

- Clarify the source quick start and expected result, and link focused contribution guidance. Runtime behavior, release assets and recorded measurements are unchanged.


## Documentation — 5 November 2026

- Lead with a one-minute browser walkthrough and distinguish its JavaScript model from the downloadable .NET/SQLite operator panel.
- Add the owner's approved MIT license for original public sample material and a contribution guide for synthetic, reproducible reports.
- Application code, tests and existing release archives are unchanged.

## v0.5.0-preview.1 — 4 November 2026

- Optional loopback React/TypeScript operator panel over the existing reservation API.
- Rate-limited local operator sign-in, short-lived JWT, read-only exposure/order status and explicit exact-request replay.
- Windows launcher with a fresh synthetic database. Static assets are built into the .NET publish bundle.
- 43 .NET cases and two UI protocol tests. Browser checks cover login rejection, acceptance, replay and limit denial.

## v0.4.0 — 3 November 2026

- Actual file-backed SQLite state, receipt and audit-outbox atomic commit.
- Content-checked idempotency, persistent limit guard and transactional inbox/counter.
- ASP.NET Core reservation endpoint with JWT validation and operator-role policy.
- Nine integration cases: reopen, historical replay, rollback, competing connections, duplicate-key
  races, redelivery, configuration guard and actual HTTP authentication/authorization.
- Existing 24 core and 9 host cases retained; 42 total. Synthetic control-plane
  code, no broker/cloud deployment or employer/HFT performance claim.

## v0.3.0

Bounded single-writer host, nine hosting cases and reproducible finite measurements.
Existing source release and raw measurements remain available.

## v0.2.0 / v0.1.0

Typed immutable order/risk model and 24 cases; v0.2.0 moved the public target to
.NET10. Older source tags remain unchanged.
