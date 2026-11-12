# RebateProof live verification

Verified on GenLayer StudioNet, chain 61999, on 2026-11-12. Deployment and transactions were signed with the built-in Studio account `0xffE74E2F480173092216096275CdA04AFd4eACbE` in normal full-consensus mode. The demo account served as both sponsor and buyer. The sample issuer and purchases are fictional.

- [Public dashboard](https://rebateproof.tinymule33.chatgpt.site)
- [Deployed contract](https://explorer-studio.genlayer.com/address/0x6FaD6B937A12baA48F1888433cfC9867D2cC85D5)
- [Source-matched deployment commit](https://github.com/amzar1st/RebateProof-Verify-purchases-against-published-rebate-terms/blob/4ee51e94615de848f9a8b58d956ce200183f1126/contracts/rebate_proof.py)
- [Machine-readable verification inputs](../public/deployment.json)

| Operation | Explorer | Finalized result |
| --- | --- | --- |
| Deploy | [Receipt](https://explorer-studio.genlayer.com/tx/0x38faeb7c41aad3c694b38e2ab71b7ba1db6ded0ad116e22877ab6636c191d073) | Contract deployed |
| Lock policy | [Receipt](https://explorer-studio.genlayer.com/tx/0x8de8898515e0c0702889e375da95935182af94159610f1f95f2034c90a39496d) | Northline policy locked |
| Submit AER-2400-PRO | [Receipt](https://explorer-studio.genlayer.com/tx/0xe498571fcb923598a7697f0a74d55027bcc4981e6f3e065aaad040042691416f) | Claim recorded |
| Submit AER-2400 | [Receipt](https://explorer-studio.genlayer.com/tx/0x0e525d48806afcec05c9f13af30eebaaea7e5b38590df1f0322a8f9aa883b2ac) | Claim recorded |
| Review AER-2400-PRO | [Receipt](https://explorer-studio.genlayer.com/tx/0x68d23b128e35fd2a21cf144a58f1a739d9ea0b6b8bae70d76beb9f60789f9d84) | ELIGIBLE, USD 150.00, all four clauses pass |
| Review AER-2400 | [Receipt](https://explorer-studio.genlayer.com/tx/0x0d6d89dce132c2540b0202a56e829ac24ea1bf7dbc633b038f8806c6154d661e) | INELIGIBLE, USD 0.00, clause 1 fails |
| Repeat PRO review | [Receipt](https://explorer-studio.genlayer.com/tx/0x48a2ebff9be25d8078b369213544d86bc7ff4fe48ac85e551026fe55a5ec98ca) | Contract execution fails, original decision remains intact |

## Reproduce the read-only verification

1. Open the public dashboard and select the locked policy, PRO claim, or base-model claim. Each lookup reads finalized StudioNet state.
2. Use the transaction tracker examples to inspect both a successful review and a finalized execution failure. Consensus can finalize an execution failure.
3. To verify independently from a checkout, run `npm ci` and `node scripts/verify-live.mjs`. The verifier compares the deployed bytes to the repository and checks the finalized receipts, model clauses, amounts and decision hashes. The expected source SHA-256 is `d268bc9b3c2bef2303807dff34c4be6daab0ff61aba7a072ac9ca6767edbf9d1`.

## Reproduce with a fresh Studio account

1. Import `contracts/rebate_proof.py` into [Studio](https://studio.genlayer.com/contracts) and deploy in **Normal (Full Consensus)** for a separate sandbox run.
2. Publish copies of the example policy, listing and receipt JSON. Set the policy's issuer directories and use the signing account's lowercase address in the receipt's buyer field. Keep the documents publicly fetchable. Compute SHA-256 over each file's original bytes.
3. Run `lock_policy`, `submit_claim`, and `review_claim` using the respective IDs returned by Studio. Wait for finalization and read the claim. The dashboard can prepare the arguments and track the hashes.

The local suite contains 12 contract tests and 4 frontend transaction-state tests. It covers exact suffixes, date boundaries, issuer paths, buyer binding, unavailable or changed evidence, duplicate receipts, bounded retries, and consensus disagreement.
