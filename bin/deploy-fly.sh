#!/usr/bin/env bash
# Deploy one (or all) glink-booking services to Fly.io.
#
# Usage:
#   bin/deploy-fly.sh                # deploy all four services
#   bin/deploy-fly.sh receiver       # deploy only the receiver
#   bin/deploy-fly.sh admin-api admin-ui   # deploy a subset
#
# Services: receiver admin-api admin-ui fallback
#
# Prerequisites (one-time, see apps/ops/RUNBOOK.md for the full first-deploy
# walkthrough):
#   - `fly auth login` done
#   - Apps created: fly apps create glnk-receiver glnk-admin-api glnk-admin-ui glnk-fallback
#   - Postgres created + attached: fly postgres create --name glnk-receiver-db ...
#                                  fly postgres attach glnk-receiver-db --app glnk-receiver
#   - Volume created: fly volumes create admin_data --app glnk-admin-api --region iad --size 1
#   - Secrets set:
#       fly secrets set CAL_WEBHOOK_SECRET=... --app glnk-receiver
#       fly secrets set ADMIN_SESSION_SECRET=$(openssl rand -hex 32) --app glnk-admin-api

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Prevent macOS tar from emitting AppleDouble sidecars (`._foo.json`) when
# archiving .data — they're binary metadata files that match `*.json` globs
# and crash write_manifest on the Linux extractor. Belt-and-suspenders.
export COPYFILE_DISABLE=1

ALL=(receiver admin-api admin-ui fallback)
TARGETS=("${@:-${ALL[@]}}")

for svc in "${TARGETS[@]}"; do
  case "$svc" in
    receiver)
      echo "==> Deploying receiver"
      (cd apps/receiver && fly deploy)
      ;;

    admin-api)
      echo "==> Deploying admin-api (build context: monorepo root)"
      # Build context = monorepo root (trailing '.') because the Dockerfile
      # COPYs packages/* which sit one level above apps/admin-api/.
      fly deploy --config apps/admin-api/fly.toml .
      ;;

    admin-ui)
      echo "==> Deploying admin-ui"
      (cd apps/admin-ui && fly deploy)
      ;;

    fallback)
      echo "==> Building fallback static export (reads .data/clients.json)"
      if [ ! -f .data/clients.json ]; then
        echo "ERROR: .data/clients.json not found. Run any provisioning command first." >&2
        exit 1
      fi
      # CAL_PUBLIC_BASE is baked into the prerendered HTML at build time.
      # Without it the "Try the booking page again" links default to
      # http://localhost:3000 — broken in prod. Override via env if needed.
      : "${CAL_PUBLIC_BASE:=https://glnk-booking.fly.dev}"
      (cd apps/fallback && npm install --no-audit --no-fund && CAL_PUBLIC_BASE="$CAL_PUBLIC_BASE" npm run build)
      echo "==> Deploying fallback (static out/ → nginx)"
      (cd apps/fallback && fly deploy)
      ;;

    *)
      echo "ERROR: unknown service '$svc'. Valid: ${ALL[*]}" >&2
      exit 1
      ;;
  esac
done

echo
echo "Done. URLs:"
echo "  receiver : https://glnk-receiver.fly.dev/health"
echo "  admin-api: https://glnk-admin-api.fly.dev/health"
echo "  admin-ui : https://glnk-admin-ui.fly.dev/login"
echo "  fallback : https://glnk-fallback.fly.dev/"
