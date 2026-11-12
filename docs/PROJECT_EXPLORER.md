# Project Explorer submission

| Field | Suggested entry |
| --- | --- |
| Contribution type | Builder → Projects |
| Project name | RebateProof |
| Application date | 2026-11-12 |
| Primary tag | Real-World Data, or the closest available category |
| Secondary tags | Oracles, Consumer Verification, if available under the selected category |
| One-liner | Verify redacted purchases against locked rebate terms and show the exact clause behind each GenLayer decision. |
| Repository | https://github.com/amzar1st/RebateProof-Verify-purchases-against-published-rebate-terms |
| Frontend | https://rebateproof.tinymule33.chatgpt.site |
| Contract | https://explorer-studio.genlayer.com/address/0x6FaD6B937A12baA48F1888433cfC9867D2cC85D5 |
| Supporting evidence | https://github.com/amzar1st/RebateProof-Verify-purchases-against-published-rebate-terms/blob/main/docs/LIVE_VERIFICATION.md |

## Description

RebateProof gives buyers and sponsors an auditable answer to rebate disputes. A sponsor locks a published policy by SHA-256. A buyer submits a hash-pinned, redacted receipt and product listing. GenLayer validators independently fetch the evidence from approved directories and agree on clause-level checks for the exact model, purchase window, seller, and listing match. The contract computes the rebate in integer minor units, binds the receipt to the buyer, and blocks repeat redemption of eligible receipts across that sponsor's policy versions. The public dashboard reads finalized StudioNet state and tracks transactions signed with Studio's built-in account. The live demo compares two nearly identical heat pumps: AER-2400-PRO qualifies for $150, while AER-2400 fails the exact-model clause.
