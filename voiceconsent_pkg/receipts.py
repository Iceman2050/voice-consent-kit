"""voice-consent-kit: consent receipts + disclosure snippets for AI voice cloning.

Stdlib only. This module holds the receipt crypto and disclosure rendering;
the CLI entry point is voiceconsent.py.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timezone

VERSION = "1.0"
RECEIPT_VERSION = "1.0"

# Fields covered by the HMAC signature, in canonical order.
SIGNED_FIELDS = ("receipt_id", "voice_owner", "granted_to", "scope",
                 "issued_at", "expires", "version")


def _canonical_bytes(payload: dict) -> bytes:
    """Deterministic JSON encoding of the signed fields only."""
    canonical = {k: payload[k] for k in SIGNED_FIELDS if k in payload}
    return json.dumps(canonical, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def sign_receipt(payload: dict, secret: str) -> str:
    """HMAC-SHA256 over the canonical payload. Returns hex digest."""
    if not secret:
        raise ValueError("a signing secret is required")
    return hmac.new(secret.encode("utf-8"), _canonical_bytes(payload),
                    hashlib.sha256).hexdigest()


def issue_receipt(voice_owner: str, granted_to: str, scope: str,
                  expires: str, secret: str,
                  issued_at: str | None = None) -> dict:
    """Create and sign a consent receipt. Raises ValueError on bad input."""
    for name, val in (("voice_owner", voice_owner), ("granted_to", granted_to),
                      ("scope", scope), ("expires", expires)):
        if not (val or "").strip():
            raise ValueError(f"{name} must not be empty")
    try:
        exp_date = datetime.strptime(expires.strip(), "%Y-%m-%d").date()
    except ValueError:
        raise ValueError("expires must be YYYY-MM-DD")
    if issued_at is None:
        issued_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    receipt = {
        "receipt_id": secrets.token_hex(16),
        "voice_owner": voice_owner.strip(),
        "granted_to": granted_to.strip(),
        "scope": scope.strip(),
        "issued_at": issued_at,
        "expires": exp_date.isoformat(),
        "version": RECEIPT_VERSION,
    }
    receipt["signature"] = sign_receipt(receipt, secret)
    return receipt


def load_revocations(path: str) -> set:
    """Read the local revocation blocklist. Missing/corrupt file -> empty set."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            ids = data.get("revoked", [])
        elif isinstance(data, list):
            ids = data
        else:
            return set()
        return {str(x) for x in ids if x}
    except (OSError, ValueError):
        return set()


def save_revocations(path: str, revoked: set) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"revoked": sorted(revoked),
                   "updated_at": datetime.now(timezone.utc).strftime(
                       "%Y-%m-%dT%H:%M:%SZ")},
                  f, indent=2, sort_keys=True)
        f.write("\n")


def verify_receipt(receipt: dict, secret: str,
                   revocations: set | None = None,
                   now: datetime | None = None) -> dict:
    """Verify a receipt. Returns {"status": VALID|INVALID|EXPIRED|REVOKED,
    "reasons": [...]}. Never raises on malformed input."""
    reasons: list[str] = []
    if not isinstance(receipt, dict):
        return {"status": "INVALID", "reasons": ["receipt is not a JSON object"]}
    missing = [k for k in SIGNED_FIELDS if k not in receipt]
    if missing:
        reasons.append("missing fields: " + ", ".join(missing))
    if "signature" not in receipt:
        reasons.append("missing signature")
    if reasons:
        return {"status": "INVALID", "reasons": reasons}

    expected = sign_receipt(receipt, secret)
    if not hmac.compare_digest(str(receipt.get("signature", "")),
                               expected):
        return {"status": "INVALID",
                "reasons": ["signature mismatch — receipt was tampered with "
                            "or signed with a different secret"]}

    if now is None:
        now = datetime.now(timezone.utc)
    try:
        exp = datetime.strptime(str(receipt["expires"]), "%Y-%m-%d").replace(
            tzinfo=timezone.utc)
    except ValueError:
        return {"status": "INVALID",
                "reasons": ["expires is not a valid YYYY-MM-DD date"]}
    # Expiry is end-of-day UTC on the expiry date.
    if now > exp.replace(hour=23, minute=59, second=59):
        return {"status": "EXPIRED",
                "reasons": [f"receipt expired on {receipt['expires']}"]}

    if revocations and str(receipt.get("receipt_id")) in revocations:
        return {"status": "REVOKED",
                "reasons": ["receipt_id is on the local revocation blocklist "
                            "(note: blocklist is local-only, not a global registry)"]}

    return {"status": "VALID", "reasons": []}


def default_revocations_path() -> str:
    return os.path.join(os.getcwd(), "revocations.json")
