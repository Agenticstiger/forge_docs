# `fluid generate-pipeline`

Generate a CI/CD pipeline configuration tailored to a chosen provider, complexity level, and environment list.

::: warning Known issue in 0.18.1: `--provider` is refused
Since 0.14.0, `fluid` checks a `--provider` value against the infrastructure providers it has registered (`aws`, `datamesh_manager`, `gcp`, `local`, `redshift`, `snowflake`) and exits 2 on a miss. `fluid generate-pipeline --provider` takes a CI system (`github_actions`, `jenkins`, ...), so these values fail the check before the command runs:

```text
⚠️ Unknown provider 'github_actions' — installed providers: aws, datamesh_manager, gcp, local, redshift, snowflake (see `fluid providers`)
```

Nothing is written. Use [`fluid generate ci --system <system>`](./generate.md#fluid-generate-ci), or [`--interactive`](#interactive-mode), which asks for the CI system after the check has run.
:::

## Use instead

```bash
fluid generate ci --system github
fluid generate ci --system jenkins --out Jenkinsfile
fluid generate ci --system gitlab --complexity enterprise
```

`fluid generate ci` takes a contract, writes the pipeline for it and has the options listed on the [`fluid generate`](./generate.md#fluid-generate-ci) page. `generate-pipeline` does not take a contract; it writes a template set from a provider, a complexity level and an environment list.

## Syntax

```bash
fluid generate-pipeline [--provider PROVIDER] [--complexity LEVEL] [--environments ...] [--output-dir DIR]
```

## Key options

| Option | Description |
| --- | --- |
| `--provider` | CI/CD system — `github_actions`, `gitlab_ci`, `azure_devops`, `jenkins`, `bitbucket`, `circleci`, or `tekton`. As of 0.18.1 the command exits 2 for each of these values; see the known issue above. When it is omitted, the command asks for it interactively. |
| `--complexity` | Pipeline complexity level — `basic`, `standard` (default), `advanced`, or `enterprise`. |
| `--environments` | Deployment environments (default `dev staging prod`). |
| `--enable-approvals` | Enable manual approval gates. |
| `--enable-security-scan` | Enable security scanning in the pipeline (default on). |
| `--enable-marketplace` | Enable marketplace publishing steps. |
| `--output-dir` | Directory to write pipeline files into (default `.`). |
| `--preview` | Print the first 500 chars of each generated file without writing to disk. |
| `--interactive` | Interactive prompt for provider, complexity, environments, and toggles. |

## Interactive mode

With no `--provider`, the command prompts instead of failing:

```bash
fluid generate-pipeline --output-dir ci/
```

```text
Available CI/CD providers:
  1. Github Actions
  2. Gitlab Ci
  3. Azure Devops
  4. Jenkins
  5. Bitbucket
  6. Circle Ci
  7. Tekton

Select provider (1-7):
Pipeline complexity levels:
  1. Basic - Simple validate -> apply workflow
  2. Standard - Full workflow with testing and multi-environment
  3. Advanced - Multi-environment with approvals and security
  4. Enterprise - Full governance and compliance

Select complexity (1-4, default=2):
Use default environments (dev, staging, prod)? [Y/n]:
```

Choosing `Gitlab Ci` and the defaults wrote `.gitlab-ci.yml` and `.fluid/ci-state.json` under the output directory.

## Notes

- *(since 0.8.8)* The generated **apply stage** carries [`--ensure-opentofu`](./apply.md), so a cloud apply provisions a pinned, SHA-256-verified `tofu` on a fresh / non-root runner — no root, gpg, or cosign needed. It is idempotent and a no-op for native / `local` applies.
- Each generated pipeline file starts with a provenance header naming the generator and version, the timestamp, the command, and a sha256 prefix; YAML files use `#`, `Jenkinsfile` uses `//`.
- A `ci-state.json` document is written to `.fluid/ci-state.json` under the output directory, so [`fluid forge`](./forge.md) on another machine can detect drift against the provider choice you just made.
- The `--provider` spelling is `circleci`. `circle_ci` is not a choice, and the parser rejects it.
- For a one-shot, single-file scaffold instead of the full template set, see [`fluid scaffold-ci`](./scaffold-ci.md). For Cloud Composer/Airflow DAGs see [`fluid scaffold-composer`](./scaffold-composer.md) or [`fluid generate-airflow`](./generate-airflow.md).
