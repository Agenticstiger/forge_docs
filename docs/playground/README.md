---
title: Playground
description: Edit a real FLUID contract in your browser. No install required.
sidebar: false
---

# 🎛 Playground

Pick a starter, edit the YAML, copy it. When you're ready, paste into a local file and run `fluid validate`.

In-browser validation via Pyodide is on the roadmap — for now the editor focuses on **fast iteration on the schema** without round-tripping through `pip install`.

<ClientOnly>
  <Playground />
</ClientOnly>

## What's in each template?

- **Local · DuckDB** — runs on your laptop with `platform: local` + `format: parquet`. The fastest path from "never installed FLUID" to "deployed data product."
- **GCP · BigQuery** — production-grade with schema, IAM grants in `accessPolicy.grants[]`, AI/agent boundaries via `agentPolicy`, and column-level PII tagging.
- **AWS · Athena** — S3-backed external table with the canonical bucket/prefix layout the AWS provider produces.
- **Snowflake** — three-part-name binding with role-based access control.

All four are valid against `fluid-schema-0.7.2`, the current contract spec.

## Next steps

After you've edited a contract you like:

```bash
# 1. Save the YAML to a local file (right-click → Save As, or just paste)
$ pbpaste > contract.fluid.yaml      # macOS — pulls from clipboard

# 2. Validate it (requires `pipx install data-product-forge` — see Getting Started)
$ fluid validate contract.fluid.yaml

# 3. Plan and apply against the local provider (no cloud account needed)
$ fluid plan contract.fluid.yaml
$ fluid apply contract.fluid.yaml --yes
```

[Full quickstart →](/getting-started/) · [CLI reference →](/cli/)
