# Use a redirect mapping tool to catch 301-to-302 migration regressions

Your release candidate returns a successful final page. That still leaves a question for the SEO lead: did each legacy URL reach the **approved destination**, using the expected kind of redirect? Use the evidence your release pipeline already collects and let a verification step return one decision for the whole migration.

## Start with one regression

In `examples/migration-custom.json`, the approved source is `https://old.example/help` and its destination is `https://new.example/support`. Both the previous and current captures include the final 200 response. The previous hop was 301 and the new hop is 302. The expected result is one fully traced URL, one flagged URL and one source with a newly introduced finding. Your release stays on hold.

Run the local tests or import `workflows/n8n-migration-gate.json` into n8n and press **Execute workflow**. The manual branch is self-contained and uses no credentials or network. Its synthetic decision is `DEMO_ONLY`. This branch lets an agency demonstrate routing without accidentally approving a real release. [Migration Redirect Audit](https://apify.com/beyondforge/migration-redirect-audit)

```sh
python -B -m unittest discover -s workflows -p test_workflows.py
node workflows/test_n8n.mjs
```

## Add the gate to your deployment

Use the release ID and capture ID to form an immutable operation ID. Export the approved URL map and the complete response evidence for each hop, including the terminal URL, from your authorized telemetry. Missing evidence leaves the customer pipeline on hold. The Actor consumes these tables without visiting any of the sites.

First try the fixed temporary-redirect example. The preview requests zero commercial report events. When your eligible paid account is ready to purchase a **$2.75 report**, the command below submits the custom fixture and caps the run at $2.75. Use your own secret store for `CUSTOMER_APIFY_TOKEN` and create the private working directory on your existing worker. [Temporary redirect example](https://apify.com/beyondforge/migration-redirect-audit/examples/audit-temporary-redirects-after-migration)

```sh
python workflows/run_workflow.py migration --workspace ./private --scope docs-site --operation rc-001 --input examples/migration-custom.json --max-usd 2.75 --accept-cloud-run
python workflows/export_result.py migration --workspace ./private --scope docs-site --operation rc-001 --output ./private/route-001.json --routing-only
```

The client checks coverage and the saved report fingerprint. It compares the reported event count and mode against the requested service. Send the routing object into n8n's **From customer workflow** trigger, using Execute Sub-workflow with one JSON item. Then branch on `route`: `HOLD_RELEASE` opens a review, `READY_FOR_SIGN_OFF` allows an authorized human or existing gate to continue, and `DEMO_ONLY` stays outside production. The example executes no deployment. Keep detailed traces in your own restricted storage.

A lost network reply after submission needs care. Resume an operation with its saved run ID. If the submission itself was ambiguous, inspect your Apify run history and reconcile its output and charges before submitting anything again. A newly submitted report is a separate purchase.

Published by the maker of Migration Redirect Audit. This tutorial was prepared with AI assistance and checked against synthetic fixtures.
