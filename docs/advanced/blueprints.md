# Blueprints

A blueprint is a parameterized contract template. You give it a few values (a product name, a project id) and it renders a complete FLUID contract. Four blueprints ship inside the CLI, so this works offline with no AI key and no account.

## Quick start

Render the bundled starter blueprint into a contract and run it locally:

```bash
fluid market --blueprint-id fluid.starter \
  --instantiate --params '{"product_name": "Orders"}' -O contract.fluid.yaml
fluid validate contract.fluid.yaml
```

```text
✅ Valid FLUID contract (schema v0.7.4)
```

`-O` (`--output`) is what writes the file. Without it the contract is printed to the console and nothing is saved. The saved file is JSON, whatever its extension. `fluid validate`, `plan` and `apply` read it as they would YAML, because JSON is valid YAML.

To get a YAML file in a fresh project directory, use [`fluid init --blueprint`](../cli/init.md) instead:

```bash
fluid init demo-orders --blueprint fluid.starter --domain sales \
  --owner-team analytics --owner-email analytics@example.com
cd demo-orders && fluid validate
```

Run from an empty directory, `fluid init --blueprint` writes `demo-orders/contract.fluid.yaml` and `demo-orders/.fluid/forge-receipt.json`. It also writes a `fluid.workspace.yaml`, a `.gitignore` and a `.fluid/` folder in the directory you ran it from. It takes the blueprint ids listed below.

## The bundled blueprints

```bash
fluid market --blueprints
```

```text
                 Blueprint Marketplace (4 bundled + 0 registry)
┏━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━┓
┃ ID                      ┃ Name     ┃ Category ┃ Maturity ┃ Source  ┃ Version ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━┩
│ fluid.starter           │ Starter  │ starter  │ stable   │ bundled │  1.0.0  │
│ fluid.analytics-daily   │ Daily    │ analyti… │ stable   │ bundled │  1.0.0  │
│ fluid.starter-gcp       │ Starter  │ starter  │ stable   │ bundled │  1.0.0  │
│ fluid.starter-snowflake │ Starter  │ starter  │ stable   │ bundled │  1.0.0  │
...
```

| Blueprint | What it renders | Parameters beyond `product_name`, `domain`, `owner_team`, `owner_email` |
|---|---|---|
| `fluid.starter` | A Bronze product: embedded SQL to a local CSV. | none |
| `fluid.analytics-daily` | A Silver product: a daily row count read from a CSV at `runtime/in/<name>_source.csv`, which you supply. | none |
| `fluid.starter-gcp` | The starter bound to a BigQuery table. | `gcp_project`, `gcp_dataset` |
| `fluid.starter-snowflake` | The starter bound to a Snowflake table. | `sf_account`, `sf_database`, `sf_schema` |

`product_name` is the only required parameter. Each blueprint declares its own `fluidVersion`; the bundled starter renders `0.7.4`, so a contract rendered from a blueprint can sit one schema version behind what `fluid init --quickstart` writes.

The listing's fifth column is the source (`bundled` or a registry), not a download count.

## Inspect a blueprint

`fluid market --blueprint-id <id>` prints a blueprint's description, maturity, license and parameter table, with each parameter's type and whether it is required:

```bash
fluid market --blueprint-id fluid.starter-gcp
```

Add `--show-template` to print the Jinja2 template the contract is rendered from.

## Instantiate a blueprint

`--instantiate` needs `--blueprint-id` and one way to supply parameters:

| Flag | Behaviour |
|---|---|
| `--params '<json>'` | Parameters as a JSON string, or a path to a JSON file. |
| `--interactive` | Prompts for each parameter. |
| neither | Prints `No parameters provided. Use --params or --interactive.` and exits 1. |

Leaving out a required parameter fails before anything is rendered:

```bash
fluid market --blueprint-id fluid.starter --instantiate --params '{}'
```

```text
❌ Missing required blueprint parameter(s): product_name. Pass them via --params
'{"product_name": "..."}' or --interactive.
```

Bundled blueprints render on your machine in a sandboxed Jinja2 environment, with no network call. The CLI does not validate the rendered contract for you, so run `fluid validate` on it.

## Blueprints from a registry

Only the four bundled blueprints are available with no registry. For any other id, `fluid market` needs a registry, and the command fails with `no_blueprint_marketplace` when it finds none:

```bash
fluid market --blueprint-id customer-360-etl
```

```text
❌ Error: no_blueprint_marketplace
```

Set `FLUID_API_URL` to a Command Center or compatible API, or `FLUID_PUBLIC_REGISTRY`, to list and instantiate registry blueprints alongside the bundled ones. With no registry configured, `fluid market --blueprints` prints `No registry configured; showing bundled blueprints.` and, when Command Center is not running on `localhost:8000`, a one-line warning that it is unavailable. Registry blueprints render on the server, and the listing's source column shows where each one came from.

## Next steps

Run the standard workflow on the rendered contract:

```bash
fluid validate contract.fluid.yaml
fluid plan contract.fluid.yaml
fluid apply contract.fluid.yaml --yes
```

The local blueprints (`fluid.starter`, `fluid.analytics-daily`) apply on your machine and need the `local` extra (`pip install "data-product-forge[local]"`). The GCP and Snowflake starters bind to a real project or account, so edit the placeholder `binding.location` values first.

## See also

- [`fluid market`](../cli/market.md): every flag, including the catalog-search mode
- [`fluid init`](../cli/init.md): create a project from a blueprint or a template
- [Getting started](../getting-started/README.md): install and run your first project
- [Custom LLM agents](./custom-llm-agents.md): AI-assisted project generation with your own models
- [Contributing](../contributing.md): contribute new blueprints
