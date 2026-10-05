# AI Forge And Data-Model Journeys

This walkthrough shows the main `fluid forge` and `fluid forge data-model` paths a new user can take. AI helps with discovery, interview, semantic modeling, and review. Contract writing, validation, and dbt SQL generation stay deterministic from the forged logical model.

## Credential Safety First

Never put an API key in an intent file, contract, docs page, shell history snippet, or Git commit. Use environment variables or `fluid ai setup`.

```bash
# Pick one hosted provider.
export GOOGLE_API_KEY="<your-gemini-key>"
# or
export OPENAI_API_KEY="<your-openai-key>"
# or
export ANTHROPIC_API_KEY="<your-anthropic-key>"
```

For local-only testing, use Ollama instead, and name the model with `--llm-model` (the built-in default is `gemma4:latest`):

```bash
export OLLAMA_HOST=http://localhost:11434
```

`fluid ai setup` stores provider/model preferences under `~/.fluid/`. API keys go to the OS keyring when available. Plaintext key persistence requires explicit opt-in with `FLUID_ALLOW_PLAINTEXT_AI_SECRETS=1`.

## Choose The Right Entry Point

| Goal | Command | AI needed |
| --- | --- | --- |
| Create a blank contract scaffold | `fluid forge --blank` | No |
| Let the CLI interview you and scaffold a project | `fluid forge` | Optional but recommended |
| Forge a model from YAML/JSON business intent | `fluid forge data-model from-intent` | Optional |
| Reverse-engineer existing SQL DDL | `fluid forge data-model from-ddl` | Optional |
| Forge directly from a metadata catalog | `fluid forge data-model from-source` | Optional for modeling, catalog credentials required |
| Validate a forged artifact | `fluid forge data-model validate` | No |
| Compare two sidecars | `fluid forge data-model diff` | No |
| Teach memory from operator edits | `fluid forge data-model learn` | No |
| Generate dbt SQL | `fluid generate transformation` | No |

## Provider Setup And Model Plan

Inspect the configured provider defaults and tier routing:

```bash
fluid ai models
```

```text
                        AI Model Plan                        
┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Provider           ┃ Role     ┃ Model                     ┃
┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Google Gemini      │ primary  │ gemini-2.5-pro            │
│                    │ routing  │ gemini-2.5-flash          │
│                    │ deep     │ gemini-2.5-pro            │
...
│ Anthropic (Claude) │ primary  │ claude-sonnet-4-6         │
...
└────────────────────┴──────────┴───────────────────────────┘
Contract forging, dbt SQL generation, and validation are deterministic from the 
logical sidecar.
```

The table lists Gemini, OpenAI, Anthropic and Ollama with a `primary`, `routing`, `deep`, `balanced` and `fast` model each. The model ids come from the CLI's built-in defaults and change between releases, so read them from your own `fluid ai models`.

`--json` prints one object per provider (`anthropic`, `gemini`, `ollama`, `openai`) with its `stages`. To look at one provider:

```bash
fluid ai models --json | python3 -c "import json,sys; print(json.dumps(json.load(sys.stdin)['gemini'], indent=2))"
```

::: warning `fluid ai models --provider <name>` fails in 0.18.1
`fluid ai models` documents a `--provider {gemini,openai,anthropic,claude,ollama}` filter, but the top-level CLI checks any parsed `provider` value against the infrastructure providers (`aws`, `datamesh_manager`, `gcp`, `local`, `redshift`, `snowflake`) first. `fluid ai models --provider gemini` therefore exits `2` with `Unknown provider 'gemini' — installed providers: aws, datamesh_manager, gcp, local, redshift, snowflake`. Use `--json` and filter as above. `fluid ai setup --provider` is not affected.
:::

The current tier plan is provider-local:

| Stage (`stages[].stage` in the JSON) | Mode | Tier |
| --- | --- | --- |
| `interview` | `llm_routing` | `fast` |
| `logical_modeler` | `strict_llm_or_llm` | `deep` |
| `contract_forge` | `deterministic` | none |
| `transformation` | `deterministic_from_sidecar` | none |
| `validator` | `deterministic` | none |
| `self_eval` | `llm_routing` | `fast` |

