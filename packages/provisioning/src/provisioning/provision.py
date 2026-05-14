"""Per-client provisioning orchestrator.

Strict ordering — each step must succeed before the next:

    1. signup (web)                     ─┐ if 409: load stored record + skip
    2. login  (web/NextAuth)             │
    3. create + update schedule (tRPC)   │ idempotent on re-run
    4. create + update event type (tRPC) ─┘

Failure at any step raises ProvisionError tagging the client + step.
"""
from __future__ import annotations

import secrets
import string
from dataclasses import dataclass, replace

from cal_client import Client, ProvisionedClient, Settings
from cal_client.cal_web import (
    CalWebError,
    SignupConflict,
    create_event_type,
    create_schedule,
    ensure_webhook,
    login,
    signup,
    standard_booking_fields,
    update_event_type,
    update_schedule,
    weekday_schedule,
)

from provisioning import defaults, store
from provisioning.settings import WebhookSettings


class ProvisionError(RuntimeError):
    """Raised when provisioning fails for a specific client.

    The CLI catches this, prints `step` + `email`, and continues with the
    next client (in batch mode) or exits non-zero (in single mode).
    """

    def __init__(self, *, email: str, step: str, message: str, cause: Exception | None = None):
        super().__init__(f"[{step}] {email}: {message}")
        self.email = email
        self.step = step
        self.cause = cause


@dataclass
class ProvisionResult:
    record: ProvisionedClient
    created: bool  # True if the user was newly signed up; False if already existed
    webhook_created: bool = False  # True if a new webhook was registered this run


def _generate_password() -> str:
    """20-char password from a friendly alphabet (no ambiguous chars)."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*-_=+"
    # Avoid leading/trailing punctuation that some shells mangle when echoed
    body = "".join(secrets.choice(alphabet) for _ in range(20))
    return body


def _booking_link(base: str, slug: str, event_slug: str) -> str:
    return f"{base}/{slug}/{event_slug}"


def provision_client(
    client: Client,
    settings: Settings,
    webhook_settings: WebhookSettings,
) -> ProvisionResult:
    base = settings.cal_web_base

    # 1. signup ---------------------------------------------------------------
    existing = store.load(client.email)
    if existing is None:
        password = _generate_password()
        try:
            signup(base, email=client.email, password=password, username=client.slug)
            created = True
        except SignupConflict as exc:
            # Race: someone else (UI? a parallel run?) created this email.
            # Without a stored password we cannot log in, so refuse to guess.
            raise ProvisionError(
                email=client.email,
                step="signup",
                message=(
                    "email/username already exists in cal.diy but no local record found in "
                    f"{store.default_store_dir()}; cannot recover the password to continue. "
                    "Reset the user (or remove them) before re-running."
                ),
                cause=exc,
            ) from exc
        except CalWebError as exc:
            raise ProvisionError(
                email=client.email, step="signup", message=str(exc), cause=exc
            ) from exc
    else:
        password = existing.password
        created = False

    # 2. login ---------------------------------------------------------------
    try:
        session = login(base, email=client.email, password=password)
    except CalWebError as exc:
        raise ProvisionError(
            email=client.email, step="login", message=str(exc), cause=exc
        ) from exc

    with session:
        try:
            # 3. schedule ---------------------------------------------------
            if existing is not None:
                schedule_id = existing.schedule_id
                cal_user_id = existing.cal_user_id
            else:
                schedule_id, cal_user_id = create_schedule(session, name=defaults.SCHEDULE_NAME)
            update_schedule(
                session,
                schedule_id=schedule_id,
                name=defaults.SCHEDULE_NAME,
                timezone=client.timezone,
                schedule=weekday_schedule(client.work_start, client.work_end),
            )
        except CalWebError as exc:
            raise ProvisionError(
                email=client.email, step="schedule", message=str(exc), cause=exc
            ) from exc

        try:
            # 4. event type ------------------------------------------------
            if existing is not None:
                event_type_id = existing.event_type_id
                event_type_slug = existing.event_type_slug
            else:
                event_type_id = create_event_type(
                    session,
                    title=defaults.EVENT_TYPE_TITLE,
                    slug=defaults.EVENT_TYPE_SLUG,
                    length_minutes=defaults.EVENT_TYPE_LENGTH_MINUTES,
                )
                event_type_slug = defaults.EVENT_TYPE_SLUG
            update_event_type(
                session,
                event_type_id=event_type_id,
                schedule_id=schedule_id,
                minimum_notice_minutes=defaults.MINIMUM_NOTICE_MINUTES,
                before_buffer_minutes=defaults.BEFORE_BUFFER_MINUTES,
                after_buffer_minutes=defaults.AFTER_BUFFER_MINUTES,
                rolling_window_days=defaults.ROLLING_WINDOW_DAYS,
                booking_fields=standard_booking_fields(defaults.EXTRA_BOOKING_QUESTIONS),
            )
        except CalWebError as exc:
            raise ProvisionError(
                email=client.email, step="event_type", message=str(exc), cause=exc
            ) from exc

        # Persist what we know BEFORE the webhook step so a webhook
        # failure leaves a recoverable record (re-runs can retry the
        # webhook step without re-signing-up the user).
        partial_record = ProvisionedClient(
            email=client.email,
            slug=client.slug,
            full_name=client.full_name,
            timezone=client.timezone,
            password=password,
            cal_user_id=cal_user_id,
            schedule_id=schedule_id,
            event_type_id=event_type_id,
            event_type_slug=event_type_slug,
            booking_link=_booking_link(base, client.slug, event_type_slug),
            work_start=client.work_start,
            work_end=client.work_end,
            webhook_id=existing.webhook_id if existing else None,
        )
        store.save(partial_record)

        try:
            # 5. webhook ---------------------------------------------------
            # Per-user scope is the default for new webhooks (one subscription
            # covers every event type the client owns now or later). Match is
            # by subscriberUrl across BOTH per-user and per-event-type scopes,
            # so a leftover per-event-type webhook from earlier testing is
            # reused rather than duplicated.
            webhook_id, webhook_created = ensure_webhook(
                session,
                subscriber_url=webhook_settings.receiver_url,
                secret=webhook_settings.shared_secret,
                event_type_id=event_type_id,
            )
        except CalWebError as exc:
            raise ProvisionError(
                email=client.email, step="webhook", message=str(exc), cause=exc
            ) from exc

    final_record = replace(partial_record, webhook_id=webhook_id)
    store.save(final_record)
    return ProvisionResult(record=final_record, created=created, webhook_created=webhook_created)
