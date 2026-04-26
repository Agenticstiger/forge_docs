# Fluid Forge Docs

Documentation for the [Fluid Forge CLI](https://github.com/Agenticstiger/forge-cli).

Fluid Forge is a contract-first CLI for building, validating, and deploying data products across local and cloud targets. The docs in this repo track the promoted CLI surface from `fluid --help`, with local-first onboarding and compatibility notes for older commands where needed.

## Start Here

- [Live docs](https://agenticstiger.github.io/forge_docs/)
- [Getting started](https://agenticstiger.github.io/forge_docs/getting-started/)
- [Forge data model](https://agenticstiger.github.io/forge_docs/forge-data-model.html)
- [CLI reference](https://agenticstiger.github.io/forge_docs/cli/)
- [Providers](https://agenticstiger.github.io/forge_docs/providers/)
- [Forge CLI repo](https://github.com/Agenticstiger/forge-cli)

## Current Versioning

- Current CLI release documented here: `0.8.0`
- Current scaffolded contract schema examples: `fluidVersion: 0.7.2`

Those are different on purpose. `fluid version` reports the installed CLI release, while `fluidVersion` inside a contract selects the contract schema version.

## First-Run Path

```bash
pip install data-product-forge
fluid version
fluid doctor
fluid init my-project --quickstart
cd my-project
fluid validate contract.fluid.yaml
fluid plan contract.fluid.yaml
fluid apply contract.fluid.yaml --yes
```

Optional AI-assisted scaffolding uses `fluid forge`:

```bash
fluid forge
fluid forge --domain finance
fluid forge --llm-provider openai --llm-model gpt-4.1-mini
```

To forge a reviewable data model from a business intent file:

```bash
fluid forge data-model from-intent --example retail > intent.yaml
fluid forge data-model from-intent intent.yaml -o customer_orders.fluid.yaml
fluid generate transformation customer_orders.fluid.yaml -o ./dbt_customer_orders --dbt-validate
```

## Promoted Command Groups

| Group | Commands |
| --- | --- |
| Core Workflow | `init`, `forge`, `forge data-model`, `validate`, `plan`, `apply` |
| Generate | `generate transformation`, `generate schedule`, `generate ci`, `generate standard` |
| Integrations | `publish`, `market`, `import` |
| Quality & Governance | `policy-check`, `diff`, `test`, `verify` |
| Utilities | `config`, `split`, `bundle`, `auth`, `doctor`, `providers`, `memory`, `mcp`, `version` |

Compatibility commands such as `generate-airflow` are still documented, but the docs now lead with the promoted paths above.

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
├── README.md
├── getting-started/
├── cli/
├── providers/
├── walkthrough/
├── advanced/
└── .vuepress/
```

## Contributing

Docs-only pull requests are welcome. When a docs update depends on a CLI change, link the related `forge-cli` PR or issue in the description.
