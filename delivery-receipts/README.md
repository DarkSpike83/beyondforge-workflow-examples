# Read an existing BeyondForge delivery

A purchasing team can review a supplier's completed comparison again without starting another Actor. The same pattern lets a document team keep the page behind a citation, or an Italian procurement office check why a register search ended. All examples start with synthetic data. Keep your own job identifiers, results and credentials in your private instance.

## n8n

Import one of these inactive JSON files into an empty workflow and run it manually with its demonstration data. Each workflow is bound to one BeyondForge Actor and its immutable Apify Actor ID.

| Workflow | What the customer receives |
|---|---|
| [Albo Gestori Ambientali](n8n/albo-gestori-ambientali.json) | Il numero di record e regioni controllati. Il raggiungimento del limite richiede una valutazione della copertura. [Guida italiana](../field-guides/albo-gestori-ambientali.md) |
| [PDF Text Pages](n8n/pdf-text-pages.json) | The page and document length associated with the delivered text. [PDF guide](../field-guides/pdf-text-pages.md) |
| [HTML Markdown Batch](n8n/html-markdown-batch.json) | The delivered Markdown, including table structure. [HTML guide](../field-guides/html-markdown-batch.md) |
| [JSON CSV Export](n8n/json-csv-export.json) | The delivered CSV and row count, preserving headers, line breaks and zero stock. [JSON guide](../field-guides/json-csv-export.md) |

**Connecting private data.** The two source nodes use separate synthetic constants in the example. For a real job the customer must replace **both** sources. Keep each node's name, which the review node uses to select the matching execution.

1. In **Trusted job reference**, load exactly one `expectedRunId` from your own protected job journal for the business operation being reviewed. Use the ID saved from the authenticated launch response or reconciled previously in your Apify Console. This node must be controlled by your organization and unable to accept replacement IDs from a delivery or webhook.
2. Replace **Synthetic receipt** with a private reader. Read that specific run by HTTPS from the official Apify API using your own scoped connection. Populate `runId`, `actId` and `status` from the authenticated run's `data.id`, `data.actId` and `data.status`. Resolve the Actor slug from trusted configuration. Obtain `rows` only from that run's default dataset, or the Albo `summary` from its default key-value store. Reconcile paging, row counts and completion before projecting a complete delivery. If the job reference is missing, ambiguous or no longer matches the provider's result, stop. [Apify run details](https://docs.apify.com/api/v2/actor-run-get) · [Default dataset](https://docs.apify.com/api/v2/default-dataset)
3. **Read delivered fields** requires one independent job reference, one receipt, the immutable ID and slug for this particular workflow, matching run ID and a successful terminal status. The checks detect integration mistakes. Authenticating the upstream response requires the private API reader above. Never derive the reference and the delivery from a single untrusted payload. A later database insert or notification needs its own replay protection.

The examples perform no network requests or writes. We executed the exported JavaScript locally under Node.js, including all twelve cross-Actor receipt combinations, independent job references, invalid deliveries and replay. Run the regression suite with `node --test delivery-receipts/tests/test-receipts.cjs` from the repository root. This release has no full-engine n8n or Apify cloud test for these four new workflows. [n8n workflow import](https://docs.n8n.io/workflows/export-import/) · [Access other nodes’ output](https://docs.n8n.io/code/builtin/output-other-nodes/)

## Make Supplier

Import the [passive Supplier blueprint](make/supplier-receipt-review.blueprint.json) into an empty private scenario. Keep scheduling disabled. The [synthetic receipt](make/synthetic-receipt.json) is a completed preview with zero commercial events; its expected classification is `DEMO_ONLY`. A buyer can use the classifier after an authorized upstream process has verified the run identity, same supplier, report completeness and event counts. A report with recorded exceptions requires review. The classifier has no Apify connection or purchase-order action. The actor charges USD 0.85 for a completed custom Paid comparison, including an unchanged result. Manual Make operations consume plan credits. [Supplier guide](../field-guides/supplier-catalog-reconciliation.md) · [Make blueprints](https://help.make.com/blueprints)

## Zapier Supplier

The [two-step mapping worksheet](zapier/supplier-receipt-mapping.json) shows a finished Supplier Actor run followed by reading `RUN_SUMMARY` from the default key-value store of that same run. This JSON describes an editor configuration. It does not install a Zap or start an Actor. Confirm the official Apify connector exposes the required fields in your plan and use only your own private connection. Replaying an event can consume a Zapier task for another read. Keep the Zap off during configuration. The synthetic examples include no real customer IDs. [Apify's Zapier integration](https://docs.apify.com/integrations/zapier)

These integration examples are covered by the repository's [MIT license](../LICENSE). BeyondForge's commercial Actors have their own pricing and terms. Our original Make mapping tests covered 15 local synthetic cases; our original Zapier mapping used two local reads of the same synthetic event. Neither test establishes end-to-end cloud Paid coverage.
