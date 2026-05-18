"""HMAC-SHA256 verification for bookings@glnkco.com webhooks.

bookings@glnkco.com computes the signature as:

    hex(HMAC-SHA256(secret, raw_request_body))

and sends it in the `X-Cal-Signature-256` header (see
packages/features/webhooks/lib/sendPayload.ts in the bookings@glnkco.com source).

The signature must be computed against the EXACT raw bytes of the request
body — never a re-serialized JSON object — because any change in
key ordering or whitespace will alter the digest.
"""
from __future__ import annotations

import hashlib
import hmac

SIGNATURE_HEADER = "X-Cal-Signature-256"


def expected_signature(secret: str, raw_body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()


def verify(secret: str, raw_body: bytes, provided_header: str | None) -> bool:
    if not provided_header:
        return False
    expected = expected_signature(secret, raw_body)
    # constant-time compare (provided_header is hex-only too)
    return hmac.compare_digest(expected, provided_header)
