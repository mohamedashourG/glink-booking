# Operator runbook

Operational knowledge for the people running the booking system.
Audience is engineering / ops, not clients.

## Component map

| Piece | Path | Port | Purpose |
|---|---|---|---|
| bookings@glnkco.com | `cal.diy/` (vendored) | 3000 | The booking app. Self-hosted. |
| receiver | `apps/receiver/` | 8000 | FastAPI; receives bookings@glnkco.com webhooks, persists, fans out |
| provisioning | `packages/provisioning` | (CLI) | Creates clients in bookings@glnkco.com + writes the manifest |
| fallback | `apps/fallback/` | (static) | Outage page; built ahead of time, served when bookings@glnkco.com is down |
| admin-api | `apps/admin-api/` | 8002 | FastAPI; thin HTTP wrapper around `provisioning` for the agency UI |
| admin-ui | `apps/admin-ui/` | 3001 | Next.js; the agency director's no-terminal control panel |

## Deploying to Fly.io

bookings@glnkco.com itself is already at `https://glnk-booking.fly.dev` (config in
`../cal.diy/fly.toml`). The four glink-booking services deploy as four
separate Fly apps in the same org, region `iad`.

| Fly app | Code | URL |
|---|---|---|
| `glnk-receiver` | `apps/receiver` | https://glnk-receiver.fly.dev |
| `glnk-admin-api` | `apps/admin-api` | https://glnk-admin-api.fly.dev |
| `glnk-admin-ui` | `apps/admin-ui` | https://glnk-admin-ui.fly.dev |
| `glnk-fallback` | `apps/fallback` | https://glnk-fallback.fly.dev |
| `glnk-receiver-db` | Fly Postgres | (attached to glnk-receiver) |

### First-time setup (run once per environment)

```bash
# 0. Sanity: fly CLI logged in
fly auth whoami

# 1. Create the four apps (idempotent — re-running errors but does no harm)
fly apps create glnk-receiver
fly apps create glnk-admin-api
fly apps create glnk-admin-ui
fly apps create glnk-fallback

# 2. Postgres for the receiver
fly postgres create \
  --name glnk-receiver-db \
  --region iad \
  --vm-size shared-cpu-1x \
  --volume-size 1 \
  --initial-cluster-size 1
fly postgres attach glnk-receiver-db --app glnk-receiver
# ^ writes DATABASE_URL into glnk-receiver's secrets.

# 3. Persistent volume for admin-api (.data/ survives deploys)
fly volumes create admin_data --app glnk-admin-api --region iad --size 1 --yes

# 4. Secrets
fly secrets set CAL_WEBHOOK_SECRET="$(openssl rand -hex 32)" --app glnk-receiver
fly secrets set ADMIN_SESSION_SECRET="$(openssl rand -hex 32)" --app glnk-admin-api
# Optional fan-out integrations on receiver (omit any you don't want):
# fly secrets set SLACK_WEBHOOK_URL="..." HUBSPOT_TOKEN="..." \
#                 RESEND_API_KEY="..." RESEND_FROM_EMAIL="..." \
#                 AGENCY_NOTIFY_EMAIL="..." --app glnk-receiver

# 5. Initial deploy
bin/deploy-fly.sh        # builds + deploys all four

# 6. Seed admin-api's volume with current .data/ (per-client records)
#    Skip if you're starting clean.
#    NOTE the COPYFILE_DISABLE=1 — without it, macOS tar emits `._foo.json`
#    AppleDouble sidecars that match `*.json` globs on Linux and crash
#    write_manifest. The deploy script exports this already; included here
#    for the manual path.
COPYFILE_DISABLE=1 tar czf /tmp/data.tgz -C . .data
fly ssh sftp put /tmp/data.tgz /app/data.tgz --app glnk-admin-api
fly ssh console --app glnk-admin-api \
  -C "sh -c 'cd /app && tar xzf data.tgz && rm data.tgz && ls .data | head'"

# 7. Re-register the platform webhook so it points at the deployed receiver.
#    The old webhook (host.docker.internal:8000) doesn't work anymore.
docker exec -i database psql -U unicorn_user -d calendso \
  -c "DELETE FROM \"Webhook\" WHERE platform = true;"   # if it exists
rm -f .data/platform_webhook.json
export CAL_WEB_BASE=https://glnk-booking.fly.dev
export RECEIVER_WEBHOOK_URL=https://glnk-receiver.fly.dev/webhook
export CAL_WEBHOOK_SECRET="<value you used in step 4>"
export CAL_ADMIN_EMAIL=<your bookings@glnkco.com admin email>
export CAL_ADMIN_PASSWORD=<that user's password>
uv run glink-provision bootstrap-webhook
```

