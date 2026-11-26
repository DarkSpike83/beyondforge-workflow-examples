# BeyondForge workflow examples for e-commerce, publishing and SEO

Before the next Google Merchant Center upload, give your catalog team a list of offer IDs with invalid prices, availability values or GTIN check digits. This repository also includes an RSS feed monitoring workflow for editorial corrections and a redirect mapping tool integration for an agency's migration sign-off.

| Tutorial | BeyondForge Actor and public example | Local fixture result |
|---|---|---|
| [Run a Google Merchant Center feed validator before upload](tutorials/01-merchant-feed-before-upload.md) | [Merchant Feed Preflight](https://apify.com/beyondforge/merchant-feed-preflight) · [XML feed example](https://apify.com/beyondforge/merchant-feed-preflight/examples/validate-google-merchant-xml-feed) · [GTIN example](https://apify.com/beyondforge/merchant-feed-preflight/examples/validate-gtin-check-digits) | A sale price above the regular price returns `HOLD_EXPORT` and the affected SKU. |
| [Set up RSS feed monitoring for edits to published entries](tutorials/02-rss-corrections-with-checkpoints.md) | [RSS Revision Ledger](https://apify.com/beyondforge/rss-revision-ledger) · [Headline correction example](https://apify.com/beyondforge/rss-revision-ledger/examples/detect-rss-title-edits) | A revised title returns `REVIEW_CHANGES`. The next identical capture returns `UNCHANGED`. |
| [Use a redirect mapping tool to catch migration regressions](tutorials/03-migration-release-gate.md) | [Migration Redirect Audit](https://apify.com/beyondforge/migration-redirect-audit) · [Temporary redirect example](https://apify.com/beyondforge/migration-redirect-audit/examples/audit-temporary-redirects-after-migration) | A 301 becoming a 302 keeps the release on hold. A synthetic preview yields `DEMO_ONLY`. |

## For agencies handling 1,000–5,000 offers

Run the Merchant check when your commerce platform finishes a daily or intraday export. Use a separate private workspace per client, an immutable export ID and an expected count of distinct offers. Start with a small sample of your own offers. The Free plan delivers up to 25 inline audits per run. Paid callers can request up to 5,000 and can use an authorized direct HTTPS XML feed. Set the maximum result count to cover the intended export.

At the listed default rate, a completed check of 1,000 distinct offers costs $0.90 in offer events, or $4.50 for 5,000. Add the platform start charge of $0.00005 at default memory per run. Repeated exports are separate runs. Choose an explicit per-run cap and check the current listing before scheduling checks on your own account.

If your buyer also receives a fresh catalog from a supplier, compare two authorized versions of that **same supplier's** list before promoting new prices and stock into the store. [Supplier Catalog Reconciliation](https://apify.com/beyondforge/supplier-catalog-reconciliation) · [Compare supplier prices by SKU](https://apify.com/beyondforge/supplier-catalog-reconciliation/examples/supplier-price-comparison-by-sku)

## Run locally

With Python 3.10+ and Node.js 18+, run these commands in this directory.

```sh
python -B -m unittest discover -s workflows -p test_workflows.py
node workflows/test_n8n.mjs
```

The tests use synthetic inputs and run offline. To try the n8n example, import `workflows/n8n-migration-gate.json` with **Import from File**. Its **From customer workflow** branch accepts a verified routing object from your worker. Validation covered the workflow JSON and node JavaScript locally. An actual n8n import, production Make or Zapier runs, and a Paid cloud run of these integrations are unverified. [n8n import instructions](https://docs.n8n.io/workflows/export-import/)

Each tutorial separately describes an optional actual call. Use an authorized customer's account, a durable restricted local directory, private secret storage and an explicit per-run spending limit. Confirm prices, account eligibility and retention in the linked Store page before connecting real business data. See the migration tutorial before buying a full report. Reuse an operation ID for a retry of the same observation. Separate organizations physically and keep results out of source control.

When a submission reply is lost before a run ID is known, the worker freezes that scope. Reconcile the corresponding run and charges in your account before clearing the ambiguity. An earlier operation may have completed even if the worker did not receive its response. Keep serial ownership of each scope and back up the private SQLite journal. The scripts do not start schedules or buy services.

## About BeyondForge

BeyondForge publishes the hosted Actors linked above. This repository contains their customer-side integrations, synthetic examples and guides.

## License

You can use, adapt and distribute the contents of this repository commercially under the [MIT License](LICENSE). Keep its copyright and permission notice with copies or substantial portions. The license covers only the files distributed here. The separately hosted BeyondForge Actor implementations, service terms and commercial brand are outside its scope.
