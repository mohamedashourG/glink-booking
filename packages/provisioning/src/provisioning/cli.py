"""Command-line interface: single-client and CSV-batch provisioning."""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from cal_client import Client, load_settings

from provisioning import store
from provisioning.provision import ProvisionError, ProvisionResult, provision_client
from provisioning.settings import load_webhook_settings


def _add_client_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--name", required=True, help="Client full name")
    p.add_argument("--email", required=True, help="Client email (used to log into cal.diy)")
    p.add_argument("--slug", required=True, help="cal.diy username, also part of the booking URL")
    p.add_argument("--tz", default="America/New_York", help="IANA timezone, default America/New_York")
    p.add_argument("--work-start", default="09:00", help="HH:MM in client tz, default 09:00")
    p.add_argument("--work-end", default="18:00", help="HH:MM in client tz, default 18:00")
    p.add_argument(
        "--calendly-url",
        default=None,
        help="Optional fallback Calendly URL the outage page embeds when cal.diy is down",
    )


def _print_result(res: ProvisionResult) -> None:
    rec = res.record
    state = "created" if res.created else "updated"
    wh = "new webhook" if res.webhook_created else "webhook reused"
    print(f"  ✓ {state} {rec.email}  [{wh} {rec.webhook_id}]")
    print(f"      booking link : {rec.booking_link}")
    print(f"      first-login pw: {rec.password}")


def _client_from_args(args: argparse.Namespace) -> Client:
    return Client(
        full_name=args.name,
        email=args.email,
        slug=args.slug,
        timezone=args.tz,
        work_start=args.work_start,
        work_end=args.work_end,
        calendly_url=args.calendly_url,
    )


def _clients_from_csv(path: Path) -> list[Client]:
    """Read a CSV with columns: full_name,email,slug[,timezone,work_start,work_end,calendly_url].

    Extra columns are ignored. A header row is required.
    `calendly_url` is optional — leave the cell empty for clients without one.
    """
    with path.open(newline="") as fh:
        reader = csv.DictReader(fh)
        required = {"full_name", "email", "slug"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise SystemExit(f"CSV {path} missing required columns: {sorted(missing)}")
        out: list[Client] = []
        for i, row in enumerate(reader, start=2):  # row 1 is the header
            try:
                out.append(
                    Client(
                        full_name=row["full_name"].strip(),
                        email=row["email"].strip(),
                        slug=row["slug"].strip(),
                        timezone=(row.get("timezone") or "").strip() or "America/New_York",
                        work_start=(row.get("work_start") or "").strip() or "09:00",
                        work_end=(row.get("work_end") or "").strip() or "18:00",
                        calendly_url=(row.get("calendly_url") or "").strip() or None,
                    )
                )
            except KeyError as exc:
                raise SystemExit(f"CSV {path} row {i} missing field: {exc}") from exc
        return out


def _run_one(client: Client, *, settings, webhook_settings) -> ProvisionResult | None:
    try:
        return provision_client(client, settings, webhook_settings)
    except ProvisionError as exc:
        # Loud, single-line failure that names the client + the step.
        print(f"  ✗ FAILED at step '{exc.step}' for {exc.email}: {exc}", file=sys.stderr)
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="glink-provision", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    one = sub.add_parser("single", help="Provision a single client passed via CLI flags")
    _add_client_args(one)

    batch = sub.add_parser("batch", help="Provision every row of a CSV")
    batch.add_argument("csv_path", type=Path, help="Path to CSV with columns full_name,email,slug,...")

    args = parser.parse_args(argv)
    settings = load_settings()
    webhook_settings = load_webhook_settings()
    print(f"cal.diy web base: {settings.cal_web_base}")
    print(f"webhook receiver: {webhook_settings.receiver_url}")

    if args.cmd == "single":
        result = _run_one(_client_from_args(args), settings=settings, webhook_settings=webhook_settings)
        if result is None:
            return 1
        _print_result(result)
        manifest = store.write_manifest()
        print(f"manifest: {manifest}")
        return 0

    # batch
    clients = _clients_from_csv(args.csv_path)
    print(f"Provisioning {len(clients)} client(s) from {args.csv_path}\n")
    successes: list[ProvisionResult] = []
    failures = 0
    for c in clients:
        print(f"→ {c.email}")
        r = _run_one(c, settings=settings, webhook_settings=webhook_settings)
        if r is None:
            failures += 1
        else:
            successes.append(r)
    manifest = store.write_manifest()
    print(f"\nmanifest: {manifest}")

    print()
    print(f"Done: {len(successes)} succeeded, {failures} failed.\n")
    if successes:
        print("Booking links:")
        for r in successes:
            print(f"  {r.record.email:32}  {r.record.booking_link}   (pw: {r.record.password})")
    return 1 if failures else 0
