# `fluid init`

Create a new project with the fastest local-first path into Fluid Forge.

## Syntax

```bash
fluid init NAME
```

## Key options

| Option | Description |
| --- | --- |
| `--quickstart` | Create a working example with sample data |
| `--blank` | Create an empty project skeleton |
| `--template NAME` | Create from a named template |
| `--list-templates` | Show available templates and exit |
| `--discover URI` | Introspect a source (`postgres://`, `mysql://`, `file://`, `s3://`) and emit a Bronze acquisition contract per discovered stream. **Coming on the source-aligned-acquisition branch — schema 0.7.3.** |
| `--provider` | Target provider, defaulting to local |
| `--yes`, `-y` | Skip confirmation prompts |
| `--dry-run` | Preview what would be created |
| `--dir`, `-C` | Initialize in a specific directory |
| `--quiet`, `-q` | Suppress post-success hints |
| `--agent NAME` | Scaffold a custom domain agent spec in `.fluid/agents/` |

## Examples

```bash
fluid init my-project
fluid init my-project --quickstart
fluid init my-project --template customer-360
fluid init --list-templates
fluid init my-project --provider snowflake
```

## `--discover` — introspect a source into a Bronze contract

::: tip Coming in the next release
`--discover` ships on the `feat/source-aligned-acquisition` branch as part of schema 0.7.3. The pinned 0.8.0 baseline doesn't include it yet.
:::

Instead of writing the acquisition block by hand, point `fluid init` at a source URI and it emits a deterministic 0.7.3 Bronze (SDP) contract per discovered stream:

```bash
fluid init --discover postgres://user:pass@host:5432/dbname
fluid init --discover mysql://user:pass@host:3306/dbname
fluid init --discover file:///path/to/csv-tree
fluid init --discover s3://bucket/prefix/
```

What it does:

- Connects to the source (read-only — `\dt` for Postgres, `SHOW TABLES` for MySQL, directory walk for filesystem)
- Emits one acquisition contract per discovered table or stream
- Sets `metadata.layer: Bronze` AND `metadata.productType: SDP` (both vocabularies — see [Product Types](/forge_docs/data-products/product-type.html))
- **Auto-redacts secrets** from the connection string into `${ENV_VAR}` placeholders (so the emitted contract is safe to commit)
- Picks `engine: duckdb` by default for embedded ingestion (no Airbyte cluster required)

Output shape (one file per discovered stream):

```text
my-project/
├── public.orders.fluid.yaml          # one contract per table
├── public.customers.fluid.yaml
├── public.products.fluid.yaml
└── .fluid/
```

You can then `fluid validate` and `fluid apply` immediately, or open the files and tweak the engine choice / quality rules / retention horizons. See [Source-Aligned Acquisition](/forge_docs/advanced/source-aligned-acquisition.html) for the full framework, or [the Postgres → DuckDB walkthrough](/forge_docs/walkthrough/source-aligned-postgres-duckdb.html) for an end-to-end example.

## Notes

- The promoted newcomer path is `fluid init ... --quickstart`, then `validate`, `plan`, and `apply`.
- Current scaffolds emit contracts using `fluidVersion: 0.7.2`. The `--discover` path emits `fluidVersion: 0.7.3`.
- If you want AI-assisted scaffolding instead, use [`fluid forge`](./forge.md).

## Fastest path — `fluid demo`

If you want to *see* FLUID working end-to-end in about 30 seconds rather than create your own project first, use `fluid demo`. It scaffolds a working customer-360 example with sample data **and** runs the pipeline immediately — zero setup, no API key, no cloud account, local DuckDB.

```bash
fluid demo [NAME]
```

### Options

| Option | Description |
| --- | --- |
| `NAME` | Directory name for the demo project (positional, optional). Default: `customer-360`. |
| `--dry-run` | Preview what would be created without writing anything |
| `--no-run` | Scaffold the project but skip running the pipeline |
| `--quiet`, `-q` | Suppress post-success hints |

### Examples

```bash
fluid demo
fluid demo my-customer-360
fluid demo --dry-run
fluid demo my-project --no-run
```

After `fluid demo` completes you have a normal FLUID project — `fluid validate`, `fluid plan`, `fluid apply` all work against it. Use `--no-run` when you want to inspect the generated contract and SQL before executing the pipeline.
