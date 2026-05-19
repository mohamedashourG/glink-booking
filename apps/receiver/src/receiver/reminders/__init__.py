"""Pre-meeting reminder emails.

Three pieces, kept separate so each is easy to reason about on its own:

- `config`    — knows the *policy*: who gets reminded, how long before the
                meeting, per-client overrides, env defaults.
- `scheduler` — runs at webhook time. Inserts/updates/cancels rows in the
                `reminder_jobs` queue based on the booking lifecycle event.
- `worker`    — runs continuously. Polls `reminder_jobs` for due rows,
                sends each via Resend, handles retries and recovery.

The send side reuses the existing Resend env (RESEND_API_KEY,
RESEND_FROM_EMAIL) — no new outbound credential. Email body lives in
`template`.

Disabling the feature: set REMINDER_OFFSETS_MIN=  (empty). Receiver will
keep accepting webhooks, but no new reminder rows are scheduled and the
worker has nothing to do.
"""
