# RebateProof

RebateProof gives buyers and rebate sponsors a shared record of why a purchase qualifies. A sponsor locks a published policy. A buyer submits hash-pinned, redacted purchase evidence and a product listing. GenLayer validators independently fetch and validate those documents. The contract applies exact model, purchase window, seller, and listing checks, then calculates the rebate in integer minor units.

- [Public dashboard](https://rebateproof.tinymule33.chatgpt.site)
- [StudioNet contract](https://explorer-studio.genlayer.com/address/0x6FaD6B937A12baA48F1888433cfC9867D2cC85D5)
- [Live verification and transaction links](docs/LIVE_VERIFICATION.md)
- [Project Explorer copy](docs/PROJECT_EXPLORER.md)

## Demo

The fictional Northline campaign includes AER-2400-PRO at USD 150.00. Two claims have the same purchase date and approved seller. The PRO claim passes all four checks. The base model passes the date, seller and listing checks but fails clause 1 because its exact model is absent from the policy.

The dashboard reads finalized records and tracks transaction receipts through the GenLayer JS SDK. Its transaction workspace prepares arguments for signing in GenLayer Studio with the built-in account. It never asks for signing credentials. Open the dashboard and select either claim under **Read a chain record** to inspect the finalized decision.

## Run locally

Requires Node.js 20+ and Python 3.10+.

```sh
npm ci
npm test
npm run build
npm run dev
node scripts/verify-live.mjs
```

The Python tests exercise the deployed source against a local GenLayer API double. The live verifier retrieves network chain ID, deployed source, finalized receipts and the policy and claim state using the SDK.

## Contract

| Method | Behavior |
| --- | --- |
| `lock_policy` | Fetches hash-pinned JSON over HTTPS using strict equivalence and binds the validated policy to the sponsor and digest. |
| `submit_claim` | Binds the claim to the sender, policy, evidence URLs and digests. The policy supplies the approved receipt and listing directories. |
| `review_claim` | Independently retrieves both documents under strict equivalence. Checks their digests, schemas and buyer binding, calculates the clause result, and records a decision hash. |
| `get_policy`, `get_claim` | Return the canonical policy or claim record for a deterministic ID. |

An unavailable, malformed or modified document yields an inconclusive decision if validators agree on that output. The buyer or sponsor can retry the same evidence up to three recorded attempts. A terminal decision locks the claim. Eligible receipt IDs are consumed per sponsor and seller across policy versions.

## Evidence and trust

Publish policy JSON and evidence as small UTF-8 documents under trusted HTTPS directories. Use the example schemas in [public/fixtures](public/fixtures). Policy model keys and seller IDs use exact uppercase identifiers. The purchase window is inclusive and dates use ISO calendar format. Amounts are fixed integers in the currency's minor unit.

The sponsor chooses the source directories. In production, use issuer-controlled endpoints with no untrusted redirects or write access, and use receipt IDs unique within the seller. Each receipt binds its minimal purchase facts to the buyer's public StudioNet address. A hash proves the reviewed bytes match the commitment. Issuer provenance still depends on control of the approved endpoint. The sample fixtures represent a fictional issuer and are intentionally public. Keep personal receipt details, customer names, addresses, payment data and original receipts off-chain.

The contract determines eligibility and amount. Disbursement, settlement, returns, real seller onboarding and cryptographic issuer credentials are outside this version. A production integration can use a seller-controlled endpoint for redacted receipt issuance and consume finalized decisions in the sponsor's payout system.
