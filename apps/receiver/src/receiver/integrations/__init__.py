"""Best-effort fan-out targets for booking events.

Each module in here:
- reads its own credentials from env vars
- exposes one async function `dispatch(booking, raw_payload, *, pool)` that does its thing
- `is_configured()` returns False when env is missing — fanout skips it cleanly
- never raises across the fan-out boundary; failures are logged and contained
"""