For a hosted provider run, either complete interactive setup:

```bash
fluid ai setup
fluid ai status
```

or use environment variables for a single shell session:

```bash
export GOOGLE_API_KEY="<your-gemini-key>"
fluid forge data-model from-intent intent.yaml \
  -o customer_orders.fluid.yaml \
  --llm-provider gemini \
  --tiered \
  --require-llm
```

Use `--require-llm` when you are validating provider setup. Without it, normal UX may fall back to deterministic heuristics if the hosted provider is unavailable. With no provider configured, `--require-llm` stops the run:

```text
copilot_missing_required_llm: --require-llm was set but no LLM provider/model 
was configured.
  - Pass --llm-provider and the provider API key
  - Or unset --require-llm for heuristic fallback runs
```

## Flow 1: Blank Scaffold, No AI

Use this when you want a contract skeleton and prefer to fill it by hand.

```bash
fluid forge --blank --target-dir ./customer-orders --non-interactive
cd customer-orders
fluid validate contract.fluid.yaml
fluid plan contract.fluid.yaml --out runtime/plan.json
```

```text
✅ Valid FLUID contract (schema v0.7.5)
...
1. provision_output (provisionDataset)
2. schedule_main (scheduleTask)
```

This path writes a contract scaffold (`contract.fluid.yaml`) only. It does not create a logical model sidecar or dbt project.

## Flow 2: Interactive AI Scaffold

Use this when you want the CLI to discover local context, ask a short interview, and scaffold the first product draft.

```bash
fluid forge
```

Useful variants:

```bash
fluid forge --domain retail
fluid forge --provider gcp --domain finance
fluid forge --discovery-path ./warehouse-ddl --discovery-path ./sample-data
fluid forge --no-discover
fluid forge --no-memory
fluid forge --save-memory
fluid forge --llm-provider openai --llm-model gpt-4.1-mini
fluid forge --llm-provider gemini --tiered --require-llm
```

The interview keeps three concepts separate:

| Interview concept | Meaning |
| --- | --- |
| Data model | Dimensional or Data Vault 2.0 |
| Transformation | dbt, SQL, Spark, Python, or custom code generation |
| Scheduler | None, Airflow, Dagster, or Prefect |

Choosing dbt as the transformation engine does not imply scheduling. Add a scheduler only when you want generated orchestration artifacts.

## Flow 3: Intent To Model Doc To dbt

An intent file is the business request in YAML or JSON. For example:

```yaml
data_product:
  name: customer_orders
  domain: retail
  description: Customer order analytics for revenue, basket, and store performance.

business_context:
  problem_statement: >
    The team needs a trusted customer order model that can support sales reporting,
    product performance analysis, and store operations.
  consumer: sales analysts

grain:
  entity: order_line
  time_dimension: order_date

dimensions:
  entities:
    - customer
    - product
    - store
    - promotion

metrics:
  - name: total_revenue
    description: Sum of order line revenue after discounts.
  - name: order_count
    description: Count of unique customer orders.
  - name: average_order_value
    description: Total revenue divided by order count.

data_sources:
  - source_name: raw_orders
    source_type: snowflake
    description: RAW_RETAIL.ORDERS
  - source_name: raw_order_lines
    source_type: snowflake
    description: RAW_RETAIL.ORDER_LINES

business_rules:
  - Exclude cancelled orders from revenue metrics.
  - Treat returned items as negative revenue.

modeling:
  technique: dimensional
```

`business_context` is a mapping (`problem_statement`, `decision_supported`, `consumer`, ...), and each `data_sources` entry needs `source_name` and `source_type`. A plain-text `business_context`, or a source with `name` and `system` instead, fails validation:

```text
intent validation failed: intent file has invalid business_context: Input should
be a valid dictionary or instance of BusinessContext
```

Ask the CLI for a parseable example and schema:

```bash
fluid forge data-model from-intent --example retail > retail.intent.yaml
fluid forge data-model from-intent --schema > business-intent.schema.json
fluid forge data-model from-intent --validate retail.intent.yaml
```

