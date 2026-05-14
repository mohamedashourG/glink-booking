# glink-booking

Booking system built **around** a self-hosted cal.diy instance. cal.diy itself
lives in a sibling directory (`../cal.diy`) — this repo never edits its code.

## Layout

```
glink-booking/
├── packages/
│   ├── shared/                         # cal-client (Python lib)
│   │   └── src/cal_client/
│   │       ├── config.py               # env-driven config (CAL_WEB_BASE)
│   │       ├── models.py               # plain data classes
│   │       └── cal_web.py              # ⚠️ cal.diy web/session internals
│   └── provisioning/                   # CLI built on top of cal-client
│       └── src/provisioning/
│           ├── cli.py
│           ├── provision.py
│           ├── defaults.py
│           └── store.py
└── apps/
    ├── receiver/                       # placeholder: future FastAPI webhook receiver
    └── fallback/                       # placeholder: future Next.js 16 frontend
```

This is a [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/);
`packages/shared` and `packages/provisioning` are members.

## Why two packages

`cal-client` carries everything that knows how to *talk to cal.diy*. The
provisioning CLI and (eventually) the FastAPI receiver both depend on it
— so the cal.diy details live in one place.

Inside `cal-client`, the **`cal_web` module is quarantined**. It uses
cal.diy's web routes (signup, NextAuth login, mounted tRPC procedures)
because in this build of cal.diy, API v2 doesn't expose the operations
we need (user creation, per-user API key bootstrap). Anything that talks
to API v2 should go in a *separate* module — never reach into `cal_web`
from outside the provisioning package.

## Setup

```bash
uv sync                  # creates .venv, installs both packages editable
```

## Provisioning

The provisioning CLI gives one cal.diy login per client, configured with
our standard policy:

- one 30-minute event type
- Mon–Fri 09:00–18:00 in the client's timezone
- 15-min before & after buffers
- 4-hour minimum booking notice
- 60-day rolling booking window
- booking questions: `name`, `email` (required), `Company`, `What would you like to discuss?`

Required env var:

```bash
export CAL_WEB_BASE=http://localhost:3000
```

Single client:

```bash
uv run glink-provision single \
    --name "Acme Inc" --email founder@acme.test --slug acme \
    --tz America/New_York
```

CSV batch (header row required; columns: `full_name, email, slug` — and
optionally `timezone, work_start, work_end`):

```bash
uv run glink-provision batch ./clients.csv
```

Per-client records (including the generated password and the cal.diy IDs
needed for idempotent re-runs) are written to `./.data/<email>.json`,
mode `0600`. The `.data/` directory is gitignored — **treat its contents
as secrets**.

Re-running the same client (same email) is safe: it loads the stored
record, logs back in, and re-applies the schedule + event-type config
without duplicating anything.