> **Step 7 caveat** — that `docker exec` command targets a *local* cal.diy
> database. The deployed cal.diy on Fly has its own database — talk to it
> via `fly postgres connect --app <cal.diy-db-app>` and run the same DELETE.

### Ongoing deploys

```bash
bin/deploy-fly.sh                    # all four
bin/deploy-fly.sh admin-ui           # just one
bin/deploy-fly.sh receiver admin-api # subset
```

The script handles each service's build-context quirks:
- `receiver`, `admin-ui` build from their own dirs.
- `admin-api` builds from monorepo root (Dockerfile pulls in `packages/*`).
- `fallback` runs `npm run build` locally first (the build reads
  `.data/clients.json`, which is gitignored AND `.dockerignore`d for safety),
  then ships the prebuilt `out/` into an nginx image.

### When `.data/` changes (new client provisioned)

Two paths write to `.data/`:
1. **Local CLI** (`uv run glink-provision single ...`) — writes to your
   laptop's `.data/`. To get those records onto the deployed admin-api,
   either re-run step 6 above, or re-do the provisioning from the admin-ui
   (it writes straight to the volume).
2. **admin-ui** (web form / CSV upload) — writes directly to the Fly
   volume. No sync needed.

After **any** provisioning that changes the client roster, redeploy the
fallback so its prerendered pages match: `bin/deploy-fly.sh fallback`.

### Cost note

Roughly **$15–20/month** on top of cal.diy's existing spend (4 small
machines, one tiny Postgres, one 1 GB volume). admin-ui and fallback
auto-suspend when idle.

### Optional: live data sources for admin-api

admin-api can augment its responses with two **read-only** Postgres
lookups. Both are optional — admin-api degrades gracefully when either
env var is unset (the dashboard still works against the manifest, just
without live usernames or booking counts).

| Env var on `glnk-admin-api` | DB it reads | What it powers |
|---|---|---|
| `CAL_DB_URL` | `glnk-booking-db.glnk_booking` | live `users.username` lookups (drift detection on the dashboard, live `/slug-available` check on the new-client form) |
| `RECEIVER_DB_URL` | `glnk-receiver-db.glnk_receiver` | per-client booking counts, status breakdown, recent-meetings list on detail pages |

**Connection string format** (Fly internal — uses the flycast private IP):

```
postgres://<user>:<password>@<cluster>.flycast:5432/<db>?sslmode=disable
```

The flycast hostname is reachable from any app in the same Fly org —
no proxy needed.

**Two ways to provide credentials** (pick one):

**A. Reuse the existing app DB users (simplest).** Each Fly Postgres
attach creates an app-scoped user with full access to its database.
admin-api will only issue SELECTs, but the credential itself is
write-capable.

```bash
# Pull the DATABASE_URL secret value from each app, set as a NEW secret on admin-api.
# Fly does not expose secret values, so this requires fly ssh into each app:

fly ssh console --app glnk-booking -C 'printenv DATABASE_URL'  # then copy
fly secrets set CAL_DB_URL="<paste>" --app glnk-admin-api

fly ssh console --app glnk-receiver -C 'printenv DATABASE_URL'
fly secrets set RECEIVER_DB_URL="<paste>" --app glnk-admin-api
```

