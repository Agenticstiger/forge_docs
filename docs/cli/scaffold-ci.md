# `fluid scaffold-ci`

Generate a CI pipeline file for GitLab, GitHub Actions, or Jenkins that wires together the FLUID validate / generate / plan / apply stages.

## Syntax

```bash
fluid scaffold-ci CONTRACT [--system {gitlab,github,jenkins}] [--out PATH]
```

## Key options

| Option | Description |
| --- | --- |
| `CONTRACT` | Path to `contract.fluid.yaml` (positional, required). |
| `--system` | CI system to target — `gitlab` (default), `github`, or `jenkins`. |
| `--out` | Output path for the generated pipeline file (default `.gitlab-ci.yml`). |

## Examples

```bash
fluid scaffold-ci contract.fluid.yaml
fluid scaffold-ci contract.fluid.yaml --system github --out .github/workflows/fluid.yml
fluid scaffold-ci contract.fluid.yaml --system jenkins --out Jenkinsfile
```

## Notes

- The generated pipeline references `$CONTRACT` and `$PROVIDER` env vars and runs `python -m fluid_build.cli ...` for each stage.
- The `apply` stage is gated: `manual` in GitLab, `workflow_dispatch` in GitHub Actions, and an `input` step on the `main` branch in Jenkins.
- The default `--out` value is `.gitlab-ci.yml` regardless of `--system`; pass `--out` explicitly when targeting GitHub or Jenkins.
- For producing the FLUID artifacts the pipeline drives, see [`fluid generate`](./generate.md), [`fluid plan`](./plan.md), and [`fluid apply`](./apply.md).
