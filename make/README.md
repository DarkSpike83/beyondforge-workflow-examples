# Google Merchant feed validator for Make

Use this integration when your shop or agency exports an updated catalog before sending it to Google Merchant Center. It checks a fixed snapshot, compares the returned product IDs with the export and sends Make a small receipt. A price error on one product can hold the entire export for review. Your team decides whether to upload it.

The Python client runs on **your own persistent runner** and starts [Merchant Feed Preflight](https://apify.com/beyondforge/merchant-feed-preflight). Make receives and stores its verified decision. The catalog remains in the systems that perform the audit. The Make receipt contains hashed identifiers, counts and a decision. Keep the working directory and the hosted Actor’s dataset private. Run one journal per organization on durable local storage and restrict access to its service account. Back it up consistently, including any SQLite sidecar files. Restoring an old journal may forget a previously billed run. Reconcile recent runs before enabling the restored launcher.

## Try the offline example

Use Python 3.10 or later. From this directory, run:

```sh
python -m unittest -v test_merchant_make
```

The fixture [sample-offers.json](sample-offers.json) contains one synthetic mug. Its sale price exceeds its regular price. The expected decision is `HOLD_EXPORT`. A catalog that passes the implemented checks produces `READY_FOR_REVIEW`. Google makes its own approval decision. The offline suite uses no provider credentials and makes no billable calls.

## Set up your copy

1. Import [merchant-feed-validation.blueprint.json](merchant-feed-validation.blueprint.json) into an empty Make scenario in your organization. Bind new resources in your copy and keep the scenario inactive until you finish setup.
2. Create a **Custom webhook** with API-key authentication. Define the eight receipt fields in [webhook-schema.json](webhook-schema.json). Set `schema`, `receiptId`, `runRef`, `operationKey` and `decision` as text, and `expected`, `delivered` and `flagged` as numbers. Treat the webhook URL and its key as secrets.
3. Create a **private Data Store**. Use `receiptId` as the record key and bind the six data fields shown in the imported module. Preserve their names and types. A delivery of the same receipt writes the same key. Bind the Webhook Response module, which acknowledges that ID and decision as JSON after storage. Leave sequential processing off for the synchronous response. If you receive Make’s generic “Accepted” response, the client keeps delivery pending.
4. Create an existing private working directory on your persistent runner. Use the same SQLite database for all workers handling this organization and export stream. Avoid synchronizing the journal through shared file folders or using independently copied databases. Keep catalog data, webhooks and logs out of Git.
5. Configure `CUSTOMER_APIFY_TOKEN`, `CUSTOMER_MAKE_WEBHOOK` and `CUSTOMER_MAKE_WEBHOOK_KEY` through your runtime's secret store. The Apify identity must be able to run Merchant and read the run, its dataset and summary. For more than 25 offers, the client also checks the paying status of that same account. Test the inbound webhook with a synthetic receipt in Run once before enabling any production trigger.

When you use an existing **Team Template**, the editor can retain settings from before the import. Open **Set up a template → Show advanced settings**. Set **Process data in order** to **No** for the synchronous response and **Keep data confidential** to **Yes**. In the wizard, prompt for the customer's own webhook and data store and leave **Use as default value** off for both. Save, close, and reopen the template. Check those two settings and both bindings again. If Make still reports an incompatible response configuration, resolve it before publication. Verify in a private scenario by sending a synthetic receipt twice. Both replies must return the same ID and decision, with exactly one record in the data store after replay.

## Audit one immutable export

On a Windows runner that uses the Windows certificate store, install the optional `truststore` package in the same Python environment (`python -m pip install truststore`). The integration can then verify the Apify and Make HTTPS certificates with Windows. If certificate validation fails, correct the trust configuration before retrying. A pending receipt can be delivered separately without starting the Actor again. [Truststore on PyPI](https://pypi.org/project/truststore/)

Pass a JSON object to `--input`. Put the product array in `offers`, as in the sample file. For an RSS catalog, put the complete XML document in the `feedXml` string instead. Each offer needs one explicit product ID. Set `--expected` to the number of distinct IDs in the original export. If your upstream feed is a URL, save a fixed snapshot in your own environment first. An export with duplicate, empty or unsupported IDs is held before dispatch.

The template is free. Hosted runs can incur charges. At the checked price, a start costs USD 0.00005 at 256 MiB and 1,000 delivered offer audits cost USD 0.90. A 5,000-offer export costs USD 4.50005 nominally if all rows are delivered. A single-offer audit costs USD 0.00095 nominally. Make credits are separate. The launcher checks the current Actor identity, rate and budget before starting. [Current Apify pricing](https://apify.com/beyondforge/merchant-feed-preflight/pricing)

The following command starts a real audit on your own account. Create the private `state` directory first. The sample cap is for the one-offer example.

```sh
python merchant_make.py audit --workspace ./state --scope demo-feed --export-id catalog-001 --input sample-offers.json --expected 1 --max-usd 0.01 --accept-cloud-run
```

Send the resulting receipt to your own bound Make scenario:

```sh
python merchant_make.py deliver --workspace ./state --scope demo-feed --export-id catalog-001 --send-to-make
```

Use the same scope, export ID, input and cap after a timeout. Retries with a recorded run ID resume reading. If the start request might have reached Apify but no run ID was saved, the client stops. Reconcile the run and billing in your own Apify Console before proceeding. Deleting the journal or changing the export ID can start a second paid run. A failed Make acknowledgment is recoverable by repeating only `deliver`; it never starts the Actor. A partial result or a different set of IDs keeps the export on hold. Your export process can pass a stable sequence into this same client for each new catalog. No scheduler is installed.

On Make Free the documented allowance is 1,000 credits per month and one 1 MB Data Store. Plan retention or archival for your own receipts before it fills. Make sharing leaves each recipient responsible for binding their own credentials and data structures. [Data Store limits](https://help.make.com/l6du-data-stores) · [Scenario sharing](https://help.make.com/scenario-sharing) · [Webhook idempotency and recovery](../n8n/tutorials/webhook-idempotency.md)
