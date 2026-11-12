"""Exercise the source with an isolated GenLayer API double."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "public" / "fixtures"
SPONSOR = "0x" + "1" * 40
OTHER = "0x" + "2" * 40
BUYER = "0xffe74e2f480173092216096275cda04afd4eacbe"


class API:
    def __init__(self):
        self.responses = {}
        self.gl = NS(
            Contract=object,
            public=NS(write=lambda fn: fn, view=lambda fn: fn),
            message=NS(sender_address=NS(as_hex=SPONSOR)),
            eq_principle=NS(strict_eq=self.strict_eq),
            nondet=NS(web=NS(get=self.get)),
        )
        self.calls = []

    def strict_eq(self, fn):
        first, second = fn(), fn()
        if first != second:
            raise RuntimeError("Validators disagree")
        return first

    def get(self, url):
        self.calls.append(url)
        return self.responses.get(url, NS(body=b"", status=404))

    def supply(self, url, path=None, value=None):
        body = path.read_bytes() if path else json.dumps(value).encode()
        self.responses[url] = NS(body=body, status=200)
        return hashlib.sha256(body).hexdigest()


class RebateTests(unittest.TestCase):
    def setUp(self):
        self.api = API()
        spec = importlib.util.spec_from_file_location("rebate_proof", ROOT / "contracts/rebate_proof.py")
        self.code = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"genlayer": NS(gl=self.api.gl, TreeMap=dict)}):
            spec.loader.exec_module(self.code)
        self.contract = self.code.RebateProof()
        self.contract.policies = {}
        self.contract.claims = {}
        self.contract.used_receipts = {}
        self.rules = json.loads((FIXTURES / "policy.json").read_text())
        self.policy_url = "https://sponsor.example.com/rebates/policy.json"
        self.policy_hash = self.api.supply(self.policy_url, FIXTURES / "policy.json")
        self.policy = self.contract.lock_policy(self.policy_url, self.policy_hash)
        self.as_sender(BUYER)

    def as_sender(self, wallet):
        self.api.gl.message.sender_address.as_hex = wallet

    def claim_args(self, suffix="pro", listing=None):
        listing = listing or suffix
        receipt_url = self.rules["sellers"]["NORTHLINE"] + suffix + ".json"
        listing_url = self.rules["listing_prefix"] + listing + ".json"
        return [self.policy, "NORTHLINE", receipt_url,
                self.api.supply(receipt_url, FIXTURES / "receipts" / (suffix + ".json")),
                listing_url, self.api.supply(listing_url, FIXTURES / "listings" / (listing + ".json"))]

    def get_claim(self, claim_id):
        return json.loads(self.contract.get_claim(claim_id))

    def test_policy_is_immutable_and_retrieved_by_id(self):
        self.as_sender(SPONSOR)
        with self.assertRaisesRegex(AssertionError, "already locked"):
            self.contract.lock_policy(self.policy_url, self.policy_hash)
        self.assertEqual(json.loads(self.contract.get_policy(self.policy))["rules"], self.rules)

    def test_eligible_and_excluded_suffix(self):
        for variant, outcome, amount in (("pro", "ELIGIBLE", 15000), ("base", "INELIGIBLE", 0)):
            with self.subTest(variant=variant):
                claim = self.contract.submit_claim(*self.claim_args(variant))
                self.assertEqual(self.get_claim(claim)["decision"]["status"], "SUBMITTED")
                reviewed = self.contract.review_claim(claim)
                record = self.get_claim(claim)
                self.assertEqual(record["decision"]["status"], outcome)
                self.assertEqual(record["decision"]["rebate_minor"], amount)
                self.assertEqual(record["decision"]["clauses"]["1.model"], variant == "pro")
                self.assertEqual(record["decision_sha256"], reviewed)
                with self.assertRaisesRegex(AssertionError, "already recorded"):
                    self.contract.review_claim(claim)

    def test_listing_conflict_is_ineligible(self):
        claim = self.contract.submit_claim(*self.claim_args(listing="base"))
        self.contract.review_claim(claim)
        self.assertFalse(self.get_claim(claim)["decision"]["clauses"]["4.listing_match"])

    def test_sender_binding_and_review_permissions(self):
        self.as_sender(OTHER)
        claim = self.contract.submit_claim(*self.claim_args())
        self.as_sender(BUYER)
        with self.assertRaisesRegex(AssertionError, "Only claimant or sponsor"):
            self.contract.review_claim(claim)
        self.as_sender(SPONSOR)
        self.contract.review_claim(claim)
        self.assertEqual(self.get_claim(claim)["decision"]["reason"], "RECEIPT_BUYER_MISMATCH")
        self.assertFalse(self.contract.used_receipts)

    def test_failed_fetch_can_retry_then_recover(self):
        args = self.claim_args()
        claim = self.contract.submit_claim(*args)
        receipt = self.api.responses.pop(args[2])
        self.contract.review_claim(claim)
        self.assertEqual(self.get_claim(claim)["decision"]["status"], "INCONCLUSIVE")
        self.api.responses[args[2]] = receipt
        self.contract.review_claim(claim)
        self.assertEqual(self.get_claim(claim)["decision"]["status"], "ELIGIBLE")
        self.assertEqual(self.get_claim(claim)["attempts"], 2)

    def test_three_invalid_attempts_are_bounded(self):
        args = self.claim_args()
        args[3] = "0" * 64
        claim = self.contract.submit_claim(*args)
        for _ in range(3):
            self.contract.review_claim(claim)
        self.assertEqual(self.get_claim(claim)["decision"]["status"], "INCONCLUSIVE")
        with self.assertRaisesRegex(AssertionError, "Review limit"):
            self.contract.review_claim(claim)

    def test_receipt_id_deduplicated_across_policy_versions(self):
        first = self.contract.submit_claim(*self.claim_args())
        self.contract.review_claim(first)
        self.as_sender(SPONSOR)
        policy_url = self.policy_url.replace("policy.json", "next.json")
        self.policy = self.contract.lock_policy(policy_url, self.api.supply(policy_url, value=self.rules))
        self.as_sender(BUYER)
        second = self.contract.submit_claim(*self.claim_args())
        self.contract.review_claim(second)
        self.assertEqual(self.get_claim(second)["decision"]["status"], "DUPLICATE_RECEIPT")
        self.assertEqual(self.get_claim(second)["decision"]["rebate_minor"], 0)

    def test_receipt_location_enforced_before_web_fetch(self):
        args = self.claim_args()
        for url in ("https://untrusted.example.com/receipts/a.json",
                    args[2].replace("/receipts/", "/receipts/../receipts/"),
                    args[2] + "?redirect=1"):
            with self.subTest(url=url), self.assertRaises(AssertionError):
                bad = args.copy()
                bad[2] = url
                self.contract.submit_claim(*bad)

    def test_purchase_window_boundaries(self):
        for date, expected in (("2026-10-01", True), ("2026-11-30", True), ("2026-12-01", False)):
            with self.subTest(date=date):
                receipt = json.loads((FIXTURES / "receipts/pro.json").read_text())
                receipt["purchase_date"] = date
                result = self.code.evaluate(self.rules, {"seller": "NORTHLINE", "buyer": BUYER},
                                            receipt, {"model": receipt["model"]})
                self.assertEqual(result["clauses"]["2.purchase_window"], expected)

    def test_policy_rejects_boolean_amount_and_impossible_date(self):
        with self.assertRaises(AssertionError):
            self.code.check_policy({**self.rules, "models": {"AER-2400-PRO": True}})
        with self.assertRaises(AssertionError):
            self.code.check_date("2100-02-29")
        self.code.check_date("2000-02-29")

    def test_duplicate_json_keys_are_rejected(self):
        with self.assertRaises(ValueError):
            json.loads('{"model":"A","model":"B"}', object_pairs_hook=self.code.object_fields)

    def test_consensus_disagreement_does_not_mutate_claim(self):
        claim = self.contract.submit_claim(*self.claim_args())
        with patch.object(self.api.gl.eq_principle, "strict_eq", side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                self.contract.review_claim(claim)
        self.assertEqual(self.get_claim(claim)["attempts"], 0)
        self.assertFalse(self.contract.used_receipts)


if __name__ == "__main__":
    unittest.main()
