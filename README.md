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
- a per-user webhook subscription pointing at the receiver, covering
  `BOOKING_CREATED` / `RESCHEDULED` / `CANCELLED` / `REJECTED` (so every
  booking on a provisioned client lands in the receiver's Postgres
  automatically)

Required env vars:

```bash
export CAL_WEB_BASE=http://localhost:3000
# Webhook wiring — both required:
export RECEIVER_WEBHOOK_URL=http://host.docker.internal:8000/webhook
export CAL_WEBHOOK_SECRET=<same value as apps/receiver/.env CAL_WEBHOOK_SECRET>
```

`CAL_WEBHOOK_SECRET` here MUST be the same value the receiver was
started with. They sign and verify the same envelopes.

Single client (no fallback URL):

```bash
uv run glink-provision single \
    --name "Acme Inc" --email founder@acme.test --slug acme \
    --tz America/New_York
```

Single client with a fallback Calendly URL (used by the outage-fallback page when cal.diy is down):

```bash
uv run glink-provision single \
    --name "Acme Inc" --email founder@acme.test --slug acme \
    --tz America/New_York \
    --calendly-url https://calendly.com/acme-inc/30min
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

### clients.json manifest

After every provisioning run the CLI also (re)writes a flat manifest at
`./.data/clients.json` containing only the publicly-shareable subset:

```json
[ { "slug": "...", "full_name": "...", "email": "...", "calendly_url": "..." | null } ]
```

This is the static source of truth the **outage-fallback** Next.js app
([apps/fallback/](apps/fallback/)) reads at build time to generate one
static page per client. The manifest carries no secrets, but lives under
`.data/` (gitignored) by convention — regenerate it with any provisioning
run.
