# BeyondForge field guides

Each guide includes an input, an illustrated example, a public task and a read-only API request. Choose the result you need, then review the Actor’s price before starting a run. The field guides contain demonstration data. The Italian registry example uses a public corporate name and stores no registration records.

- [Verifica iscrizione Albo Gestori Ambientali prima dell’affidamento](albo-gestori-ambientali.md) — Cerca un’impresa negli elenchi dell’Albo per nome e sezione. Un esempio per chi qualifica fornitori e vuole risalire alle categorie restituite dalla fonte ufficiale.
- [Google Shopping XML feed validator for the last check before upload](merchant-feed-preflight.md) — Catch a sale price higher than the regular price in a Google Merchant Center XML feed. Use the SKU finding to decide whether an agency should hold the upload.
- [RSS feed monitoring for headline corrections under the same GUID](rss-revision-ledger.md) — Compare two RSS snapshots with the same GUID, identify an edited headline and send an actionable correction to the newsroom’s review queue.
- [Use a PDF to text API to preserve a page reference in a handoff](pdf-text-pages.md) — Extract a cited page from a text-layer PDF and retain its page number when handing document text to search, operations or editorial review.
- [Convert HTML table to Markdown for a release handoff](html-markdown-batch.md) — Turn a two-row release checklist inside an HTML article into a Markdown table that a documentation team can paste into its release notes.
- [Nested JSON to CSV with a stable warehouse handoff](json-csv-export.md) — Flatten nested inventory records into a predictable two-column CSV and preserve zero stock for downstream warehouse imports.
- [Price list comparison for two exports from the same supplier](supplier-catalog-reconciliation.md) — Compare the last accepted supplier catalog against its replacement by SKU, so a buyer can review price increases and decreases before import.
- [301 redirect mapping checks when the wrong destination returns 200](migration-redirect-audit.md) — Compare planned 301 redirect targets with recorded crawl evidence. Catch migrations that return HTTP 200 on the wrong page before sign-off.

## Use with an AI agent

Connect your MCP client to the [discovery-only Apify endpoint](https://mcp.apify.com?tools=search-actors,fetch-actor-details). Paste the prompt in the guide to inspect the tool and its current schema. The sample commands perform GET requests. To try a task, review its prefilled input and pricing in your own account. A free-plan example can still consume usage credit where the Actor lists a start or result event.

The repository’s [MIT license](https://github.com/DarkSpike83/beyondforge-workflow-examples/blob/b1f4e02e15d5c4be0cbe7b45f626dbd82ba423fa/LICENSE) applies to these example materials. BeyondForge operates the Actors separately on Apify. [Apify MCP documentation](https://docs.apify.com/mcp) · [Actor API documentation](https://docs.apify.com/api/v2/act-get)
