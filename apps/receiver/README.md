# receiver — placeholder

Future home of the FastAPI service that receives cal.diy webhook callbacks
(BOOKING_CREATED, BOOKING_RESCHEDULED, BOOKING_CANCELLED, etc.) and routes
them into the rest of the booking system.

When you build it:

- Add a `pyproject.toml` here that depends on `cal-client` from
  `packages/shared` (already a uv workspace member).
- Reuse `cal_client.config.load_settings()` and `cal_client.models` —
  do **not** import from `cal_client.cal_web` (web/session internals).
- For anything you need to call back into cal.diy with, prefer API v2
  via the user's API key.
