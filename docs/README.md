---
home: true
heroImage: /logo.png
heroText: Fluid Forge
tagline: Contract-first data products, from local DuckDB to multi-cloud delivery.
actions:
  - text: Get Started →
    link: /getting-started/
    type: primary
  - text: CLI Reference
    link: /cli/
    type: secondary

features:
  - title: Local First
    details: Install the CLI, scaffold a project, validate it, and run it locally before you touch cloud credentials.
  - title: Contract-Driven
    details: Use one FLUID contract to describe the data product, then plan, test, verify, and publish from the same source of truth.
  - title: Promoted CLI Surface
    details: These docs track the current `fluid --help` experience so new users are not sent down stale or deprecated command paths.
  - title: AI-Optional
    details: Start with `fluid init` for a quickstart or use `fluid forge` when you want AI-assisted scaffolding and discovery.
  - title: Multi-Target Delivery
    details: Build locally with DuckDB, then target GCP, AWS, Snowflake, or standards/export flows when you are ready.
  - title: Compatibility Aware
    details: Legacy commands still exist in the docs where they matter, but primary pages lead with the current recommended workflow.

footer: Apache 2.0 Licensed | Documentation for the Fluid Forge CLI
---

## Start with the current workflow

```bash
pip install fluid-forge
fluid version
fluid doctor
fluid init my-project --quickstart
cd my-project
fluid validate contract.fluid.yaml
fluid plan contract.fluid.yaml
fluid apply contract.fluid.yaml --yes
```

This docs site currently tracks:

- CLI release `0.7.9`
- Scaffolded contract examples using `fluidVersion: 0.7.2`

`fluid version` and `fluidVersion` are different things. The first is the CLI release you installed. The second is the schema version inside a contract.

## Optional AI-assisted scaffolding

```bash
fluid forge
fluid forge --domain retail
fluid forge --llm-provider openai --llm-model gpt-4o-mini
```

Use `fluid forge` when you want discovery, memory, and LLM-guided scaffolding. Use `fluid init` when you want the fastest deterministic quickstart.

## Promoted command groups

| Group | Commands |
| --- | --- |
| Core Workflow | `init`, `forge`, `validate`, `plan`, `apply` |
| Generate | `generate transformation`, `generate schedule`, `generate ci`, `generate standard` |
| Integrations | `publish`, `market`, `import` |
| Quality & Governance | `policy-check`, `diff`, `test`, `verify` |
| Utilities | `config`, `split`, `bundle`, `auth`, `doctor`, `providers`, `version` |

## Where to go next

- [Getting Started](/getting-started/) for the local-first path
- [CLI Reference](/cli/) for the promoted command surface
- [Providers](/providers/) for platform-specific guidance
- [Walkthroughs](/walkthrough/local) for end-to-end examples

Compatibility note:
`fluid generate-airflow` is still available, but primary docs now lead with `fluid generate schedule --scheduler airflow`.
