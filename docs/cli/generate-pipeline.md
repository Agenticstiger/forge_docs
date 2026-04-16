# `fluid generate-pipeline`

Generate a CI/CD pipeline configuration tailored to a chosen provider, complexity level, and environment list.

## Syntax

```bash
fluid generate-pipeline [--provider PROVIDER] [--complexity LEVEL] [--environments ...] [--output-dir DIR]
```

## Key options

| Option | Description |
| --- | --- |
| `--provider` | CI/CD provider — `github_actions`, `gitlab_ci`, `azure_devops`, `jenkins`, `bitbucket`, `circleci`, or `tekton`. Required unless `--interactive` is passed (or no provider is given, which auto-enables interactive mode). |
| `--complexity` | Pipeline complexity level — `basic`, `standard` (default), `advanced`, or `enterprise`. |
| `--environments` | Deployment environments (default `dev staging prod`). |
| `--enable-approvals` | Enable manual approval gates. |
| `--enable-security-scan` | Enable security scanning in the pipeline (default on). |
| `--enable-marketplace` | Enable marketplace publishing steps. |
| `--output-dir` | Directory to write pipeline files into (default `.`). |
| `--preview` | Print the first 500 chars of each generated file without writing to disk. |
| `--interactive` | Interactive prompt for provider, complexity, environments, and toggles. |

## Examples

```bash
fluid generate-pipeline --provider github_actions --complexity standard
fluid generate-pipeline --provider gitlab_ci --environments dev prod --enable-approvals
fluid generate-pipeline --provider jenkins --complexity enterprise --output-dir ci/
fluid generate-pipeline --interactive
```

## Notes

- Each generated file is prefixed with a provenance header naming the generator, timestamp, command, and a sha256 prefix; YAML files use `#`, `Jenkinsfile` uses `//`.
- A `ci-state.json` document is written next to the pipeline files so [`fluid forge`](./forge.md) on another machine can detect drift against the provider choice you just made.
- Providers passed as `circleci` are auto-aliased to the internal `circle_ci` name; use the underscore form when scripting.
- For a one-shot, single-file scaffold instead of the full template set, see [`fluid scaffold-ci`](./scaffold-ci.md). For Cloud Composer/Airflow DAGs see [`fluid scaffold-composer`](./scaffold-composer.md) or [`fluid generate-airflow`](./generate-airflow.md).
