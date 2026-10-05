# Fluid Forge Docs

Documentation for the [Fluid Forge CLI](https://github.com/Agenticstiger/forge-cli).

Fluid Forge is a contract-first CLI for data products. You declare a product in a contract; the CLI validates it, builds it locally on DuckDB or deploys it to AWS, GCP or Snowflake, and verifies that what landed matches the contract.

## Start Here

The site is organised the way a reader uses it (get started, tutorials, how-to guides, concepts, reference, releases):

- [Live docs](https://agenticstiger.github.io/forge_docs/)
- [Getting started](https://agenticstiger.github.io/forge_docs/getting-started/): install and build a first product locally
- [Tutorials](https://agenticstiger.github.io/forge_docs/walkthrough/): end-to-end builds, with what each one needs
- [Recipes](https://agenticstiger.github.io/forge_docs/recipes/): one task each, on a contract you already have
- [Concepts](https://agenticstiger.github.io/forge_docs/concepts/): the model, in reading order
- [CLI reference](https://agenticstiger.github.io/forge_docs/cli/) and [contract reference](https://agenticstiger.github.io/forge_docs/reference/)
- [Providers](https://agenticstiger.github.io/forge_docs/providers/)
- [Forge CLI repo](https://github.com/Agenticstiger/forge-cli)

## Current Versioning

- Current CLI release documented here: `0.18.1`
- Contract schema: `fluidVersion: 0.7.5` is the stable default; `0.7.6` is an opt-in preview

Those are different on purpose. `fluid version` reports the installed CLI release, while `fluidVersion` inside a contract selects the contract schema version.

What changed in each release, and what to do when you upgrade:

- [Upgrade guide](https://agenticstiger.github.io/forge_docs/upgrading.html)
- [Release notes for 0.18.0 and 0.18.1](https://agenticstiger.github.io/forge_docs/RELEASE_NOTES_0.18.0.html), [0.17.0](https://agenticstiger.github.io/forge_docs/RELEASE_NOTES_0.17.0.html), [0.16.0](https://agenticstiger.github.io/forge_docs/RELEASE_NOTES_0.16.0.html)

## First-Run Path

```bash
pip install "data-product-forge[local]"
mkdir fluid-quickstart && cd fluid-quickstart
fluid init my-first-product --blueprint fluid.starter
cd my-first-product
fluid validate contract.fluid.yaml
fluid plan contract.fluid.yaml
fluid apply contract.fluid.yaml --yes --mode amend-and-build
fluid verify contract.fluid.yaml --strict
cat runtime/out/my-first-product.csv
```

[Getting started](https://agenticstiger.github.io/forge_docs/getting-started/) runs these steps with their output, and says why it uses the `fluid.starter` blueprint rather than `fluid init --quickstart` on 0.18.1 (the quickstart's local apply writes a placeholder file).

Optional AI-assisted scaffolding uses `fluid forge`:

```bash
fluid forge
fluid forge --domain finance
```

To forge a reviewable data model from a business intent file:

```bash
fluid forge data-model from-intent --example retail > intent.yaml
fluid forge data-model from-intent intent.yaml -o customer_orders.fluid.yaml
fluid generate transformation customer_orders.fluid.yaml -o ./dbt_customer_orders --dbt-validate
```

## Promoted Command Groups

These are the groups `fluid --help` prints on `0.18.1`:

| Group | Commands |
| --- | --- |
| Core Workflow | `init`, `forge`, `validate`, `plan`, `apply` |
| Generate | `generate transformation`, `generate schedule`, `generate ci`, `generate standard` |
| Integrations | `publish`, `market`, `import`, `mcp` |
| Quality & Governance | `policy-check`, `test` |
| Safety & Supply Chain | `rollback`, `verify-signature` |
| Utilities | `config`, `ai`, `split`, `auth`, `doctor`, `providers`, `exporters`, `version` |

`--help` promotes a short surface. Commands such as `bundle`, `diff`, `verify`, `schedule-sync` and `forge data-model` are documented in the [CLI reference](https://agenticstiger.github.io/forge_docs/cli/). Compatibility commands such as `generate-airflow` are still documented, but the docs lead with the promoted paths above.

## Local Preview

```bash
npm install
npm run docs:dev
```

Build the production site with:

```bash
npm run docs:build
npm run docs:preview
```

## Repo Layout

```text
docs/
├── README.md              # home page
├── upgrading.md           # upgrade guide
├── RELEASE_NOTES_*.md     # one page per docs baseline
├── getting-started/
├── concepts/
├── cli/                   # command reference
├── providers/
├── recipes/
├── walkthrough/
├── advanced/
├── data-products/
├── sdk-and-plugins/
├── demos/
├── playground/
├── faq/
└── .vuepress/             # site config, sidebar, cli-version.json
scripts/                   # docs checks (check_cli_docs.py, check-dist-links.mjs, ...)
```

## Contributing

Docs-only pull requests are welcome. When a docs update depends on a CLI change, link the related `forge-cli` PR or issue in the description.
