# End-to-End Walkthrough: Catalog → Contract → Transformation

Take a Snowflake schema and end with a Fluid contract, a logical-model sidecar and a dbt project scaffold, using `fluid` commands.

> The same `fluid forge data-model from-source` command reads each supported
> catalog. Pick your catalog from the [catalogs index](../cli/catalogs/README.md)
> for the catalog-specific privilege grant, env-var setup, and auth options. This
> walkthrough uses Snowflake.

::: warning Read this before you point it at a catalog that has domain tags or lineage
As of 0.18.1, when the catalog reports a `domain` tag on its tables, or upstream lineage, the forge writes `metadata.domain` and `metadata.lineage` into the contract, and the contract schema rejects both. The forge's own validation then fails, the command exits `1`, and **no files are written**. See [Known issue](#known-issue-catalog-domain-and-lineage-fail-validation) below for the output and what to do about it.
:::

## Prerequisites

- Python 3.10+
- A Snowflake account with `INFORMATION_SCHEMA` read access on at
  least one schema
- For an AI-assisted run: an LLM API key (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`,
  `GEMINI_API_KEY`) or a local Ollama runtime. A `--deterministic` run needs none.

## Install

```bash
pip install "data-product-forge[snowflake]"
# Or for the catalog adapters together:
# pip install "data-product-forge[catalogs]"
```

## Step 1: Configure your LLM provider (one-time, optional)

```bash
fluid ai setup
```

`fluid ai setup` asks which provider to use and stores the choice under `~/.fluid/`; API keys go to the OS keyring when one is available. Paste the key at the hidden prompt, not into a file or a shell command. To configure one provider without the picker, pass `--provider`:

```bash
fluid ai setup --provider anthropic
```

`fluid ai status` shows what is configured. On a machine with nothing configured it says `No LLM provider configured. Run 'fluid ai setup' or set an API key env var.`

## Step 2: Configure your source catalog (one-time per source)

```bash
fluid ai setup --source snowflake --name snowflake-prod
```

The setup asks which authentication method to use (password, key pair, OAuth or browser SSO), captures the credentials, saves them to the OS keyring and `~/.fluid/sources.yaml`, and tests the connection. The saved name (`snowflake-prod`) is what you pass as `--credential-id` in the next step. Prefer key-pair or OAuth for anything that is not an interactive laptop session.

## Step 3: Forge the data model

```bash
fluid forge data-model from-source \
  --source snowflake \
  --credential-id snowflake-prod \
  --database BIZ_LAB --schema SEEDED \
  --technique data-vault-2 \
  -o biz_lab.fluid.yaml
```

Add `--deterministic` to run without any LLM call (the logical model comes from heuristics over the catalog metadata, and the run prints `deterministic mode enabled; staged LLM calls are disabled`). Without it, and with a provider configured, the logical-modelling stage uses the model and the run ends with a cost summary.

When the catalog's tags match an industry pack, the run prints one line before it validates:

```text
Detected industry: telecommunications (from catalog tags). Pack loaded for skeleton + lint.
```

A successful run ends like this (reproduced against a two-table stand-in for a catalog, so the contents of your run will differ):

```text
Validation passed (score=10)
Wrote OSI sidecar biz_lab.fluid.yaml.semantics.osi.yaml
Wrote contract biz_lab.fluid.yaml
Wrote logical sidecar biz_lab.fluid.yaml.model.json
Wrote model document biz_lab.fluid.yaml.model.md
```

| File | What it is |
| --- | --- |
| `biz_lab.fluid.yaml` | The contract. Declares `fluidVersion: 0.7.5` and passes `fluid validate`. |
| `biz_lab.fluid.yaml.model.json` | The logical-model sidecar. The machine source of truth for generation. |
| `biz_lab.fluid.yaml.model.md` | A Mermaid diagram and tables of the model, for review. Skip it with `--no-emit-model-doc`. |
| `biz_lab.fluid.yaml.semantics.osi.yaml` | The semantic model as a standalone Apache Ossie (OSI) interchange document. `--osi-sidecar-format json` writes JSON instead. |

`--name` sets the model name; without it the name is the schema (`SEEDED`), and the contract's `id` is `generated.seeded` unless you edit it.

## Step 4: Inspect the forged contract

```bash
fluid validate biz_lab.fluid.yaml
head -40 biz_lab.fluid.yaml
```

```text
✅ Valid FLUID contract (schema v0.7.5)
```

The catalog signals that survive into the contract are written to `labels` and `metadata.owner`. From the stand-in run, with the catalog's tags, classifications and quality score set:

```yaml
# biz_lab.fluid.yaml (excerpt)
domain: analytics
labels:
  dataModelingTechnique: data_vault_2
  modelSidecar: biz_lab.fluid.yaml.model.json
  catalogClassifications: IDENTIFIER
  catalogOwnerSource: tag
  sensitivityTags: pii
  sourceCatalog: snowflake
  dataQualityScore: '0.97'
  freshnessSla: PT24H
metadata:
  layer: Logical
  owner:
    team: data-eng
```

| Contract field | Where it comes from |
| --- | --- |
| `metadata.owner.team` | The catalog's owner tag. A system role such as `ACCOUNTADMIN` is not promoted to team owner; it is recorded under `labels.catalogCreatingRoles`. With no tag and no owner the value is `data-team`. |
| `labels.catalogOwnerSource` | `tag` when the owner came from a tag, `table_owner` when it came from the table's owner. |
| `labels.sensitivityTags`, `labels.catalogClassifications` | Comma-joined sensitivity tags and classifications the catalog reported. |
| `labels.sourceCatalog`, `labels.dataQualityScore` | The catalog name, and the lowest quality score across the tables. |
| `labels.freshnessSla` | Set when every table reports the same SLA. |
| `domain` | `analytics` unless you name one. The catalog's `domain` tag is **not** written here (see the known issue below). |

Each satellite, hub and link becomes an `exposes[]` entry with its own `binding`, `contract.schema` and a generated `semantics` block. To look at the model graphically:

```bash
fluid viz-graph biz_lab.fluid.yaml
```

`fluid viz-graph` renders the contract's graph with Graphviz when it is installed. Without Graphviz, it writes `runtime/graph/contract.dot` and says so.

### Known issue: catalog `domain` and lineage fail validation

The forge writes the catalog's dominant `domain` tag to `metadata.domain` and the tables' upstream lineage to `metadata.lineage`. Neither key is in any contract schema version, so the forge's validation rejects its own output:

```text
Detected industry: telecommunications (from catalog tags). Pack loaded for skeleton + lint.
Validation failed (score=0)
  ...
  ERROR: metadata: Additional properties are not allowed ('domain', 'lineage' 
were unexpected)
```

The command exits `1` and writes no contract, sidecar or model document. Reproduced in 0.18.1 with a stand-in adapter that returns a `domain` tag on its tables, and again with upstream lineage on its own; the Snowflake adapter reads tags from `OBJECT_TAGS` and lineage from `OBJECT_DEPENDENCIES`. Until the emitter is fixed, forge a schema whose tables carry no `domain` tag and no recorded upstream lineage; with neither, the same command passes validation.

## Step 5: Generate a dbt scaffold

```bash
fluid generate transformation biz_lab.fluid.yaml -o ./dbt_biz_lab --dbt-validate
```

For the stand-in catalog (two tables, Data Vault 2.0), the command wrote:

```text
Generated 9 files (dbt engine):

  dbt_biz_lab/dbt_project.yml
  dbt_biz_lab/profiles.yml
  dbt_biz_lab/models/
    metricflow_time_spine.sql
    semantic_models.yml
  dbt_biz_lab/models/intermediate/
    lnk_orders_customer.sql
  dbt_biz_lab/models/marts/
    sat_customer_details.sql
    sat_orders_details.sql
  dbt_biz_lab/models/staging/
    hub_customer.sql
    hub_orders.sql
```

The model files are **scaffolds**. Each one selects typed null columns from nowhere (`select cast(null as varchar) as "CUSTOMER_ID" where false`) under a `-- Source hint:` comment, so the project parses and builds an empty relation. Write the SQL that reads your real source tables before you rely on `dbt run`. As of 0.18.1 the forged models carry no dbt `meta:` tags, tests or `partition_by` settings; the catalog's classifications are in the contract's `labels` only.

`--dbt-validate` runs `dbt parse` on the output. If no usable dbt is on your `PATH` (or at `$DBT_EXECUTABLE`), the command says `--dbt-validate set but no usable dbt was found` and skips the check; install `dbt-core` and an adapter to enable it.

## Step 6: Iterate

If the modeled output isn't quite right, you have three options:

### Option 1: Re-forge with different scope or technique

```bash
# Try Dimensional instead of Data Vault 2.0:
fluid forge data-model from-source \
  --source snowflake \
  --credential-id snowflake-prod \
  --database BIZ_LAB --schema SEEDED \
  --technique dimensional \
  -o biz_lab.fluid.yaml
```

### Option 2: Review the logical sidecar, regenerate downstream artifacts

```bash
# Edit biz_lab.fluid.yaml.model.json directly.
$EDITOR biz_lab.fluid.yaml.model.json

# Regenerate the dbt project from the contract's labels.modelSidecar.
fluid generate transformation biz_lab.fluid.yaml -o ./dbt_biz_lab --overwrite --dbt-validate
```

You can also open the sidecar for review while forging, with `--review` (it opens in `$EDITOR`).

### Option 3: Drive interactive refinements via Claude Code / Cursor

Configure your IDE's MCP client (see [MCP walkthrough](../advanced/mcp.md)),
then:

> Read `biz_lab.fluid.yaml.model.json` and add a Satellite to
> `hub_customer` for `loyalty_status` (SCD2). Regenerate the contract.

The agent can call the MCP tools `read_logical_model`, `update_entity` and `regenerate_physical`, then write the result back to disk.

## What `--deterministic` does

`--deterministic` forces the cache and tiering off, disables the staged LLM calls, and records audit metadata. The contract, the sidecar and the dbt scaffold are written by deterministic code in either mode; the LLM is used for the logical-modelling decisions only.

## What's audited

A forge writes one audit event, as a JSON file under `~/.fluid/store/audit/`, named `<timestamp>_<id>_forge_data_model.json`:

```json
{
  "event": "forge_data_model",
  "payload": {
    "agentic_mode": "heuristic",
    "deterministic": true,
    "output_path": "biz_lab.fluid.yaml",
    "technique": "dimensional"
  },
  ...
}
```

It records the output path, the technique and the modes. Credentials are not among its fields.

## What's the cost ceiling

Set a per-run ceiling with the `FLUID_COST_LIMIT_USD` environment variable, or `behavior.cost_limit_usd_per_run` in `~/.fluid/config.yaml`:

```bash
export FLUID_COST_LIMIT_USD=5.00
```

When the running total passes it, the run stops with `Cost ceiling exceeded: running $<total> > limit $<limit>`. The environment variable wins over the config file.

## Errors you might see (and what to do)

| Error | What to do |
| --- | --- |
| `snowflake-connector-python is not installed` | `pip install "data-product-forge[snowflake]"` |
| A permission error that suggests `Confirm your role has USAGE on the database and schema.` | Run the `GRANT` command in the suggestion list |
| `CredentialNotFoundError` for a source | `fluid ai setup --source snowflake --name snowflake-prod`, or set the `SNOWFLAKE_*` variable the message names |
| `Note: 1 call had no usage data; cost may be under-reported.` | The provider returned no usage block; the cost figure is partial |

Each catalog page documents the catalog-specific errors. See the
[catalogs index](../cli/catalogs/README.md).

## Next steps

- [Add your own catalog adapter](../contributing.md#add-a-catalog-adapter)
- [V1.5 architecture deep-dive](../advanced/v1.5-architecture.md)
- [MCP server walkthrough](../advanced/mcp.md)
- [Cost tracking details](../advanced/cost-tracking.md)