**B. Create dedicated read-only roles (best practice).** Limits blast
radius if the admin-api credential ever leaks.

```bash
# cal.diy DB
fly ssh console --app glnk-booking-db -C \
  'psql -U postgres -p 5433 -h /run/postgresql -d glnk_booking -c "
    CREATE USER glnk_admin_ro WITH PASSWORD '\''<random>'\'';
    GRANT CONNECT ON DATABASE glnk_booking TO glnk_admin_ro;
    GRANT USAGE ON SCHEMA public TO glnk_admin_ro;
    GRANT SELECT ON ALL TABLES IN SCHEMA public TO glnk_admin_ro;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO glnk_admin_ro;
  "'
fly secrets set \
  CAL_DB_URL="postgres://glnk_admin_ro:<random>@glnk-booking-db.flycast:5432/glnk_booking?sslmode=disable" \
  --app glnk-admin-api

# receiver DB — same pattern with the glnk_receiver database.
```

After setting either set of secrets, `fly deploy --config apps/admin-api/fly.toml .`
to roll the machine. The startup log line will end with
`cal_db=on receiver_db=on` when both pools opened cleanly.

## Pre-meeting reminders

Receiver schedules + sends reminder emails before each booking. One row in
`reminder_jobs` per (offset × recipient); a polling worker in the
receiver process claims due rows with `FOR UPDATE SKIP LOCKED` and sends
via the same Resend account fan-out already uses.

### Env vars (receiver)

| Var | Default | Effect |
|---|---|---|
| `REMINDER_OFFSETS_MIN` | `60` | CSV minutes-before-meeting. `1440,60,15` = 1 day + 1 hour + 15 min reminders. Empty disables global default. |
| `REMINDER_RECIPIENTS` | `prospect,host,agency` | Subset of {prospect,host,agency}. Empty disables global default. |
| `REMINDER_TICK_SECONDS` | `30` | Worker poll interval. Floor of 5s. |

`RESEND_API_KEY` / `RESEND_FROM_EMAIL` are shared with the existing email
fan-out — no new key. `AGENCY_NOTIFY_EMAIL` doubles as the agency
reminder recipient.

### Per-client overrides

The admin-ui detail page has a Reminders card. Saving there writes to
`client_reminder_config` (receiver-DB) — admin-api needs the same
`RECEIVER_DB_URL` it already has for live booking counts, but with INSERT/
UPDATE permission on this table. If you used the recommended read-only
role from the "Optional: live data sources" section, grant it the extra
permission:

```sql
GRANT INSERT, UPDATE ON client_reminder_config TO glnk_admin_ro;
```

(Re-using the existing app DB user, no action needed — it already has
full access.)

Newly-provisioned clients get a seeded default config: `offsets_min=[60]`,
`recipients=[prospect,host,agency]`. Visible immediately in admin-ui.

### Behavior nuances worth knowing

- **Existing pending rows are not retroactively rewritten** when the
  config changes. Already-scheduled reminders fire on their original
  schedule; only *new* bookings see the new config.
- **Reschedules** cancel pending rows under the old uid and create fresh
  rows under the new uid. Past-the-window offsets (e.g. 1 hour notice on
  a meeting now 30 min away) are silently dropped.
- **Cancels / rejects** flip all pending rows for the uid to `cancelled`.
  Sent/failed rows are untouched (history).
- **Concurrent workers**: production receiver runs 2 machines for HA;
  both poll. `FOR UPDATE SKIP LOCKED` ensures each row is sent once.
- **Worker crash mid-send**: rows stuck in `processing` for >5 min are
  reverted to `pending` on the next tick. Mid-send durability is
  Resend's responsibility — we may double-send in the rarest case where
  Resend accepted the call but we lost the connection before marking
  sent. Logged as `transient failure`.

### Disabling

Per-client: edit the Reminders card, save with empty offsets OR empty
recipients. Either alone disables for that client.

Globally: `fly secrets unset REMINDER_OFFSETS_MIN --app glnk-receiver`
(or set to empty string). Existing per-client overrides still apply.

