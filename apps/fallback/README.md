# fallback — outage page

Static Next.js 16 app. One prerendered page per provisioned client at
`/<slug>/`. Shown to prospects when bookings@glnkco.com is unreachable — the routing
layer that flips traffic over to here is a deploy-phase concern and
**not** in this app.

**Hard contract: zero runtime dependency on bookings@glnkco.com or the receiver.**
Everything is generated at build time from
`../../.data/clients.json` (the manifest the provisioning CLI writes).
Once built, the `out/` directory is a fully self-contained static site
that any plain HTTP server (or CDN) can serve.

## What each page shows

- A clear "Booking temporarily unavailable" headline with the host's name,
  so prospects know they're in the right place.
- A primary `mailto:` CTA — `Email <full_name> directly at <email>`.
- A "Try the booking page again" link back to bookings@glnkco.com at `CAL_PUBLIC_BASE`
  (defaults to `http://localhost:3000`).
- **If** the client has a `calendly_url` in the manifest: an inline
  Calendly iframe so prospects can still self-serve a slot. **If** they
  don't: the email CTA is the whole page — no warning, no broken embed.

Unknown slugs render the global `app/not-found.tsx` 404.

## Bring-up

```bash
cd apps/fallback
npm install

# 1) Make sure the manifest is up to date (any provisioning run does it)
uv run --project ../.. glink-provision single ...   # if needed

# 2) Build the static site
npm run build           # writes ./out
npm run serve           # serves ./out at http://localhost:3030
```

Optional env at build time:

| Var | Default | Purpose |
|---|---|---|
| `CAL_PUBLIC_BASE` | `http://localhost:3000` | Base URL the "try booking again" links point at |
| `CLIENTS_MANIFEST_PATH` | `<repo>/.data/clients.json` | Override the manifest source |

## Verifying the offline guarantee

```bash
# Stop bookings@glnkco.com AND the receiver:
docker compose -f ../../../cal.diy/docker-compose.yml stop
docker compose -f ../receiver/docker-compose.yml stop

# Serve the static build — should still work with everything else dead:
npm run serve
curl -fsS http://localhost:3030/<slug>/ | grep "Booking temporarily unavailable"
```
