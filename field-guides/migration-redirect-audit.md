# 301 redirect mapping checks when the wrong destination returns 200

Compare planned 301 redirect targets with recorded crawl evidence. Catch migrations that return HTTP 200 on the wrong page before sign-off.

![Migration Redirect Audit — worked example](figures/migration-redirect-audit.png)

## Try the example

1. Start with the approved old-to-new URL mapping and an export of HTTP observations from an authorized crawl. The preview supplies both.
2. Follow the old `/resources` URL. A 301 reaches the new site’s homepage and ends with 200. The plan required `/guides`. Record the wrong destination even though the terminal status is healthy.
3. Fix the redirect in your own website, collect fresh crawl evidence and audit the matching map for release sign-off. Keep separate snapshots if you need regression comparison.

The synthetic example finishes at `https://new.example/` while the expected URL is `https://new.example/guides`. The Actor evaluates supplied observations; acquiring a current crawl remains part of the customer’s release process.

## Plans and charges

The built-in preview uses no `migration-audited` event. Custom maps require Paid. One completed full audit costs USD 2.75, including a clean audit. There is no separate fee per start, URL, hop or anomaly.

**Will it crawl the migrated site or apply redirects?** Supply your planned map and crawl observations. The result helps your team decide what to repair and recheck.

## API and AI agents

This GET reads the public Actor record without starting a run.

```sh
curl --fail --silent --show-error "https://api.apify.com/v2/actors/beyondforge~migration-redirect-audit"
```

In an Apify MCP client, ask

> Use fetch-actor-details for beyondforge/migration-redirect-audit. Show the input schema, output and price so I can review this example. Stop before starting a run.

[Open the wrong-destination preview](https://apify.com/beyondforge/migration-redirect-audit/examples/find-wrong-redirect-destinations) · [Sample input](inputs/migration-redirect-audit.json) · [Apify Store](https://apify.com/beyondforge/migration-redirect-audit) · [Apify MCP](https://docs.apify.com/mcp)

## 301 redirect mapping when the wrong page returns HTTP 200

A visitor opens an old link to a product guide. The server redirects them to the new home page. That page loads perfectly. The redirect still failed the migration plan, which promised the visitor a replacement guide. To catch this before sign-off, compare the **observed final URL** with the **approved destination** for the same old URL.

### Try the four-row exercise

The [approved map](migration-exercise/planned-map.csv) names the destination each page owner signed off. The [crawl export](migration-exercise/observed-redirects.csv) is a synthetic observation from one release. Both files can be opened in a spreadsheet. The reserved example domains contain no customer data. This exercise needs neither a site crawl nor an Apify account.

1. Put the approved map on the first sheet and the crawl export on the second. Use the old URL as the join key. Keep planned rows that have no matching observation.
2. Bring the first status, observed final URL and final status alongside each planned row. Flag duplicate old URLs for manual review before joining. A duplicate with conflicting targets makes the expected destination ambiguous.
3. Compare the three fields for each retained row. A planned permanent move can pass this exercise when the agreed permanent redirect is observed, the intended destination is reached and the final page responds successfully. Use evidence from the same release as the map.
4. If no observation exists, record **evidence missing**. Assign it to whoever owns the authorized crawl. A blank cell tells you nothing about the URL's HTTP status.

| Old path | Approved end | Observed end | Disposition |
|---|---|---|---|
| `/manual` | `/help/manual` | `/help/manual`, 200 after 301 | Pass this mapping check. |
| `/resources` | `/guides` | `/`, 200 after 301 | Hold this row. The home page answered, but the promised guide was never reached. |
| `/catalog` | `/shop` | `/shop`, 404 after 301 | Investigate the destination. The path agrees and the target failed. |
| `/shipping` | `/delivery` | No observation | Request evidence. Leave the status unknown. |

The [answer key](migration-exercise/answer-key.csv) includes a next action for each row. For absolute URLs, preserve scheme, host, path and meaningful query parameters. An apparent match after dropping a host or every query value can hide a redirect to the wrong locale or product variant. Agree on any normalization rule with the page owner and retain the raw strings.

### Decide what to fix and what to retest

For the second row, give the release engineer the old URL, expected target, observed final URL and the observation time. Ask them to correct the rule that sends `/resources` to the home page. Obtain a new authorized crawl export after the change and repeat the comparison against the same approved map. Keep the original failure beside the new result so that the reviewer can see what changed.

A destination match is one release check. The content owner should also confirm that the replacement page is relevant and usable. Check indexing and traffic after launch using evidence appropriate to those separate questions. Google recommends mapping old and new URLs and points out that many irrelevant redirects to a home page may be treated as soft 404s. A 200 alone does not establish how Google classified a particular page. [Google Search Central’s migration guide](https://developers.google.com/search/docs/crawling-indexing/site-move-with-url-changes)

### Optional worked Actor example

BeyondForge publishes the commercial Migration Redirect Audit Actor. The [wrong-destination preview](https://apify.com/beyondforge/migration-redirect-audit/examples/find-wrong-redirect-destinations) supplies a map and observations for a similar case. Its built-in preview incurs no `migration-audited` event. A complete custom audit requires Paid access and costs USD 2.75 once delivered, including a clean result. The Actor evaluates the evidence supplied to it. Your team collects the crawl and controls the site's redirects. The spreadsheet exercise above stands on its own.

This guide was prepared with AI assistance. The example URLs and observations are synthetic.
