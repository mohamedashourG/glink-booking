# receiver — cal.diy webhook receiver

Durability layer that captures every cal.diy booking event into its own
Postgres before any external fan-out (Slack / HubSpot / email — added in
a follow-up).

The receiver:

- accepts `POST /webhook` from cal.diy
- verifies `X-Cal-Signature-256` (HMAC-SHA256 over the raw body, hex-encoded)
- persists one row per delivery into its own Postgres
- treats the DB write as the source of truth — failures return non-2xx so
  cal.diy retries
- handles `BOOKING_CREATED`, `BOOKING_RESCHEDULED`, `BOOKING_CANCELLED`,
  `BOOKING_REJECTED`; unknown trigger types are a 200-OK no-op
- dedupes retries via a `UNIQUE (cal_booking_uid, event_type)` constraint
- exposes a `/health` endpoint

Non-goals (deliberate):
- the receiver never calls cal.diy
- the receiver never writes into cal.diy's database

## Fan-out: Slack / HubSpot / Email

After the DB row is committed and the 2xx returned, three best-effort
integrations fire in a background task ([`fanout.py`](src/receiver/fanout.py)).
They run **concurrently** so a slow one doesn't block the others.

- They fire **only on newly-stored rows** — a cal.diy retry (deduped by
  the UNIQUE constraint) does NOT re-post to Slack/HubSpot/email.
- Each integration is independent. A failure or hang in one is logged
  and contained; it never affects the others, the DB row, or the
  response cal.diy already received.
- Each reads its own env vars. Unset = silently skipped at startup
  ("not configured"). The receiver runs cleanly with zero, one, two,
  or all three configured.
- Known limitation, accepted for now: if the receiver process crashes
  between the 2xx and the background task running, that booking's
  fan-out is lost. The DB row persisted, so a future replay tool can
  re-fire — out of scope here.

### Env vars

| Var                    | Required for       | Notes |
|------------------------|--------------------|-------|
| `CAL_WEBHOOK_SECRET`   | the receiver       | must match the secret on the cal.diy webhook subscription |
| `DATABASE_URL`         | the receiver       | set by docker-compose; points at the bundled Postgres |
| `SLACK_WEBHOOK_URL`    | Slack integration  | incoming-webhook URL from your Slack app config |
| `HUBSPOT_TOKEN`        | HubSpot integration | private-app access token |
| `HUBSPOT_PIPELINE_ID`  | HubSpot deal step  | optional. With `HUBSPOT_DEAL_STAGE`, also creates a deal at that stage. If unset (or HubSpot rejects them), contact + meeting still sync — only the deal step is skipped |
| `HUBSPOT_DEAL_STAGE`   | HubSpot deal step  | optional, internal stage id |
| `RESEND_API_KEY`       | email integration  | from <https://resend.com/api-keys> |
| `RESEND_FROM_EMAIL`    | email integration  | sender — for local dev you can use Resend's test sender `onboarding@resend.dev`, sending to your own verified address |
| `AGENCY_NOTIFY_EMAIL`  | email integration  | recipient |

Drop them into `apps/receiver/.env` next to `CAL_WEBHOOK_SECRET`. The
docker-compose file passes them through to the container.

## Local bring-up

The receiver runs as its own Compose project (it doesn't share a network
with cal.diy — cal.diy reaches it via `host.docker.internal:8000`).

```bash
cd apps/receiver

# 1) Generate a webhook secret and store it for Compose
echo "CAL_WEBHOOK_SECRET=$(openssl rand -hex 32)" > .env

# 2) Build + start the receiver and its Postgres
docker compose up -d --build

# 3) Smoke-test
curl -fsS http://localhost:8000/health     # → {"status":"ok"}
```

The `CAL_WEBHOOK_SECRET` you generate here must match the
`CAL_WEBHOOK_SECRET` env var you give the provisioning CLI — it's the
shared secret cal.diy signs each delivery with and the receiver verifies
against. Provisioning auto-registers a per-user webhook for every client
pointing at this receiver:

    http://host.docker.internal:8000/webhook

## Verifying durability

Every successful POST to `/webhook` writes a row into:

```bash
docker compose exec postgres psql -U receiver -d receiver \
    -c "SELECT id, event_type, client_slug, prospect_email, scheduled_at, utm_source FROM bookings ORDER BY id DESC LIMIT 5;"
```

The full original payload is always in `raw_payload_json` — extracted
columns are a convenience, not a contract.

## Stop / reset

```bash
docker compose stop          # keep data
docker compose down          # keep data
docker compose down -v       # WIPE Postgres volume
```