To fully kill the feature: drop the receiver tables (`reminder_jobs`,
`client_reminder_config`). The bookings table's `host_email` column is
harmless to keep around.

### Troubleshooting

```bash
# Are jobs being scheduled? Should see numbers next to 'pending' after a booking.
fly ssh console --app glnk-receiver-db -C \
  'psql -U postgres -p 5433 -h /run/postgresql -d glnk_receiver \
   -c "SELECT status, COUNT(*) FROM reminder_jobs GROUP BY status;"'

# Tail worker activity (sent / failed / retried)
fly logs --app glnk-receiver | grep -E "reminder"

# A specific booking's reminder rows
fly ssh console --app glnk-receiver-db -C \
  'psql -U postgres -p 5433 -h /run/postgresql -d glnk_receiver \
   -c "SELECT * FROM reminder_jobs WHERE cal_booking_uid=$$<uid>$$;"'
```

A "no scheduled_at" log line means the webhook payload didn't carry a
meeting time — scheduling is skipped for that row. Inspect
`raw_payload_json` to see why; cal.diy may have changed its envelope
shape in an upgrade.

## One-time bootstrap

After standing up bookings@glnkco.com + the receiver, run this **once** per bookings@glnkco.com
instance to register the single global webhook that pipes every booking
into the receiver:

```bash
export CAL_WEB_BASE=http://localhost:3000
export RECEIVER_WEBHOOK_URL=http://host.docker.internal:8000/webhook
export CAL_WEBHOOK_SECRET=<same value as apps/receiver/.env>
export CAL_ADMIN_EMAIL=<your bookings@glnkco.com system-admin email>
export CAL_ADMIN_PASSWORD=<that user's password>

uv run glink-provision bootstrap-webhook
# ✓ created (or 'already exists'): platform webhook <id>
```

The platform webhook fires for **every** booking trigger across **every**
client — `WebhookRepository.getSubscribersRaw` puts platform webhooks in
the priority-1 union branch with no scope filter. So provisioning new
clients does NOT register a per-client webhook anymore; the platform
webhook covers them.

Idempotent. Safe to re-run. Won't create duplicates.

> **How idempotency works** — bookings@glnkco.com's `webhook.list` route returns `[]`
> for admins even when platform webhooks exist (verified live), so the
> usual "list, match by URL, skip" pattern doesn't work here. The
> bootstrap CLI instead writes a state record to
> `.data/platform_webhook.json` after creating the webhook. Re-runs
> short-circuit on that file.
>
> If you ever delete the platform webhook in bookings@glnkco.com out of band (e.g.
> via SQL during a reset) — also delete `.data/platform_webhook.json`
> before re-running the bootstrap, otherwise the CLI will think it
> already exists and skip.

## Decisions worth knowing about

### "Send email to additional addresses" on event types — N/A in this build

The original brief (9a) called for the agency email to be set as a CC on
every event type, in addition to the receiver email, for redundancy.

**Status: not implemented. Not reachable.**

bookings@glnkco.com stripped the Workflows feature, and "send email to additional
recipients" was a Workflows action — it doesn't exist as a standalone
event-type field in this build. Confirmed by source:

- `packages/trpc/server/routers/viewer/eventTypes/heavy/update.handler.ts`
  carries the explicit comment `// Workflows feature removed - always
  disallow disabling standard emails`.
- Greps across event-type schemas for `additionalEmail | notifyEmail |
  ccEmail | emails: z.array | copyEmail` return zero hits.

**Sole agency-notification path: the receiver's email integration**
(`apps/receiver/src/receiver/integrations/email.py`) — drops a Resend
email to `AGENCY_NOTIFY_EMAIL` for every handled webhook. That's the
redundancy the spec wanted; it just lives at the receiver layer instead
of the event-type layer.

If we ever want a *second* path (true redundancy), options:

1. Add a second target to the receiver's fan-out (already trivial — the
   `dispatch_external` orchestrator runs all targets concurrently).
