# RSS feed monitoring for corrections to published RSS and Atom entries

A syndication team may already have sent a headline to subscribers when a publisher corrects it. A workflow that only looks for an unfamiliar RSS GUID or Atom entry ID will miss this edit. Compare each successfully retrieved feed with the last verified snapshot, then deliver only new or edited entries to the editorial queue.

This tutorial was prepared with AI assistance and checked against synthetic fixtures. The publisher develops RSS Revision Ledger.

## Try the same-GUID case

Open `examples/rss-edit.json`. Its two small RSS documents use the same channel link and item GUID. The title changes from “First deadline” to “Updated deadline”. Run the bundled Python tests locally. The example produces one `edited` row with `changedFields: ["title"]`. Comparing the unchanged next capture to the saved checkpoint produces zero change rows. [RSS Revision Ledger](https://apify.com/beyondforge/rss-revision-ledger)

```sh
python -B -m unittest discover -s workflows -p test_workflows.py
```

## Keep the baseline private

Use a separate private directory per organization and a stable scope per feed. For example, name this feed `bulletins`. Give each capture an immutable operation ID from the publisher's update event or your existing scheduler. The worker saves the output and the new checkpoint together after a complete comparison.

With Python 3.10+, a private directory named `private`, and your own `CUSTOMER_APIFY_TOKEN` in the runtime secret store, these two commands start two real runs on your account. Each uses a $0.02 cap. They leave the optional paid receipt disabled.

```sh
python workflows/run_workflow.py rss --workspace ./private --scope bulletins --operation capture-01 --input examples/rss-edit.json --max-usd 0.02 --accept-cloud-run
python workflows/run_workflow.py rss --workspace ./private --scope bulletins --operation capture-02 --input examples/rss-next.json --max-usd 0.02 --accept-cloud-run
python workflows/export_result.py rss --workspace ./private --scope bulletins --operation capture-01 --output ./private/correction-01.json
```

Route `REVIEW_CHANGES` to your editor. Use the feed scope, capture ID and row ID together to prevent duplicate downstream notifications. `UNCHANGED` means that all entries in the nonempty observed window stayed the same. `FEED_WINDOW_CHANGED` means entries left that window without another entry being added or edited. `EMPTY_FEED` records a valid empty observation with no prior entries. A missing checkpoint or an incomplete run stops the workflow, so a budget-limited delivery cannot erase an unreported correction.

Process captured snapshots in observation order. When a publisher delivers webhook events out of order, use its monotonic sequence or your pipeline's assigned capture sequence to discard older observations before submitting them. The worker deduplicates an operation ID, but an ID by itself cannot establish capture order.

For professional use, point the same worker at an authorized publisher's feed. Eligible paying callers may use a direct public HTTPS `feedUrl` with `authorizedFetch: true`. For protected feeds use your existing authorized fetch step and hand over inline XML. Omit `previousXml` once a checkpoint exists. An item falling out of a rolling feed window does not establish that its publisher deleted it. The client stores its state on the customer worker's private durable volume. [Same-GUID headline demonstration](https://apify.com/beyondforge/rss-revision-ledger/examples/detect-rss-title-edits)

