# Getting Started

Run your first data product locally in a few minutes, then move to cloud targets when you are ready.

## What this guide assumes

- Python `3.9+`
- `pip`
- No cloud credentials required for the local-first path

## Install the CLI

```bash
pip install fluid-forge
```

Check the installed CLI and basic system health:

```bash
fluid version
fluid doctor
```

This docs set tracks CLI release `0.7.9`.

## Understand the version numbers

You will see two different version concepts in the docs:

- `fluid version` reports the installed CLI release, such as `0.7.9`
- `fluidVersion` inside `contract.fluid.yaml` selects the contract schema version, such as `0.7.2`

Current scaffolds in `forge-cli` emit `fluidVersion: 0.7.2`.

## Quickstart with `fluid init`

Create a local project:

```bash
fluid init my-project --quickstart
cd my-project
```

Then run the core workflow:

```bash
fluid validate contract.fluid.yaml
fluid plan contract.fluid.yaml
fluid apply contract.fluid.yaml --yes
```

## What the quickstart gives you

The generated project includes a working contract plus local assets so you can validate and apply immediately. The exact scaffold evolves over time, but the important files are:

```text
my-project/
├── README.md
├── contract.fluid.yaml
├── data/
└── .fluid/
```

## Optional AI-assisted path with `fluid forge`

If you want the CLI to discover local context and scaffold with LLM help, use `fluid forge` instead of `fluid init`:

```bash
fluid forge
fluid forge --domain finance
fluid forge --llm-provider openai --llm-model gpt-4o-mini
```

Use `fluid init` for the fastest deterministic quickstart. Use `fluid forge` when you want discovery, memory, or domain-guided scaffolding.

## Promoted next commands

```bash
fluid test contract.fluid.yaml
fluid verify contract.fluid.yaml
fluid generate schedule --scheduler airflow
fluid publish contract.fluid.yaml
```

Compatibility note:
`fluid generate-airflow` still exists, but the promoted orchestration path is `fluid generate schedule --scheduler airflow`.

## Move to providers later

When you are ready to target a provider:

- [GCP guide](/providers/gcp)
- [AWS guide](/providers/aws)
- [Snowflake quickstart](/getting-started/snowflake)
- [Provider overview](/providers/)

## Troubleshooting

### `fluid: command not found`

Try the module entry point:

```bash
python -m fluid_build.cli --help
```

### Local quickstart dependencies look incomplete

Run:

```bash
fluid doctor --verbose
```

### Unsure what to use next

Use the CLI help pages:

```bash
fluid --help
fluid <command> -h
```

## Next steps

- [CLI Reference](/cli/)
- [Local walkthrough](/walkthrough/local)
- [Vision](/vision)
