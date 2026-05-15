"""Plain data models shared across cal_client and the provisioning CLI."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict


@dataclass
class Client:
    """Inputs the operator provides per client."""

    full_name: str
    email: str
    slug: str  # used as cal.diy username
    timezone: str = "America/New_York"
    work_start: str = "09:00"  # HH:MM, in client's timezone
    work_end: str = "18:00"
    # Optional: a fallback Calendly URL the outage page can embed when
    # cal.diy is unreachable. Most clients won't have one.
    calendly_url: str | None = None


@dataclass
class ProvisionedClient:
    """What we persist after a successful provision."""

    email: str
    slug: str
    full_name: str
    timezone: str
    password: str
    cal_user_id: int
    schedule_id: int
    event_type_id: int
    event_type_slug: str
    booking_link: str
    work_start: str = "09:00"
    work_end: str = "18:00"
    # cal.diy webhook subscription that wires this client's bookings into
    # the receiver. Set on first provision; reused (not duplicated) on re-runs.
    webhook_id: str | None = None
    # Optional: fallback Calendly URL — passed through to the manifest the
    # outage-fallback Next.js app reads at build time.
    calendly_url: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)
