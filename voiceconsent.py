"""voice-consent-kit CLI: consent receipts + disclosure snippets for AI voice cloning."""
from __future__ import annotations

import argparse
import json
import os
import sys

from voiceconsent_pkg.disclosure import render_disclosure
from voiceconsent_pkg.receipts import (default_revocations_path,
                                       issue_receipt, load_revocations,
                                       save_revocations, verify_receipt)

VERSION = "1.0.0"


def _secret(args) -> str:
    secret = args.secret or os.environ.get("VOICE_CONSENT_SECRET", "")
    if not secret:
        raise SystemExit("error: no signing secret — pass --secret or set "
                         "VOICE_CONSENT_SECRET")
    return secret


def cmd_issue(args) -> int:
    receipt = issue_receipt(args.voice_owner, args.granted_to, args.scope,
                            args.expires, _secret(args))
    out = json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(out + "\n")
        print(f"receipt written to {args.output} (id {receipt['receipt_id']})")
    else:
        print(out)
    return 0


def cmd_verify(args) -> int:
    try:
        with open(args.receipt, "r", encoding="utf-8") as f:
            receipt = json.load(f)
    except (OSError, ValueError) as e:
        print(f"INVALID: could not read receipt file: {e}")
        return 2
    revocations = load_revocations(args.revocations or
                                   default_revocations_path())
    result = verify_receipt(receipt, _secret(args), revocations)
    status = result["status"]
    print(status)
    for r in result["reasons"]:
        print(" - " + r)
    if revocations:
        print("(checked against local revocation blocklist: "
              f"{args.revocations or default_revocations_path()})")
    return 0 if status == "VALID" else 1


def cmd_revoke(args) -> int:
    path = args.revocations or default_revocations_path()
    revoked = load_revocations(path)
    if args.receipt_id in revoked:
        print(f"{args.receipt_id} is already revoked (local blocklist)")
        return 0
    revoked.add(args.receipt_id)
    save_revocations(path, revoked)
    print(f"revoked {args.receipt_id} (local blocklist: {path})")
    print("NOTE: this blocklist is local-only — verifiers on other machines "
          "will not see this revocation.")
    return 0


def cmd_disclosure(args) -> int:
    print(render_disclosure(args.voice_label, args.format))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="voiceconsent",
        description="Consent receipts + disclosure snippets for AI voice "
                    "cloning. Stdlib only.")
    p.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    sub = p.add_subparsers(dest="command", required=True)

    pi = sub.add_parser("issue", help="issue a signed consent receipt")
    pi.add_argument("--voice-owner", required=True,
                    help="person whose voice may be cloned")
    pi.add_argument("--granted-to", required=True,
                    help="organisation/person granted cloning rights")
    pi.add_argument("--scope", required=True,
                    help="permitted uses, e.g. 'podcast narration, EN only'")
    pi.add_argument("--expires", required=True,
                    help="consent expiry date YYYY-MM-DD")
    pi.add_argument("--secret",
                    help="HMAC signing secret (or VOICE_CONSENT_SECRET env)")
    pi.add_argument("--output", "-o", help="write receipt JSON to file")
    pi.set_defaults(func=cmd_issue)

    pv = sub.add_parser("verify", help="verify a consent receipt")
    pv.add_argument("--receipt", required=True, help="receipt JSON file")
    pv.add_argument("--secret",
                    help="HMAC signing secret (or VOICE_CONSENT_SECRET env)")
    pv.add_argument("--revocations",
                    help="path to revocations.json blocklist")
    pv.set_defaults(func=cmd_verify)

    pr = sub.add_parser("revoke", help="revoke a receipt id (local blocklist)")
    pr.add_argument("--receipt-id", required=True)
    pr.add_argument("--revocations", help="path to revocations.json blocklist")
    pr.set_defaults(func=cmd_revoke)

    pd = sub.add_parser("disclosure",
                        help="generate an AI-audio disclosure snippet")
    pd.add_argument("--format", choices=("text", "html"), default="text")
    pd.add_argument("--voice-label", required=True,
                    help="label identifying the synthetic voice")
    pd.set_defaults(func=cmd_disclosure)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