```text
Intent file is valid retail.intent.yaml
```

`--example` also accepts `minimal`, `telco` and `finance`.

Forge the contract and model artifacts:

```bash
fluid forge data-model from-intent retail.intent.yaml \
  -o customer_orders.fluid.yaml \
  --technique dimensional \
  --emit-osi-sidecar
```

For a deterministic local smoke test, add:

```bash
fluid forge data-model from-intent retail.intent.yaml \
  -o customer_orders.fluid.yaml \
  --technique dimensional \
  --deterministic \
  --emit-osi-sidecar
```

Expected output and artifacts:

```text
deterministic mode enabled; staged LLM calls are disabled
Validation passed (score=10)
Wrote OSI sidecar customer_orders.fluid.yaml.semantics.osi.yaml
Intent file accepted retail.intent.yaml
Selected modeling technique: dimensional
Wrote contract customer_orders.fluid.yaml
Wrote logical sidecar customer_orders.fluid.yaml.model.json
Wrote model document customer_orders.fluid.yaml.model.md
```

```text
customer_orders.fluid.yaml
customer_orders.fluid.yaml.model.json
customer_orders.fluid.yaml.model.md
customer_orders.fluid.yaml.semantics.osi.yaml
```

The `.model.md` file is the human review layer. It contains a Mermaid diagram, facts/dimensions or hubs/links/satellites, grain, metrics, source hints, and assumptions. The `.model.json` file is the machine source of truth for generation.

Generate dbt from the forged sidecar:

```bash
fluid generate transformation customer_orders.fluid.yaml \
  -o ./dbt_customer_orders \
  --dbt-validate \
  --overwrite
```

For this intent, the command wrote:

```text
Generated 7 files (dbt engine):

  dbt_customer_orders/dbt_project.yml
  dbt_customer_orders/profiles.yml
  dbt_customer_orders/models/marts/
    fact_order_line.sql
  dbt_customer_orders/models/staging/
    dim_customer.sql
    dim_product.sql
    dim_promotion.sql
    dim_store.sql
```

The SQL files are scaffolds. A model forged from an intent selects typed null columns with `where false` (`select cast(null as varchar) as "customer_name" where false`), so the project parses and builds empty relations until you write the SQL that reads your sources. In this run no `models/sources.yml` was written: the intent's `data_sources` entries did not produce one. A model forged from DDL (Flow 5) does get a `models/sources.yml`.

`--dbt-validate` runs `dbt parse` on the output. Without a usable dbt on your `PATH` (or `$DBT_EXECUTABLE`), the command prints `--dbt-validate set but no usable dbt was found` and skips the check.

## Flow 4: Strict Hosted Provider Smoke

Use this when you want to prove the run really used a provider and did not fall back.

Gemini:

```bash
export GOOGLE_API_KEY="<your-gemini-key>"
fluid forge data-model from-intent retail.intent.yaml \
  -o customer_orders.gemini.fluid.yaml \
  --llm-provider gemini \
  --tiered \
  --require-llm \
  --emit-osi-sidecar
```

OpenAI:

```bash
export OPENAI_API_KEY="<your-openai-key>"
fluid forge data-model from-intent retail.intent.yaml \
  -o customer_orders.openai.fluid.yaml \
  --llm-provider openai \
  --tiered \
  --require-llm \
  --emit-osi-sidecar
```

Anthropic:

```bash
export ANTHROPIC_API_KEY="<your-anthropic-key>"
fluid forge data-model from-intent retail.intent.yaml \
  -o customer_orders.anthropic.fluid.yaml \
  --llm-provider anthropic \
  --tiered \
  --require-llm \
  --emit-osi-sidecar
```

Ollama:

```bash
export OLLAMA_HOST=http://localhost:11434
fluid forge data-model from-intent retail.intent.yaml \
  -o customer_orders.ollama.fluid.yaml \
  --llm-provider ollama \
  --llm-model gemma4:latest \
  --require-llm \
  --emit-osi-sidecar
```

After any provider run, validate and generate:

