# glink-booking

Booking system built **around** a self-hosted bookings@glnkco.com instance. bookings@glnkco.com itself
lives in a sibling directory (`../cal.diy`) — this repo never edits its code.

## Layout

```
glink-booking/
├── packages/
│   ├── shared/                         # cal-client (Python lib)
│   │   └── src/cal_client/
│   │       ├── config.py               # env-driven config (CAL_WEB_BASE)
│   │       ├── models.py               # plain data classes
│   │       └── cal_web.py              # ⚠️ bookings@glnkco.com web/session internals
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

`cal-client` carries everything that knows how to *talk to bookings@glnkco.com*. The
provisioning CLI and (eventually) the FastAPI receiver both depend on it
— so the bookings@glnkco.com details live in one place.

Inside `cal-client`, the **`cal_web` module is quarantined**. It uses
bookings@glnkco.com's web routes (signup, NextAuth login, mounted tRPC procedures)
because in this build of bookings@glnkco.com, API v2 doesn't expose the operations
we need (user creation, per-user API key bootstrap). Anything that talks
to API v2 should go in a *separate* module — never reach into `cal_web`
from outside the provisioning package.

## Setup

```bash
uv sync                  # creates .venv, installs both packages editable
```

## Provisioning

The provisioning CLI gives one bookings@glnkco.com login per client, configured with
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

Required env var for everyday provisioning:

```bash
export CAL_WEB_BASE=http://localhost:3000
```

Webhook delivery is set up **once** via the `bootstrap-webhook`
subcommand, which registers a single global bookings@glnkco.com "platform" webhook
that fires for every booking across every client (replaces the
per-client webhook registration we used to do here):

```bash
export RECEIVER_WEBHOOK_URL=http://host.docker.internal:8000/webhook
export CAL_WEBHOOK_SECRET=<same value as apps/receiver/.env>
export CAL_ADMIN_EMAIL=<your bookings@glnkco.com system-admin email>
export CAL_ADMIN_PASSWORD=<that user's password>

uv run glink-provision bootstrap-webhook   # idempotent, run once per instance
```

After that, `single` and `batch` provisioning runs only need
`CAL_WEB_BASE`. Full operator docs live in
[apps/ops/RUNBOOK.md](apps/ops/RUNBOOK.md).

Single client (no fallback URL):

```bash
uv run glink-provision single \
    --name "Acme Inc" --email founder@acme.test --slug acme \
    --tz America/New_York
```

Single client with a fallback Calendly URL (used by the outage-fallback page when bookings@glnkco.com is down):

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

Per-client records (including the generated password and the bookings@glnkco.com IDs
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
