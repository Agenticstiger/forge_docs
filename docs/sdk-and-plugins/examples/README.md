# Runnable examples

Four plugins, smallest → largest, each one a complete walkthrough you can copy-paste and run. Three are mirrored from the upstream SDK repo's `examples/` directory; the fourth is a worked illustration of an apply hook.

| Example | Role | ~LOC | What it demonstrates |
|---|---|---|---|
| [`hello-scaffold`](./hello-scaffold.md) | `CustomScaffold` | 30 | The minimum viable plugin: one file output, one entry-point, ~20 inherited tests |
| [`gitlab-ci-scaffold`](./gitlab-ci-scaffold.md) | `CustomScaffold` | 140 | Realistic multi-file plugin: README + `.gitlab-ci.yml` + per-env config |
| [`steward-validator`](./steward-validator.md) | `Validator` | 90 | Governance rule with severity bucketing; runs at `fluid validate` |
| [`apply-hook-prod-key-guard`](./apply-hook-prod-key-guard.md) | apply hook | ~60 | Runtime invariant check at `fluid apply`; not a class, just a function |

If you're new, **read them in this order**. Each one builds on the concepts in the previous; by the apply-hook example the three entry-point groups and the role taxonomy should feel familiar.

## Source

Three of the four ship as runnable Python projects inside the SDK repo:

- [`hello-scaffold`](https://github.com/Agenticstiger/forge-cli-sdk/tree/main/examples/hello-scaffold)
- [`gitlab-ci-scaffold`](https://github.com/Agenticstiger/forge-cli-sdk/tree/main/examples/gitlab-ci-scaffold)
- [`steward-validator`](https://github.com/Agenticstiger/forge-cli-sdk/tree/main/examples/steward-validator)

Each has its own `pyproject.toml`, runnable `demo.py`, and full test suite. `pip install -e .[dev] && pytest` works in any of them out of the box.

## After the examples — pick your journey

The examples are reference; the [journeys](../journeys/) are how-tos framed by the problem you're solving:

- **You have your own CI/CD setup** → [your-own-ci](../journeys/your-own-ci.md)
- **You have a strict project layout** → [your-own-scaffolding](../journeys/your-own-scaffolding.md)
- **You have governance rules** → [custom-validator](../journeys/custom-validator.md)
- **You want a check at apply time** → [apply-hook](../journeys/apply-hook.md)
