# How to hold a migration release in n8n when a 301 becomes a 302

Supply a reference URL map and observed paths from your crawler. Inspect flagged redirects before the release owner signs off.

1. Import [Migration](../workflows/n8n-migration.json) and follow the [connection guide](n8n-setup.md). Use the [fixed demo](../fixtures/migration-observation.json) to see the data shape. This preview costs $0 in report events and always routes to `DEMO_ONLY`.
2. In your customer-owned crawler or export workflow, wait for a complete crawl of the mapped URLs under your authorization. Send one immutable observation with `input.redirectMap` and `input.observations`. You may attach `input.previousObservations` to compare evidence across crawls. The Actor evaluates the traces supplied by the team. The upstream crawler performs the fetching. See the [custom envelope](../fixtures/migration-custom-observation.json).
3. A custom full report requires a Paid account and can purchase **one $2.75 migration-audited event** per completed audit. Set the operator-approved run cap to at least $2.75 when you intend to buy the report. The default $0.01 cap is for the fixed demo.
4. `HOLD_RELEASE` provides findings, source URLs and traces. `READY_FOR_SIGN_OFF` requires complete trace coverage, no flagged URLs, a matching report digest and exactly one event. Pass the report to the release owner for sign-off. Technical failures keep the gate closed.
5. Use a fresh source sequence for a new crawl after remediation. Repeating the previous encounter with the same input uses the journal. Keep protected URLs and crawl evidence in your private systems.

[Migration Redirect Audit](https://apify.com/beyondforge/migration-redirect-audit) · [Audit temporary redirects](https://apify.com/beyondforge/migration-redirect-audit/examples/audit-temporary-redirects-after-migration)