```bash
fluid forge data-model validate customer_orders.gemini.fluid.yaml
fluid generate transformation customer_orders.gemini.fluid.yaml \
  -o ./dbt_customer_orders_gemini \
  --dbt-validate \
  --overwrite
```

## Flow 5: DDL To Model

Use DDL when you already have warehouse table definitions.

```bash
fluid forge data-model from-ddl \
  --ddl warehouse/orders.sql warehouse/customers.sql \
  --source-type snowflake \
  --technique dimensional \
  -o customer_orders_ddl.fluid.yaml \
  --emit-osi-sidecar
```

For live Snowflake schemas, dump first, then forge:

```bash
fluid forge data-model dump-ddl \
  --database BIZ_LAB \
  --schema SEEDED \
  -o biz_lab.sql

fluid forge data-model from-ddl \
  --ddl biz_lab.sql \
  --source-type snowflake \
  --technique data-vault-2 \
  -o biz_lab.fluid.yaml
```

DDL is excellent for table and column evidence. A model forged from DDL gets a `models/sources.yml` that lists the tables and columns from the DDL under a `raw` source (its schema is read from `FLUID_SOURCE_SCHEMA`, then `SNOWFLAKE_STAGE_SCHEMA`, then the dbt target schema). With two small tables, the generated project was:

```text
Generated 6 files (dbt engine):

  dbt_ddl/dbt_project.yml
  dbt_ddl/profiles.yml
  dbt_ddl/models/
    sources.yml
  dbt_ddl/models/marts/
    fact_orders.sql
  dbt_ddl/models/staging/
    dim_customers.sql
    dim_date.sql
```

## Flow 6: Metadata Catalog To Model

Use `from-source` when metadata already lives in Snowflake, Unity Catalog, BigQuery, Dataplex, Glue, DataHub, or Data Mesh Manager.

One-time source credential setup:

```bash
fluid ai setup --source snowflake --name snowflake-prod
```

Forge from the configured source:

```bash
fluid forge data-model from-source \
  --source snowflake \
  --credential-id snowflake-prod \
  --database BIZ_LAB \
  --schema SEEDED \
  --tables CUSTOMER ORDER_LINE PRODUCT \
  --technique data-vault-2 \
  -o biz_lab.fluid.yaml \
  --emit-osi-sidecar
```

If running on cloud infrastructure with workload identity, opt in explicitly:

```bash
fluid forge data-model from-source \
  --source bigquery \
  --database analytics-prod \
  --schema sales_mart \
  --allow-metadata-service \
  -o sales_mart.fluid.yaml
```

Catalog credentials are separate from LLM provider credentials. `--credential-id` refers to the source credential created by `fluid ai setup --source ...`.

