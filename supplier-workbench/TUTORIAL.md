# Price list comparison by SKU: review one supplier’s stock and cost changes

A retailer receives a new catalog from the same wholesaler each morning. Before updating the shop, the buyer wants to know which products disappeared, which came back in stock and whether a higher price is actually for a larger pack. This example leaves the shop untouched.

## Try the local example

Import [the parent workflow](supplier-export-parent.json) into a private n8n project. Select **Test workflow** at the manual trigger. The sample path prepares the input locally and ends at **Preview the child input**. It makes no external requests. Both lists contain five rows from the fictional Orchard supplier. The exported revision is 2. [Example data](synthetic-export.json)

| SKU | Yesterday → today | Purchasing decision |
|---|---|---|
| OR-01 | Stock 4 → 0 and USD 10 → USD 11 | Pause replenishment and review the increase. |
| OR-02 | Stock 0 → 8 | The item can be offered again after the retailer's approval. |
| OR-03 | USD → EUR | Ask the supplier to confirm the currency before comparing amounts. |
| OR-04 | Box of 6 → box of 12 | Treat this as a packaging exception. A higher box price alone does not establish a unit-cost increase. |
| OR-05 / OR-06 | One SKU disappeared. A different SKU appeared. | Confirm discontinuation and review the new listing separately. |

The existing reconciliation engine produced one occurrence of each of the seven expected findings for this pair. A stockout and a price change can affect the same SKU. [Local result](synthetic-result.json)

## Connect an authorized export

1. Obtain permission to process the supplier's catalog in the retailer's environment and on Apify. Use separate private credentials, storage and workflow copies for each organization and supplier. Remove unrelated columns upstream. If you only have a PDF, paginated API or an unbounded download, first arrange a complete bounded export in the supported format. The example expects one JSON response, and the source must enforce a download size limit. A 15-second timeout alone cannot limit the bytes downloaded into n8n.
2. Bind the private HTTPS URL and header credential in **Read one authorized completed export**. The placeholder domain cannot serve a real supplier. Limit egress to the authorized endpoint. Redirects are disabled. Set its expected supplier ID in **Check retailer supplier binding**. A trigger cannot pass an arbitrary URL, identity, token or destination.
3. The source must publish an immutable positive integer sequence and an independent final row count. A completed export includes `current.supplier`, `current.sequence`, `current.complete: true`, `current.rowCount` and `current.rows`. For the first comparison include the retailer-approved `previous` snapshot from the immediately preceding sequence. Up to 5,000 rows per side are accepted subject to the conservative size check. A partial file, duplicate SKU, empty export or next-page pointer stops the handoff.
4. Import the [published Supplier child](https://github.com/DarkSpike83/beyondforge-workflow-examples/blob/main/n8n/workflows/n8n-supplier.json) and select its private workflow ID in the last node. Configure its private journal, initial revision and Apify credential per supplier. A first pair is for an empty journal and carries `previousSequence: 0`. Later exports omit `previous` and identify the preceding revision. The native journal candidate checks that predecessor before advancing. The published child retrieves the baseline from its previous verified private Apify run. Set private resource sharing and retention to cover the export interval. Missing or expired baseline storage needs manual reconciliation and an approved new baseline.
5. Review billing before enabling a private customer-owned trigger. An eligible custom audit can buy one **USD 0.85** full report, including a clean comparison. The default Actor demos have no report charge. Explicitly set the child's per-run cap and use only a customer's consented events or schedule. Don't schedule this example in the publisher's account. A timeout with a pending run needs reconciliation before any further start.
6. Route the verified child result to a private buyer review queue. Only a confirmed report advances the child's comparison baseline. A clean result, an incomplete run and a report with exceptions have different meanings. Any ERP import or merchandising decision remains with the retailer.

## Can I test my own file first?

Open the [offline format check](own-data-preview.html) in your browser and select one to five representative rows from a normalized catalog. It checks basic formatting locally. The hosted Actor's free previews use six synthetic catalogs. A complete paid audit adds comparison, coverage and recorded results. [Public Actor and pricing](https://apify.com/beyondforge/supplier-catalog-reconciliation) · [Free SKU example](https://apify.com/beyondforge/supplier-catalog-reconciliation/examples/supplier-price-comparison-by-sku)

**Can I compare prices from two competing suppliers?** This workflow expects successive exports from one supplier, matched by exact SKU. Maintain separate streams when a retailer buys from multiple suppliers.

**Does the feed reader apply the changes?** It reads a fixed authorized export and submits a checked comparison. Your buyer reviews the findings before any separate ERP or storefront action.
