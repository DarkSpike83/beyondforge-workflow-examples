# Run Merchant feed checks with n8n Data Tables

This pilot uses an isolated self-hosted n8n Community Edition 2.49.7 instance on SQLite per organization. Local integration tests used synthetic Apify responses. Review the release-specific cloud evidence before enabling customer traffic. Merchant Feed Preflight charges for each run start and audited offer at its published rate. [Actor and pricing](https://apify.com/beyondforge/merchant-feed-preflight)

## Connect a new stream

1. Create a private Data Table in the same n8n project as the workflow. Add three string columns named `stream`, `revision` and `payload`. Insert one row for the stream. Use a short lowercase name such as `merchant-catalog`, 40 zero characters for `revision`, and the JSON below for `payload`. Record the table ID and the generated numeric row ID.

   ```json
   {"version":1,"lastSequence":0,"baselineStore":null,"baselineDigest":null,"pending":null}
   ```

2. Import the inactive workflow. In **Configure connection**, enter the fixed table ID, row ID, stream and spending cap. Select the customer's Apify HTTP Header Auth credential on the HTTP nodes. Enter its Authorization Bearer value in n8n's credential editor. Self-hosted JavaScript task runners must allow the standard Node `crypto` module. A Community instance with its own database per customer is the tested isolation design.
3. Send one immutable observation per completed export. Supply its integer `sequence` and original Actor `input`. The default expected predecessor is `sequence - 1`. If numbering has intentional gaps, supply the source's actual `previousSequence`. Use zero for the first observation of a new stream. Out-of-order input waits until the prerequisite observation completes.
4. For Google Merchant Center feed validation, set `expectedOffers` to the distinct SKU count. Inline offers must have unique text IDs. For XML or an authorized versioned feed URL, provide the source's complete list of SKU strings in the outer `expectedIds` field. A held export includes the affected SKU. The accepted budget must cover the published start and offer charges.
5. After checking permissions, source, cap and retention, enable the configured copy. The workflow import creates no schedule. Free import and demonstration terms are separate from the charges of the selected Apify Actor.

For Merchant, the workflow's estimate uses $0.90 per 1,000 offers and $0.00005 per default-memory start. At 1,000 or 5,000 offers, the estimated totals are $0.90005 and $4.50005. A cap specified in whole cents must reach $0.91 or $4.51 respectively. The $0.03 preset is for the small example. Check the effective Store price before choosing the customer's cap.

## Recover a held operation

| Journal state | Recovery |
|---|---|
| Pending operation with a confirmed run ID | Resubmit the same sequence and immutable observation. The workflow reads that run and reconciles its results. |
| Pending operation without a run ID | Stop this stream. Inspect the customer's Apify run history. An accepted start may have lost its network response. Keep the reservation until the owner can establish what happened. |
| Completed journal, downstream delivery unavailable | Recover the verified result from `lastRunId`. Deduplicate delivery at the destination by run ID. |
| Restored or missing database | Reconcile all activity after the backup before enabling another start. Keep the original journal until migration has been reconciled. |

Switching from the private GitHub journal requires stopping the old workflow, resolving pending operations and transferring the last confirmed sequence and baseline. Keep one writer active for each production stream. If you roll back, transfer the latest confirmed state to the original journal before re-enabling its workflow. Check the workflow-specific user pricing and retention settings before sending real data.
