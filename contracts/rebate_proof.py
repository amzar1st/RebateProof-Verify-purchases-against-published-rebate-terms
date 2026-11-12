# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *
import hashlib
import json
import re

HTTPS = r"https://[a-z0-9]+(?:[.-][a-z0-9]+)+(?::443)?(?:/[A-Za-z0-9_.-]+)+"
TOKEN = r"[A-Z0-9][A-Z0-9-]{0,39}"
MAX_BYTES = 8192


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def check_hash(value):
    assert re.fullmatch(r"[0-9a-f]{64}", value), "Expected lowercase SHA-256"


def check_url(value, prefix=False):
    assert type(value) is str and len(value) <= 400, "Invalid evidence URL"
    path = value[:-1] if prefix and value.endswith("/") else value
    assert re.fullmatch(HTTPS, path), "Expected a plain HTTPS URL"
    assert all(segment not in (".", "..") for segment in path.split("/")[3:]), "Invalid path"
    assert not prefix or value.endswith("/"), "Expected a directory URL ending in /"


def check_date(value):
    assert type(value) is str and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value), "Invalid date"
    year, month, day = map(int, value.split("-"))
    assert 1 <= year <= 9999 and 1 <= month <= 12, "Invalid date"
    leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    days = (31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    assert 1 <= day <= days[month - 1], "Invalid date"


def check_token(value):
    assert type(value) is str and re.fullmatch(TOKEN, value), "Invalid identifier"


def check_policy(policy):
    assert type(policy) is dict and set(policy) == {
        "title", "currency", "start", "end", "sellers", "listing_prefix", "models"
    }, "Invalid policy schema"
    assert type(policy["title"]) is str and 1 <= len(policy["title"]) <= 100, "Invalid title"
    assert type(policy["currency"]) is str and re.fullmatch("[A-Z]{3}", policy["currency"]), "Invalid currency"
    check_date(policy["start"])
    check_date(policy["end"])
    assert policy["start"] <= policy["end"], "Invalid purchase window"
    check_url(policy["listing_prefix"], True)
    assert type(policy["sellers"]) is dict and 1 <= len(policy["sellers"]) <= 20, "Invalid seller list"
    for seller, prefix in policy["sellers"].items():
        check_token(seller)
        check_url(prefix, True)
    assert type(policy["models"]) is dict and 1 <= len(policy["models"]) <= 50, "Invalid model list"
    for model, amount in policy["models"].items():
        check_token(model)
        assert type(amount) is int and 0 < amount <= 100000000, "Invalid rebate in minor units"


def object_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def download(url, expected):
    response = gl.nondet.web.get(url)
    body = response.body
    if response.status != 200 or len(body) > MAX_BYTES or digest(body) != expected:
        return None
    return json.loads(body.decode("utf-8"), object_pairs_hook=object_fields)


def check_receipt(receipt):
    assert type(receipt) is dict and set(receipt) == {
        "receipt_id", "buyer", "seller", "model", "purchase_date"
    }
    check_token(receipt["receipt_id"])
    check_token(receipt["seller"])
    check_token(receipt["model"])
    check_date(receipt["purchase_date"])
    assert type(receipt["buyer"]) is str and re.fullmatch("0x[0-9a-f]{40}", receipt["buyer"])


def evaluate(policy, claim, receipt, listing):
    check_receipt(receipt)
    assert type(listing) is dict and set(listing) == {"model"}
    check_token(listing["model"])
    model = receipt["model"]
    seller = receipt["seller"]
    purchase_date = receipt["purchase_date"]
    clauses = {
        "1.model": model in policy["models"],
        "2.purchase_window": policy["start"] <= purchase_date <= policy["end"],
        "3.approved_seller": policy["sellers"].get(seller) == policy["sellers"][claim["seller"]],
        "4.listing_match": listing["model"] == model,
    }
    clauses["3.approved_seller"] = clauses["3.approved_seller"] and seller == claim["seller"]
    if receipt["buyer"] != claim["buyer"]:
        return {"status": "INCONCLUSIVE", "reason": "RECEIPT_BUYER_MISMATCH", "rebate_minor": 0}
    eligible = all(clauses.values())
    return {
        "status": "ELIGIBLE" if eligible else "INELIGIBLE",
        "model": model, "listing_model": listing["model"], "seller": seller,
        "purchase_date": purchase_date, "clauses": clauses,
        "receipt_id": receipt["receipt_id"], "currency": policy["currency"],
        "rebate_minor": policy["models"][model] if eligible else 0,
    }


class RebateProof(gl.Contract):
    policies: TreeMap[str, str]
    claims: TreeMap[str, str]
    used_receipts: TreeMap[str, str]

    def __init__(self):
        pass

    @gl.public.write
    def lock_policy(self, policy_url: str, policy_sha256: str) -> str:
        check_url(policy_url)
        check_hash(policy_sha256)
        sponsor = gl.message.sender_address.as_hex.lower()
        policy_id = digest(canonical([sponsor, policy_url, policy_sha256]).encode())
        assert policy_id not in self.policies, "Policy already locked"

        def fetch_policy():
            policy = download(policy_url, policy_sha256)
            check_policy(policy)
            return canonical(policy)

        policy = gl.eq_principle.strict_eq(fetch_policy)
        self.policies[policy_id] = canonical({
            "id": policy_id, "sponsor": sponsor, "url": policy_url,
            "sha256": policy_sha256, "rules": json.loads(policy),
        })
        return policy_id

    @gl.public.write
    def submit_claim(self, policy_id: str, seller: str, receipt_url: str,
                     receipt_sha256: str, listing_url: str, listing_sha256: str) -> str:
        assert policy_id in self.policies, "Unknown policy"
        policy = json.loads(self.policies[policy_id])["rules"]
        check_token(seller)
        assert seller in policy["sellers"], "Seller has no trusted receipt directory"
        check_url(receipt_url)
        check_url(listing_url)
        assert receipt_url.startswith(policy["sellers"][seller]), "Receipt outside approved directory"
        assert listing_url.startswith(policy["listing_prefix"]), "Listing outside approved directory"
        check_hash(receipt_sha256)
        check_hash(listing_sha256)
        buyer = gl.message.sender_address.as_hex.lower()
        claim_id = digest(canonical([buyer, policy_id, receipt_sha256, listing_sha256]).encode())
        assert claim_id not in self.claims, "Claim already exists"
        self.claims[claim_id] = canonical({
            "id": claim_id, "policy_id": policy_id, "seller": seller, "buyer": buyer,
            "receipt_url": receipt_url, "receipt_sha256": receipt_sha256,
            "listing_url": listing_url, "listing_sha256": listing_sha256,
            "decision": {"status": "SUBMITTED"}, "attempts": 0,
        })
        return claim_id

    @gl.public.write
    def review_claim(self, claim_id: str) -> str:
        assert claim_id in self.claims, "Unknown claim"
        claim = json.loads(self.claims[claim_id])
        record = json.loads(self.policies[claim["policy_id"]])
        caller = gl.message.sender_address.as_hex.lower()
        assert caller in (claim["buyer"], record["sponsor"]), "Only claimant or sponsor can review"
        assert claim["decision"]["status"] in ("SUBMITTED", "INCONCLUSIVE"), "Decision already recorded"
        assert claim["attempts"] < 3, "Review limit reached"

        def review():
            try:
                receipt = download(claim["receipt_url"], claim["receipt_sha256"])
                listing = download(claim["listing_url"], claim["listing_sha256"])
                decision = evaluate(record["rules"], claim, receipt, listing)
            except Exception:
                decision = {"status": "INCONCLUSIVE", "reason": "EVIDENCE_UNAVAILABLE_OR_INVALID",
                            "rebate_minor": 0}
            return canonical(decision)

        decision = json.loads(gl.eq_principle.strict_eq(review))
        if decision["status"] == "ELIGIBLE":
            receipt_key = digest(canonical([
                record["sponsor"], claim["seller"], decision["receipt_id"]
            ]).encode())
            if receipt_key in self.used_receipts:
                decision["status"] = "DUPLICATE_RECEIPT"
                decision["rebate_minor"] = 0
            else:
                self.used_receipts[receipt_key] = claim_id
        claim["attempts"] += 1
        claim["decision"] = decision
        claim["decision_sha256"] = digest(canonical([
            claim_id, claim["attempts"], decision
        ]).encode())
        self.claims[claim_id] = canonical(claim)
        return claim["decision_sha256"]

    @gl.public.view
    def get_policy(self, policy_id: str) -> str:
        return self.policies[policy_id] if policy_id in self.policies else ""

    @gl.public.view
    def get_claim(self, claim_id: str) -> str:
        return self.claims[claim_id] if claim_id in self.claims else ""