::: warning A catalog that reports a `domain` tag or upstream lineage fails validation in 0.18.1
The forge writes those two signals to `metadata.domain` and `metadata.lineage`, which no contract schema accepts, so the run exits `1` and writes nothing. See [Known issue](./catalog-forge-end-to-end.md#known-issue-catalog-domain-and-lineage-fail-validation).
:::

`from-source` also reads a Postgres, MySQL or SQLite database directly, with `--uri` instead of a saved credential. That path introspects tables and columns through DuckDB (which downloads the database extension on first use) and writes a Bronze source-aligned contract; it does not run the staged modeling pipeline, so the modeling flags above do not apply:

```bash
fluid forge data-model from-source \
  --source sqlite --uri sqlite:///$PWD/shop.db \
  -o shop.fluid.yaml
```

```text
✓ Forged 2-table SDP contract from sqlite into shop.fluid.yaml
```

That contract declares `fluidVersion: "0.7.3"` and validates; bump the version by hand to use later schema features.

## Flow 7: Review, Diff, Learn

Review the logical sidecar before finalizing:

```bash
EDITOR=vim fluid forge data-model from-intent retail.intent.yaml \
  -o customer_orders.fluid.yaml \
  --review
```

Compare two forged sidecars:

```bash
fluid forge data-model diff old.model.json new.model.json
```

The diff is structural. Comparing the intent-forged model with the DDL-forged one printed, for example:

```text
Structural diff
  - Added dimension dim_customers.
  - Added dimension dim_date.
  - Removed dimension dim_customer.
  ...
  - Added fact fact_orders.
  - Removed fact fact_order_line.
```

Teach memory from a human-edited version:

```bash
fluid forge data-model learn \
  --original customer_orders.fluid.yaml \
  --edited customer_orders.reviewed.fluid.yaml
```

Use memory intentionally:

```bash
fluid forge --save-memory
fluid forge --no-memory
FLUID_COPILOT_SEMANTIC_MEMORY=1 \
  fluid forge data-model from-intent retail.intent.yaml -o customer_orders.fluid.yaml
```

`learn` records the operator's edit to memory:

```text
✓ Recorded 1 operator edit(s) for contract 'customer_orders' in memory/semantic.
  • modified description
```

Memory should store preferences and summaries, not raw data or credentials.

## Flow 8: Add Scheduling Only When Needed

dbt generation and scheduling are separate:

```bash
fluid generate transformation customer_orders.fluid.yaml \
  -o ./dbt_customer_orders \
  --dbt-validate
```

If the contract includes or you choose a scheduler, generate it explicitly:

```bash
fluid generate schedule customer_orders.fluid.yaml \
  --scheduler airflow \
  -o ./dags \
  --overwrite
```

```text
Generated 1 files (airflow scheduler):

  dags/generated_customer_orders_dag.py
```

Use `none` during interviews when the team already has its own scheduler or only wants model/dbt artifacts.

## More Flags On The Data-Model Subcommands

| Flag | What it does |
| --- | --- |
| `--allow-semantic-warnings` | Write the artifacts even when the canonical industry coverage check still has warnings. |
| `--industry <name>` | Lint the forged model against an industry pack's canonical skeleton (for example `telecommunications`, `retail`, `healthcare`, `finance`). `from-source` detects it from catalog tags when you leave it out. |
| `--emit-ddl-dir <dir>` | Write generated DDL files for the logical model. |
| `--emit-dimensional-variants <dir>` | Write star, snowflake, galaxy and flat dimensional sidecars to the directory. |
| `--transformation-engine` (or `--engine`) | `dbt`, `sql`, `python`, `spark` or `custom`: the engine hint stamped into the contract. |
| `--modeling-technique custom` with `--logical-model <file>` | Use a logical model you supply, verbatim, instead of reshaping one. |
| `--osi-sidecar-format yaml\|json` | Serialization of the OSI sidecar. `json` is the shape dbt Core 1.12 and later reads natively. |
| `--llm-timeout-seconds <n>` | Provider HTTP timeout for the staged LLM calls; defaults to 120. |

## What To Commit

Usually commit:

- The intent file when it is part of the design record.
- `*.fluid.yaml`.
- `*.model.json`.
- `*.model.md`.
- `*.semantics.osi.yaml` when semantic sidecars are part of your review flow.
- Generated dbt SQL when this repo owns transformation code.

Do not commit:

- API keys, tokens, passwords, or private keys.
- `~/.fluid/` contents.
- `.fluid/store/` memory/cache data unless your team has explicitly decided to version a sanitized team memory file.
- dbt logs, `target/`, or local profile secrets.

## Troubleshooting

| Symptom | What to do |
| --- | --- |
| `--require-llm` fails | Check provider env var, `fluid ai status`, model name, network, and quota. |
| Prompt asks about scheduling after you said no | Treat it as a UX bug and report the exact transcript; transformation and scheduler are separate decisions. |
| No `.model.md` written | Ensure `--no-emit-model-doc` was not passed. The default is to emit it. |
| dbt models select only typed nulls | Expected for a scaffold: forged models carry `where false` placeholders. Write the SQL that reads your sources. |
| No `models/sources.yml` | Forge from DDL (Flow 5): that path writes one. An intent's `data_sources` entries do not produce it in 0.18.1. |
| You want CI without AI | Use deterministic checked-in artifacts: `validate`, `generate`, `plan`, `apply`. Do not require live LLM calls in production CI. |
