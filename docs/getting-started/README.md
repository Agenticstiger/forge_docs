# Getting Started

Run your first data product locally in a few minutes, then move to cloud targets when you are ready.

## What this guide assumes

- Python `3.9+`
- `pip`
- No cloud credentials required for the local-first path

## Install the CLI

Stable release from PyPI:

```bash
pip install data-product-forge
```

Pre-release candidates (alpha / beta / rc — ahead of PyPI by one release) live on TestPyPI:

```bash
pip install --pre \
  --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ \
  data-product-forge
```

The `--extra-index-url` keeps transitive dependencies (pandas, pydantic, dbt-core, …) resolvable from normal PyPI while the CLI itself comes from TestPyPI.

Check the installed CLI and basic system health:

```bash
fluid version
fluid doctor
```

This docs set tracks CLI release `0.8.0`. Docs updates land in lockstep with each release; if you're on an older CLI, some `--mode` / `--target` flags mentioned here won't be present yet — see the [CLI index](../cli/README.md) for what maps to what.

> Stuck on install? Jump to [Troubleshooting](#troubleshooting) further down, or [open an issue](https://github.com/Agenticstiger/forge-cli/issues) — happy to help.

## Understand the version numbers

You will see two different version concepts in the docs:

- `fluid version` reports the installed CLI release, such as `0.8.0`
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

## Beyond dev — the 11-stage production pipeline

The commands above are the dev on-ramp. For production, `0.8.0` promotes an 11-stage pipeline with cryptographic plan-binding, explicit destruction gating, and supply-chain signing:

```
1. bundle → 2. validate → 3. generate-artifacts → 4. validate-artifacts
      → 5. diff (drift gate) → 6. plan → 7. apply → 8. policy-apply
      → 9. verify → 10. publish → 11. schedule-sync (Path A only)
```

See the [11-stage pipeline walkthrough](../walkthrough/11-stage-pipeline.md) for the full end-to-end flow and [`fluid generate ci`](../cli/generate.md) for auto-generating a parameterised pipeline for Jenkins / GitHub Actions / GitLab / Azure DevOps / Bitbucket / CircleCI / Tekton.

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

- [GCP guide](/forge_docs/providers/gcp)
- [AWS guide](/forge_docs/providers/aws)
- [Snowflake quickstart](/forge_docs/getting-started/snowflake)
- [Provider overview](/forge_docs/providers/)

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

- [CLI Reference](/forge_docs/cli/)
- [Local walkthrough](/forge_docs/walkthrough/local)
- [Vision](/forge_docs/vision)

---

## Need help?

- **Questions or ideas?** [Start a GitHub Discussion](https://github.com/Agenticstiger/forge-cli/discussions)
- **Bug or unexpected behavior?** [Open an issue](https://github.com/Agenticstiger/forge-cli/issues) with what you ran and what you saw
- **Want to contribute?** See [the contributing guide](../contributing.md)
