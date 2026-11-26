# Webhook idempotency when a paid API call times out

A shop sends the same catalog export to an automation twice. If the workflow starts a paid job both times, the customer may pay twice even if the final spreadsheet contains only one row. Removing duplicate rows protects the spreadsheet. To protect the customer’s budget, decide whether this export may start a job *before* sending the request.

I work on BeyondForge, which publishes the hosted Merchant Feed Preflight Actor on Apify. Here is a test from our public integration that you can reproduce with one invented SKU. The workflow and fixture are free. Calling the hosted Actor uses your Apify account and its published rates.

## Give each completed export a stable identity

Use an export sequence supplied by the source, with a separate scope for each organization and feed. Both deliveries of the same export must retain that sequence. A timestamp generated upon receipt gives each retry a new identity. A byte-for-byte hash can catch a repeated payload, but it cannot distinguish two intentionally separate snapshots that happen to contain the same offers.

Before the first network call, record the scope, sequence and pending state in storage controlled by that organization. Two workers may read the same old state. Only the one that successfully saves a conditional claim may start the job. Our published n8n example uses a private GitHub file whose current SHA is required for an update. A worker that loses the race stops and rereads the record.

## A timeout leaves two possible histories

Imagine the service accepted the request and the connection broke on the trip back. From the caller’s perspective this looks just like a request that never arrived. Restarting immediately could buy the job twice. Here is how the operator decides what to do.

| Private journal | Next action |
|---|---|
| Pending, with a confirmed run ID | Read that run. If it is still running, check the same ID again within a bounded time window. |
| Pending, with no confirmed run ID | Hold the export. Inspect the customer’s service history. Attach a run only if its identity can be established. Escalate unresolved cases to the operator. |
| Complete | Reuse the previous delivery. If a downstream notification failed, retry that handoff with the original run ID. |

This design accepts delayed processing when the network loses the receipt. That is a deliberate choice for an operation that can incur a charge.

## Try the incorrect sale price

The synthetic export contains `MUG-RED` with a regular price of USD 14.50 and a sale price of USD 16.00. Expect one distinct offer ID in the output. If the dataset has fewer offers than the source, stop for reconciliation even if the hosted job reports success.

In the test, the real Apify call returned one offer with a `SALE_PRICE` finding. The workflow decision was `HOLD_EXPORT`. Replaying the same sequence returned `DUPLICATE_SKIP` and started no additional job. A corrected catalog gets a fresh export sequence. The shop still decides what to correct and when to upload it.

We tested the decision nodes against the real API with a local private journal. The separate n8n engine tests used mock services. This evidence covers the one-offer inline case. It does not establish a cloud Paid-account outcome or approval by Google Merchant Center. The public setup guide describes how to bind customer credentials and keep each organization’s journal private. [Reproduce the fixture](https://github.com/DarkSpike83/beyondforge-workflow-examples/blob/main/n8n/tutorials/n8n-merchant.md) · [Recover an ambiguous start](https://github.com/DarkSpike83/beyondforge-workflow-examples/blob/main/n8n/tutorials/n8n-setup.md)

BeyondForge maintains this integration. Generative AI helped prepare this guide from the published workflow and a documented synthetic test.
