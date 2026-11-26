# Run a Google Merchant feed validator on XML with Python

Check your Google Merchant Center export for SKU-level GTIN and sale-price issues before upload. The Python example returns affected offer IDs for catalog review.

## Reproduce the case

Use Python 3.10 or later and the accompanying example bundle. From its root, run the local tests. They use synthetic records and make no network calls.

```sh
python -B -m unittest discover -s workflows -p test_workflows.py
```

Open `examples/merchant-offers.json`. It contains one red mug with a regular price of `14.50 USD` and a sale price of `16.00 USD`. The result for `MUG-RED` includes the code `SALE_PRICE`. The client returns `HOLD_EXPORT`. Join the result's `offerId` to the SKU in your catalog, correct the price there, and regenerate the export. The Actor leaves your catalog and your Merchant Center account untouched. [Merchant Feed Preflight](https://apify.com/beyondforge/merchant-feed-preflight)

## Connect a real export

1. Have your commerce platform send its completed-export event to your existing worker. Use the immutable export ID for the operation ID. Use a separate private working directory per customer.
2. For an authorized public HTTPS XML feed on a paying account, configure the worker once with `{"feedUrl":"https://catalog.example/products.xml","authorizedFetch":true,"maxResults":5000}`. Size the batch for 1,000–5,000 offers. Replace the reserved example address with your own direct feed. The remote XML response must fit the 3 MB download limit. URLs with credentials, a query string or redirects are unsupported. For private or larger feeds, let your authenticated exporter supply XML inline within the Actor's 8 MB serialized input limit. Keep private links out of Actor input.
3. Supply your customer token through the worker's secret store as `CUSTOMER_APIFY_TOKEN`. Create the private working directory. The following command starts one actual Actor run on the caller's account. It uses the small synthetic example and a $0.02 cap. Check the Store price and adjust the cap separately for larger exports.

```sh
python workflows/run_workflow.py merchant --workspace ./private --scope goods-eu --operation export-0042 --input examples/merchant-offers.json --max-usd 0.02 --accept-cloud-run
python workflows/export_result.py merchant --workspace ./private --scope goods-eu --operation export-0042 --output ./private/export-0042.json
```

4. Route `HOLD_EXPORT` to the catalog team. Route `EMPTY_CATALOG` to the export owner. `READY_FOR_REVIEW` means the input passed the implemented feed checks. Google still makes the approval decision. A nonzero exit from the client leaves the export on hold. For a running job, resume with the same operation ID, input and budget.

Complete the first integration by checking that the bad sale price holds the synthetic export. Then send the corrected export with a **new** immutable export ID. Compare the delivered count against your expected number of distinct offers before upload. At $0.90 per 1,000 delivered audits and $0.00005 per default-memory start, set a cap covering $0.90005 for 1,000 offers or $4.50005 for 5,000. Set `maxResults` separately to cover the intended export. [Example XML audit](https://apify.com/beyondforge/merchant-feed-preflight/examples/validate-google-merchant-xml-feed)

Published by the maker of Merchant Feed Preflight. This tutorial was prepared with AI assistance and checked against synthetic fixtures.

## Run the same check in n8n

Import the related workflow and use the synthetic observation in the [native n8n guide](../n8n/tutorials/n8n-merchant.md).
