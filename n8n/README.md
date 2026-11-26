# Import BeyondForge Apify workflows into n8n

Choose a workflow for catalog feeds, supplier price lists, migration redirects or RSS revisions. Each download includes an offline example and imports as inactive. The templates are free. Running a hosted Actor uses your connected Apify account at its published rates.

| Use case | Import | Guide | First sample |
|---|---|---|---|
| Hold a Google Merchant Center feed with invalid prices or GTINs | [Merchant workflow](workflows/n8n-merchant.json) | [Catalog validation](tutorials/n8n-merchant.md) | [One offer](fixtures/merchant-observation.json) |
| Catch a supplier's price increases, stockouts and SKU changes | [Supplier workflow](workflows/n8n-supplier.json) | [Supplier monitoring](tutorials/n8n-supplier.md) | [Stockout preview](fixtures/supplier-observation.json) |
| Check a website migration against observed redirect chains | [Migration workflow](workflows/n8n-migration.json) | [Release gate](tutorials/n8n-migration.md) | [Migration preview](fixtures/migration-observation.json) |
| Review new or edited RSS and Atom entries | [RSS workflow](workflows/n8n-rss.json) | [Editorial monitoring](tutorials/n8n-rss.md) | [Revised entry](fixtures/rss-observation.json) |

Follow the [private setup and recovery guide](tutorials/n8n-setup.md) before running a sample. The templates require n8n with JavaScript Code nodes, two customer-owned credentials, an Apify account and a private GitHub state repository. The repository stores replay metadata. The customer controls the source data and the private run storage.

To run the offline contract tests, use `node --test tests/test-n8n-contracts.mjs` from this directory. For the full engine test, use Node 24.22.1 with n8n Community Edition 2.49.7 and Python 3. If you need a separate test installation, install `n8n@2.49.7` into a temporary npm prefix **outside** the example repository. Package installation requires network access. The test itself runs against local fixtures. Substitute absolute paths to the Node executable, the installed n8n JavaScript entrypoint, an existing private scratch directory and the desired evidence file.

```sh
python tests/exercise_n8n.py --node <node-executable> --n8n-entry <installed-n8n>/bin/n8n --scratch <private-directory> --evidence <result.json>
```

The engine harness imports the four templates using n8n's Server CLI. It executes configured copies against a temporary HTTP fixture on loopback and generates its own test credentials. To test the automated entry point, run the same command again with `--caller-only` and a different evidence filename. A synthetic parent calls the locally published Merchant child and checks both the hold and approval decisions. No external account or Actor charge is involved. Keep local reports and working directories outside version control. The example repository's MIT license covers the integration materials it distributes. The Actors are separately hosted services.