2. Patch bookings@glnkco.com to surface an `additionalEmails` field. Possible but
   would mean either reviving the Workflows package or writing a small
   custom field — both violate the "do not edit bookings@glnkco.com code" rule.

### Webhook scope — global platform, not per-client

We previously registered a **per-user** webhook during each client's
provisioning. That worked but was N+1 (one webhook per client, all
pointing at the same receiver URL).

We switched to **one platform webhook** registered once via
`bootstrap-webhook` (above). Same coverage, one row in bookings@glnkco.com's
`Webhook` table, simpler operation.

Pre-existing per-user webhooks for clients provisioned before the switch
(acme, beta, eta, gamma, zeta, lambda, mu, kappa) are still there. They
are **harmless**: the receiver dedupes on `(cal_booking_uid, event_type)`
via a UNIQUE constraint, so a double-delivery from per-user + platform
results in one row, not two. Fan-out fires only for the first.

To clean them up:

```bash
# Per-user webhooks have userId set; platform has userId=NULL + platform=true.
docker exec database psql -U unicorn_user -d calendso -c \
  $'DELETE FROM "Webhook" WHERE "userId" IS NOT NULL AND "subscriberUrl" = '"'"'http://host.docker.internal:8000/webhook'"'"';'
```

Optional. Skip unless you want a clean DB.

## Day-to-day

### Provision a new client

```bash
export CAL_WEB_BASE=http://localhost:3000
uv run glink-provision single \
    --name "Acme Inc" --email founder@acme.com --slug acme \
    --tz America/New_York \
    --calendly-url https://calendly.com/acme-inc/30min   # optional, fallback embed
```

Standard policy (set centrally — change in `packages/provisioning/src/provisioning/defaults.py`):

| Setting | Value |
|---|---|
| Event-type length | 30 min |
| Working hours | Mon–Fri 09:00–18:00 (client tz) |
| Buffers | 15 min before + after |
| Minimum notice | 4 hours |
| Booking window | 60 days, rolling |
| **Max bookings per day** | **5** |
| Booking questions | name, email + Company, "What would you like to discuss?" |

### Rebuild the fallback site

The fallback is a static export. Re-run after provisioning a new client
or changing a `calendly_url`:

```bash
cd apps/fallback
npm run build      # regenerates ./out
npm run serve      # serve at :3030, or upload ./out to your static host
```

It reads `../../.data/clients.json` — the manifest that provisioning
maintains automatically. Override path via `CLIENTS_MANIFEST_PATH`.

### Add fan-out targets

All four targets (Slack, HubSpot, Resend, Google Sheets) live in
`apps/receiver/src/receiver/integrations/`. Each is its own module,
each reads its own env vars, each is best-effort (a failure in one
never affects the others or the durability row).

To enable a target: drop its env vars into `apps/receiver/.env` and
`docker compose up -d --force-recreate receiver`. To disable a target:
unset its env vars. Receiver logs `fan-out integrations configured: [...]`
on startup so you can confirm.

| Target | Env it needs |
|---|---|
| Slack | `SLACK_WEBHOOK_URL` |
| HubSpot | `HUBSPOT_TOKEN` (+ optional `HUBSPOT_PIPELINE_ID`, `HUBSPOT_DEAL_STAGE`) |
| Email (Resend) | `RESEND_API_KEY`, `RESEND_FROM_EMAIL`, `AGENCY_NOTIFY_EMAIL` |
| Google Sheets | `GOOGLE_SHEETS_CREDENTIALS_JSON` (service-account JSON, single line) + `GOOGLE_SHEETS_SPREADSHEET_ID` (+ optional `GOOGLE_SHEETS_TAB_NAME`, default `Bookings`). The service account must be granted Editor access on the target spreadsheet. |

### Rotating the webhook secret

