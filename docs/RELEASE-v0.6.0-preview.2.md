# v0.6.0-preview.2 source: reservation recovery after refresh

When the response to a pending reservation is lost, refreshing the same
operator tab preserves its exact idempotency key, order ID, quantity and
local API process identity. After signing in, **Replay last request** recovers
the receipt explicitly. The panel holds new reservations until it verifies the
receipt, then reads the current exposure separately.

The panel writes this bounded record before sending a request. If storage is
unavailable, a new reservation cannot be sent. A different local API process
fails closed, with an HTTP 412 guard before mutation if a bound request reaches
the API. Bearer tokens, signing keys and operator codes are kept out of the
record. The original API-only client contract without the binding header is
unchanged.

The scope is the same tab and the same running synthetic loopback API. This
does not recover closed tabs, browser data cleared by an operator, or a replaced
process. It introduces no broker connection, production orders or live data.

The earlier `v0.6.0-preview.1` signed packages keep their original behavior.
