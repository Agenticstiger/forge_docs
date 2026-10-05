---
title: Playground
description: Edit a starter FLUID contract in your browser, then validate it locally with the CLI.
sidebar: false
---

# Playground

Pick a starter, edit the YAML, copy it. Paste it into a local file and run `fluid validate`. The editor works on the YAML only: it does not run the CLI or the schema, so nothing in the editor tells you whether a contract is valid.

<ClientOnly>
  <Playground />
</ClientOnly>

## What's in each template?

- **Local · DuckDB** uses `platform: local` with `format: parquet` and a build step that reads a source table.
- **GCP · BigQuery** has a schema, a BigQuery binding, IAM grants in `accessPolicy.grants[]`, an AI/agent boundary and a PII-tagged column.
- **AWS · Athena** has an S3-backed table with a bucket and a prefix.
- **Snowflake** has a three-part-name binding and a role grant.

## What the starters do on CLI 0.18.1

Checked with `fluid validate` against CLI 0.18.1. The starters declare `fluidVersion: "0.7.2"`, which the CLI still accepts; the latest stable contract schema is `0.7.5`, which is what `fluid init --quickstart` writes.

| Starter | `fluid validate` |
|---|---|
| Local · DuckDB | Valid |
| Snowflake | Valid |
| GCP · BigQuery | Fails: `root: Additional properties are not allowed ('agentPolicy' was unexpected)` |
| AWS · Athena | Fails: `exposes[0].binding.location: Additional properties are not allowed ('prefix' was unexpected)` |

Both failures also occur with `fluidVersion: "0.7.5"`. To fix them by hand:

- **GCP:** `agentPolicy` is not a root key. Put it under the expose, as `exposes[].policy.agentPolicy`, with the same `allowedModels` and `allowedUseCases` keys.
- **AWS:** the `s3_file` location takes `path`, not `prefix`. Write `path: events/web_clickstream/`.

With those two edits and `fluidVersion: "0.7.5"`, all four starters validate. A starter that validates is not necessarily one that applies: the Local starter's build SQL reads a table named `raw_btc_feed` that the contract does not create, so `fluid apply` stops on the first action with `Catalog Error: Table with name raw_btc_feed does not exist!`. For a contract that applies from a clean directory, use `fluid init my-project --quickstart`; with the local extra installed it writes two Parquet files under `output/`.

## Next steps

After you've edited a contract you like:

```bash
# 1. Save the YAML to a local file (right-click → Save As, or just paste)
$ pbpaste > contract.fluid.yaml      # macOS — pulls from clipboard

# 2. Validate it (requires `pipx install data-product-forge` — see Getting Started)
$ fluid validate contract.fluid.yaml

# 3. Preview what apply would do
$ fluid plan contract.fluid.yaml
```

Applying against the local provider also needs DuckDB: `pip install "data-product-forge[local]"`. Then `fluid apply contract.fluid.yaml --yes` runs the contract, provided its build steps read tables that exist.

[Full quickstart →](/forge_docs/getting-started/) · [CLI reference →](/forge_docs/cli/)
