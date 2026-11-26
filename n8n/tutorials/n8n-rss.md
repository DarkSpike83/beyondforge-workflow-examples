# How to catch a corrected RSS headline with the same GUID in n8n

Compare a publisher's captured RSS or Atom entries with the last accepted checkpoint. Review the edit once and confirm that the next identical capture produces no new ticket.

1. Import [RSS](../workflows/n8n-rss.json), bind a private source scope using the [connection guide](n8n-setup.md) and inspect the [one-revision fixture](../fixtures/rss-observation.json). This synthetic run can incur a feed-change charge and a platform start.
2. On the first observation pass one `sequence` and either current `input.feedXml` or an authorized `input.feedUrl` with `authorizedFetch: true`. For inline data, an optional `previousXml` establishes the first comparison. Use the same logical feed and its stable identity across captures.
3. On subsequent observations omit `previousXml`. The template loads the previous complete checkpoint and verifies the new checkpoint against the delivered change rows. Use an immutable, ordered capture sequence from your publisher or collector. On a daily parent trigger, reuse the original sequence and XML if retrying that observation.
4. Set the cap and `maxResults` to cover expected changes. Small inline runs are available to Free customers under the Actor's published limits. Direct authorized feed URL acquisition and larger limits require Paid eligibility. The store rate is $1 per 1,000 delivered changes plus $0.00005 per default-memory start. This workflow never opts into the additional paid comparison receipt.
5. `REVIEW_CHANGES` contains the new or edited entries. `UNCHANGED` means the complete non-empty window matched. `FEED_WINDOW_CHANGED` asks an editor to assess entries that fell out of the current feed window. A missing entry alone does not prove deletion from the publisher's site. `EMPTY_FEED` holds the last non-empty baseline. If a read or integrity check fails, recover the same capture using the journal.

[RSS Revision Ledger](https://apify.com/beyondforge/rss-revision-ledger) · [Detect RSS title edits](https://apify.com/beyondforge/rss-revision-ledger/examples/detect-rss-title-edits)
