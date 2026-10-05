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

- Current CLI release documented here: `0.18.1`
- Current scaffolded contract schema examples: `fluidVersion: 0.7.5`

Those are different on purpose. `fluid version` reports the installed CLI release, while `fluidVersion` inside a contract selects the contract schema version.

What changed in each release, and what to do when you upgrade:

- [Upgrade guide](https://agenticstiger.github.io/forge_docs/upgrading.html)
- [Release notes for 0.18.0 and 0.18.1](https://agenticstiger.github.io/forge_docs/RELEASE_NOTES_0.18.0.html), [0.17.0](https://agenticstiger.github.io/forge_docs/RELEASE_NOTES_0.17.0.html), [0.16.0](https://agenticstiger.github.io/forge_docs/RELEASE_NOTES_0.16.0.html)

## First-Run Path

```bash
pip install "data-product-forge[local]"
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