1. Generate a new secret: `openssl rand -hex 32`.
2. Update `apps/receiver/.env` `CAL_WEBHOOK_SECRET=<new>`.
3. Restart receiver: `docker compose -f apps/receiver/docker-compose.yml up -d --force-recreate receiver`.
4. Re-run `glink-provision bootstrap-webhook` — `ensure_platform_webhook` will detect the existing webhook by URL and *not* recreate it. To actually rotate the secret in bookings@glnkco.com, the simplest path is to delete the platform webhook row (`DELETE FROM "Webhook" WHERE platform = true`) and re-run the bootstrap. bookings@glnkco.com itself doesn't expose a "rotate secret" mutation we can call from outside.

### Resetting the local bookings@glnkco.com stack

Wipes everything (bookings@glnkco.com users, schedules, event types, webhooks) and
rebuilds from migrations:

```bash
cd cal.diy
docker compose down -v
docker compose up -d
# … then in glink-booking:
rm -rf .data/                            # nuke per-client records
docker compose -f apps/receiver/docker-compose.yml down -v   # nuke receiver Postgres
docker compose -f apps/receiver/docker-compose.yml up -d
uv run glink-provision bootstrap-webhook
# re-provision clients...
```

### Handing the admin UI to a new operator (e.g. Alex)

The admin UI (`apps/admin-ui`, port 3001) authenticates against bookings@glnkco.com.
For someone to log in they need **two** things:

1. A bookings@glnkco.com user account (any sign-up flow works).
2. That user's `role` set to `ADMIN` in bookings@glnkco.com's `users` table.

bookings@glnkco.com doesn't expose role promotion in its UI, so do it in SQL:

```bash
docker exec -i database psql -U unicorn_user -d calendso \
  -c "UPDATE users SET role = 'ADMIN' WHERE email = 'alex@agency.example';"
```

After that, `https://<admin-ui-host>:3001/login` accepts those credentials.

> **Note on `INACTIVE_ADMIN`** — bookings@glnkco.com reports a user's effective role
> as `INACTIVE_ADMIN` when they have `role = ADMIN` but haven't enabled
> 2FA. The admin-api treats both `ADMIN` and `INACTIVE_ADMIN` as admin,
> so the user can sign in and work without 2FA. Encourage 2FA anyway —
> the role downgrade is bookings@glnkco.com's nudge, not ours.

> **Per-client passwords are read from `.data/<email>.json`**. If you
> blow that directory away (see "Resetting the local bookings@glnkco.com stack") the
> admin UI's "Reveal" / "Copy password" buttons will stop showing the
> first-login password for old clients. The password still exists in
> bookings@glnkco.com's DB; it's just no longer recoverable from disk. Fresh
> provisions through the UI write the file back.

> **`.data` must be a persistent volume in production.** The compose
> file bind-mounts the host's `.data` into the admin-api container. If
> you redeploy and lose that mount, you lose the manifest and every
> first-login password. Plan accordingly.

### Admin session secret

The admin-api signs session JWTs with `ADMIN_SESSION_SECRET` (HS256,
24h TTL by default). Set it once in `apps/admin-api/.env`:

```bash
echo "ADMIN_SESSION_SECRET=$(openssl rand -hex 32)" >> apps/admin-api/.env
```

Rotating the secret invalidates every outstanding session — operators
will be bounced to `/login` on their next request. That's the only
"sign everyone out" lever; there's no per-user revoke.

## Known limitations

- **Crash between 2xx and fan-out** — see `apps/receiver/src/receiver/fanout.py` docstring. The DB row persists; the external dispatch is lost. No retry queue today.
- **HubSpot custom utm_* properties** — must exist on the Contact object before the integration can write them. One-time setup via `POST /crm/v3/properties/contacts` for each of `utm_source`, `utm_medium`, `utm_campaign`, `utm_content`, `utm_term` (string/text). Documented in commit message of the fan-out integration commit.
- **HubSpot rejects `*.test` TLDs** as invalid emails. Test data using `example.com` works fine; test data using `example.test` does not. Production data is unaffected.
- **Resend in dev** — using the test sender `onboarding@resend.dev` only sends to your own verified address. For production, verify a real sender domain.
