# voice-consent-kit

Consent receipts + disclosure snippets for AI voice cloning. Stdlib-only Python CLI — no dependencies, no network, nothing to install beyond Python 3.10+.

## The problem

AI voice cloning is now trivial, and deepfake disclosure duties are arriving (EU AI Act transparency obligations for synthetic content). If you commission, produce, or publish AI-cloned voices, you need two things:

1. **Proof of consent** — a tamper-evident record that the voice owner agreed, for what uses, and until when.
2. **A visible disclosure** — telling your audience the audio is AI-generated.

This kit gives you both as small, auditable building blocks.

## Quick start

```bash
# 1. Issue a consent receipt (secret via env keeps it out of shell history)
export VOICE_CONSENT_SECRET="a-long-random-secret"
python3 voiceconsent.py issue \
  --voice-owner "Jane Doe" \
  --granted-to "Acme Podcasts" \
  --scope "podcast narration, English only" \
  --expires 2027-12-31 \
  -o receipt.json

# 2. Verify it later (tamper? expired? revoked?)
python3 voiceconsent.py verify --receipt receipt.json
# -> VALID

# 3. Revoke it if consent is withdrawn
python3 voiceconsent.py revoke --receipt-id <id-from-receipt>
python3 voiceconsent.py verify --receipt receipt.json
# -> REVOKED

# 4. Generate a disclosure snippet for your episode page
python3 voiceconsent.py disclosure --format html --voice-label "Narrator (AI)"
```

## Trust model (read this)

- A receipt is JSON signed with **HMAC-SHA256** using a shared secret. Verification proves the receipt was issued by **whoever holds the secret** and has not been altered since.
- This is **not a PKI identity system**. It does not prove *who* the voice owner is — it proves the receipt is intact and came from the secret-holder. For legal-grade identity, pair receipts with your own contracting process.
- The revocation blocklist (`revocations.json`) is **local-only**. Revoking on your machine does not notify verifiers on other machines. It is a starting point, not a global registry.
- Expiry is checked against the verifier's clock (end-of-day UTC on the expiry date).

## What this is NOT

- **No audio watermarking.** Robust, inaudible watermarking of audio cannot be done honestly with the Python standard library, so this kit does not pretend to. If you need watermarking, use a dedicated audio-watermarking library or service.
- **No identity verification / PKI.** See trust model above.
- **No legal advice.** Receipt fields are a consent *record*, not a contract. Consult counsel for enforceability in your jurisdiction.

## Receipt format

```json
{
  "receipt_id": "9f2c…",
  "voice_owner": "Jane Doe",
  "granted_to": "Acme Podcasts",
  "scope": "podcast narration, English only",
  "issued_at": "2026-10-16T13:40:00Z",
  "expires": "2027-12-31",
  "version": "1.0",
  "signature": "hmac-sha256 hex over the canonical JSON of the fields above"
}
```

The signature covers the canonical JSON (sorted keys, compact separators, UTF-8) of every field except `signature` itself. Any change — even whitespace in a value — invalidates it. Verification uses constant-time comparison.

## Verification statuses

| Status    | Meaning                                              | Exit code |
|-----------|------------------------------------------------------|-----------|
| `VALID`   | signature checks out, not expired, not revoked       | 0         |
| `INVALID` | bad signature, missing fields, unreadable file       | 1 (2 = file unreadable) |
| `EXPIRED` | past the expiry date                                 | 1         |
| `REVOKED` | receipt_id is on the local revocation blocklist      | 1         |

## Tests

```bash
python3 -m unittest discover -s tests
```

18 tests: issue→verify roundtrip, tampered scope/expiry, wrong secret, missing signature, malformed input, expired, revoked, revocation-file roundtrip, disclosure label presence + HTML escaping, and full CLI end-to-end (issue → verify → revoke → verify).

## Managed follow-up

Need consent workflows, hosted verification, and disclosure compliance across a team? That's what [DisclosureGuard](https://disclosure-guard.onrender.com) does — this kit is the open-source building block; DisclosureGuard is the managed service.

## License

MIT — see [LICENSE](LICENSE). Copyright Ingenious AI.
