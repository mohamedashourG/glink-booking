"""Subject + HTML body for the reminder email.

Kept narrow on purpose — anything that isn't strictly the email contents
lives in the scheduler/worker. Inputs come straight from the row joined
with the booking; no DB access in here.

If the agency wants brand polish later, add CSS variables here. Today the
goal is "renders well in Gmail/Outlook/Apple Mail without surprises."
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone as _tz
from html import escape


@dataclass(frozen=True)
class ReminderContext:
    recipient_role: str               # 'prospect' | 'host' | 'agency'
    recipient_email: str              # who the email is going to (FYI only)
    minutes_until: int                # always >= 0 at send time
    scheduled_at: datetime            # UTC; we render in `display_tz`
    display_tz: str | None            # IANA tz; falls back to UTC
    host_name: str | None
    host_email: str | None
    prospect_name: str | None
    prospect_email: str | None
    prospect_company: str | None
    video_link: str | None
    booking_uid: str
    # Where the booker can reschedule/cancel. Built from the webhook
    # payload (`metadata.bookerUrl` + slug + uid) at scheduling time; may
    # be None for old rows or unusual cal.diy builds.
    manage_url: str | None


# Pretty labels for the chip near the top ("Your meeting … in 1 hour").
def _humanize_minutes(n: int) -> str:
    if n <= 0:
        return "now"
    if n < 60:
        return f"in {n} minute{'s' if n != 1 else ''}"
    hours, mins = divmod(n, 60)
    if hours < 24:
        return f"in {hours} hour{'s' if hours != 1 else ''}" + (f" {mins} min" if mins else "")
    days, rem_h = divmod(hours, 24)
    return f"in {days} day{'s' if days != 1 else ''}" + (f" {rem_h}h" if rem_h else "")


def _format_when(scheduled_at: datetime, tz_name: str | None) -> str:
    """ "Tue, May 21 at 3:00 PM EDT". Falls back to UTC when no tz given.

    We deliberately use stdlib zoneinfo (no extra dep) — Python 3.9+ ships
    it. Cal.com timezones are IANA strings, which zoneinfo handles natively.
    """
    target_tz = _tz.utc
    label_tz = "UTC"
    if tz_name:
        try:
            from zoneinfo import ZoneInfo
            target_tz = ZoneInfo(tz_name)
            label_tz = tz_name
        except Exception:  # noqa: BLE001
            pass
    local = scheduled_at.astimezone(target_tz)
    return f"{local.strftime('%a, %b %-d at %-I:%M %p')} ({label_tz})"


def subject(ctx: ReminderContext) -> str:
    """Short, identifiable, no leading [BRACKETS] — operators have
    multiple booking notifications already (the per-event fan-out email
    uses [Booking]). Reminder is distinct."""
    host = ctx.host_name or "your host"
    return f"Reminder: meeting with {host} {_humanize_minutes(ctx.minutes_until)}"


def html(ctx: ReminderContext) -> str:
    """Build a single self-contained HTML string.

    Layout principles:
    - Single column, max-width 560px (renders fine on a phone)
    - One big primary action: the join URL
    - Time always rendered in the recipient's timezone
    - Footer carries the booking uid + the manage link for support
    """
    when_str = _format_when(ctx.scheduled_at, ctx.display_tz)
    countdown = _humanize_minutes(ctx.minutes_until)
    # Greeting depends on role — the prospect sees "your meeting", the
    # host sees "your meeting with <prospect>", the agency sees a more
    # neutral "Heads up — meeting between …" to make the email skim-able.
    if ctx.recipient_role == "prospect":
        greeting = f"Your meeting with <b>{escape(ctx.host_name or 'your host')}</b> is {countdown}."
    elif ctx.recipient_role == "host":
        with_who = escape(ctx.prospect_name or ctx.prospect_email or "your guest")
        greeting = f"Your meeting with <b>{with_who}</b> is {countdown}."
    else:  # agency
        host = escape(ctx.host_name or "host")
        guest = escape(ctx.prospect_name or ctx.prospect_email or "guest")
        greeting = f"Heads up — <b>{host}</b> meets <b>{guest}</b> {countdown}."

    join_button = ""
    if ctx.video_link:
        join_button = (
            f'<p style="margin:24px 0;">'
            f'<a href="{escape(ctx.video_link)}" '
            f'style="display:inline-block;background:#0a66d6;color:#fff;'
            f'text-decoration:none;padding:12px 20px;border-radius:8px;'
            f'font-weight:600">Join meeting</a></p>'
        )
    else:
        join_button = (
            '<p style="margin:24px 0;color:#666;font-style:italic">'
            "No meeting URL on file. Check your calendar invite for the dial-in.</p>"
        )

    rows: list[tuple[str, str]] = [("When", when_str)]
    if ctx.recipient_role != "prospect" and ctx.prospect_name:
        rows.append(("Prospect", escape(ctx.prospect_name)))
    if ctx.recipient_role != "prospect" and ctx.prospect_email:
        rows.append(("Email", escape(ctx.prospect_email)))
    if ctx.prospect_company:
        rows.append(("Company", escape(ctx.prospect_company)))
    if ctx.recipient_role != "host" and ctx.host_name:
        rows.append(("Host", escape(ctx.host_name)))
    if ctx.video_link:
        rows.append(("Meeting link", f'<a href="{escape(ctx.video_link)}">{escape(ctx.video_link)}</a>'))

    detail_table = "".join(
        f'<tr><td style="padding:4px 12px 4px 0;color:#666;'
        f'white-space:nowrap;vertical-align:top">{escape(k)}</td>'
        f'<td style="padding:4px 0;word-break:break-word">{v}</td></tr>'
        for k, v in rows
    )

    manage_footer = ""
    if ctx.manage_url:
        manage_footer = (
            f'<p style="margin-top:16px;color:#999;font-size:12px">'
            f'Need to change this? <a href="{escape(ctx.manage_url)}" '
            f'style="color:#999">Reschedule or cancel</a> · '
            f'Booking <code>{escape(ctx.booking_uid)}</code>'
            "</p>"
        )
    else:
        manage_footer = (
            f'<p style="margin-top:16px;color:#999;font-size:12px">'
            f'Booking <code>{escape(ctx.booking_uid)}</code></p>'
        )

    return f"""\
<!doctype html>
<html><body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
                   color:#222;line-height:1.5;margin:0;padding:24px;background:#f6f7f9">
  <div style="max-width:560px;margin:0 auto;background:#fff;padding:28px 28px 20px;
              border-radius:12px;box-shadow:0 1px 4px rgba(0,0,0,0.04)">
    <p style="margin:0 0 16px;font-size:16px">{greeting}</p>
    {join_button}
    <table style="font-size:14px;border-collapse:collapse;width:100%">
      {detail_table}
    </table>
    {manage_footer}
  </div>
</body></html>"""
