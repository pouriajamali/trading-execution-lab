# Changes

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
