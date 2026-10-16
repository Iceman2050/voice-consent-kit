"""Tests for voice-consent-kit. Run: python3 -m unittest discover -s tests"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from voiceconsent_pkg.disclosure import render_disclosure
from voiceconsent_pkg.receipts import (issue_receipt, load_revocations,
                                       save_revocations, sign_receipt,
                                       verify_receipt)

SECRET = "test-secret-not-real"


def make_receipt(**kw):
    args = dict(voice_owner="Jane Doe", granted_to="Acme Podcasts",
                scope="podcast narration, EN only", expires="2099-12-31")
    args.update(kw)
    return issue_receipt(secret=SECRET, **args)


class TestIssueVerifyRoundtrip(unittest.TestCase):
    def test_roundtrip_valid(self):
        r = make_receipt()
        res = verify_receipt(r, SECRET)
        self.assertEqual(res["status"], "VALID", res["reasons"])
        self.assertEqual(r["version"], "1.0")

    def test_receipt_has_all_signed_fields(self):
        r = make_receipt()
        for k in ("receipt_id", "voice_owner", "granted_to", "scope",
                  "issued_at", "expires", "signature"):
            self.assertIn(k, r)

    def test_signature_is_deterministic(self):
        r = make_receipt()
        self.assertEqual(sign_receipt(r, SECRET), r["signature"])

    def test_wrong_secret_invalid(self):
        r = make_receipt()
        res = verify_receipt(r, "different-secret")
        self.assertEqual(res["status"], "INVALID")
        self.assertTrue(any("signature" in x for x in res["reasons"]))

    def test_tampered_scope_invalid(self):
        r = make_receipt()
        r["scope"] = "everything, forever"
        res = verify_receipt(r, SECRET)
        self.assertEqual(res["status"], "INVALID")

    def test_tampered_expiry_invalid(self):
        r = make_receipt()
        r["expires"] = "2099-01-01"
        res = verify_receipt(r, SECRET)
        self.assertEqual(res["status"], "INVALID")

    def test_missing_signature_invalid(self):
        r = make_receipt()
        del r["signature"]
        res = verify_receipt(r, SECRET)
        self.assertEqual(res["status"], "INVALID")

    def test_malformed_input_invalid(self):
        res = verify_receipt("not a dict", SECRET)
        self.assertEqual(res["status"], "INVALID")
        res = verify_receipt({"receipt_id": "x"}, SECRET)
        self.assertEqual(res["status"], "INVALID")

    def test_expired_receipt_flagged(self):
        r = make_receipt(expires="2001-01-01")
        res = verify_receipt(r, SECRET)
        self.assertEqual(res["status"], "EXPIRED")
        self.assertTrue(any("2001-01-01" in x for x in res["reasons"]))

    def test_revoked_receipt_flagged(self):
        r = make_receipt()
        res = verify_receipt(r, SECRET, revocations={r["receipt_id"]})
        self.assertEqual(res["status"], "REVOKED")

    def test_revocation_file_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "revocations.json")
            self.assertEqual(load_revocations(path), set())  # missing -> empty
            save_revocations(path, {"abc123"})
            self.assertEqual(load_revocations(path), {"abc123"})

    def test_issue_rejects_bad_input(self):
        with self.assertRaises(ValueError):
            make_receipt(expires="not-a-date")
        with self.assertRaises(ValueError):
            make_receipt(voice_owner="  ")
        with self.assertRaises(ValueError):
            issue_receipt("a", "b", "c", "2099-01-01", secret="")


class TestDisclosure(unittest.TestCase):
    def test_text_contains_label(self):
        out = render_disclosure("Narrator-AI v2", "text")
        self.assertIn("Narrator-AI v2", out)
        self.assertIn("AI", out)

    def test_html_contains_label_escaped(self):
        out = render_disclosure('Evil <script>alert(1)</script>', "html")
        self.assertNotIn("<script>alert(1)</script>", out)
        self.assertIn("&lt;script&gt;", out)
        self.assertIn("AI-generated", out)

    def test_bad_format_rejected(self):
        with self.assertRaises(ValueError):
            render_disclosure("x", "markdown")


class TestCLIEndToEnd(unittest.TestCase):
    """Full CLI: issue -> file -> verify -> revoke -> verify."""
    def run_cli(self, *args, cwd, env_extra=None):
        env = dict(os.environ)
        env.pop("VOICE_CONSENT_SECRET", None)
        env.update(env_extra or {})
        return subprocess.run(
            [sys.executable, "voiceconsent.py", *args],
            cwd=cwd, env=env, capture_output=True, text=True, timeout=30)

    def test_cli_flow(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with tempfile.TemporaryDirectory() as d:
            env = {"VOICE_CONSENT_SECRET": SECRET,
                   "PYTHONPATH": root + os.pathsep + os.environ.get("PYTHONPATH", "")}
            r = self.run_cli("issue", "--voice-owner", "Jane Doe",
                             "--granted-to", "Acme", "--scope", "ads",
                             "--expires", "2099-06-30",
                             "-o", "receipt.json", cwd=root, env_extra=env)
            self.assertEqual(r.returncode, 0, r.stderr)
            with open(os.path.join(root, "receipt.json")) as f:
                rid = json.load(f)["receipt_id"]
            # verify against the temp-dir blocklist (empty)
            v = self.run_cli("verify", "--receipt", "receipt.json",
                             "--revocations", os.path.join(d, "rev.json"),
                             cwd=root, env_extra=env)
            self.assertEqual(v.returncode, 0, v.stdout + v.stderr)
            self.assertIn("VALID", v.stdout)
            # revoke then re-verify -> REVOKED, exit 1
            rv = self.run_cli("revoke", "--receipt-id", rid,
                              "--revocations", os.path.join(d, "rev.json"),
                              cwd=root, env_extra=env)
            self.assertEqual(rv.returncode, 0, rv.stderr)
            v2 = self.run_cli("verify", "--receipt", "receipt.json",
                              "--revocations", os.path.join(d, "rev.json"),
                              cwd=root, env_extra=env)
            self.assertEqual(v2.returncode, 1)
            self.assertIn("REVOKED", v2.stdout)
            os.remove(os.path.join(root, "receipt.json"))

    def test_cli_disclosure(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        r = self.run_cli("disclosure", "--format", "text",
                         "--voice-label", "Studio Voice", cwd=root)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Studio Voice", r.stdout)

    def test_cli_requires_secret(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        r = self.run_cli("issue", "--voice-owner", "a", "--granted-to", "b",
                         "--scope", "c", "--expires", "2099-01-01", cwd=root)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("secret", (r.stdout + r.stderr).lower())


if __name__ == "__main__":
    unittest.main()
