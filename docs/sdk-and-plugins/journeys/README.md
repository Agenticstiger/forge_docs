# Journeys

Each guide opens with a problem you might have and walks you to a working plugin end-to-end. Read in any order — they're independent. Most teams need two or three of these, not all four.

| You have… | Read | What you build |
|---|---|---|
| Your own CI/CD templates and don't want forge's defaults | [your-own-ci](./your-own-ci.md) | A git-distributed bundle that emits your CI files from contract data. Per-system templates: [GitLab](./your-own-ci-gitlab.md) · [GitHub Actions](./your-own-ci-github.md) · [Jenkins](./your-own-ci-jenkins.md) · [CircleCI](./your-own-ci-circleci.md) |
| A strict project layout (directory structure, lint config, Dockerfile, README template) | [your-own-scaffolding](./your-own-scaffolding.md) | A bundle that emits the full project skeleton — `pyproject.toml`, `src/<id>/`, tests, Dockerfile, pre-commit config |
| Governance rules — every product must declare a steward, classifications must come from a vocabulary, etc. | [custom-validator](./custom-validator.md) | A `Validator` plugin auto-discovered at `fluid validate`, distributed via `pip install` |
| An invariant that only matters at deploy time (env vars present, image signed, bundle digest matches) | [apply-hook](./apply-hook.md) | An apply hook that runs inside `fluid apply`, with a documented override flag |

## How journeys differ from examples

The [examples](../examples/) are reference: "here's a complete working plugin, every line shown." The journeys are how-tos framed by the problem: "here's the situation you're in, here's why this pattern fits, here's how to ship it."

If you're new to plugin authoring, **read the [quickstart](../quickstart.md) first** — it's the shortest path to a runnable plugin and gives you the mental model the journeys assume.

## What every journey has in common

All four journey guides share the same shape, so you can scan them the same way:

1. **The problem in one paragraph** — what you have, what you want, why this pattern is the right fit.
2. **The mental model in one diagram** — boxes and arrows for the data flow.
3. **A "see the result first" section** — what success looks like before you build anything.
4. **Step-by-step build** — every step has a "you'll see X when you run Y" check.
5. **Cloud / CI variations split out** — sub-pages per provider (e.g. GitLab / GitHub Actions / Jenkins / CircleCI for the CI journey) so the hub page stays scannable for the 80% who only care about one of them.
6. **"You'll know it worked when…"** — concrete acceptance criteria.
7. **"When NOT to use this pattern"** — honest about the limits.
8. **"Common gotchas"** — the failure modes I've seen, with the fix inlined.

## Source code

The plugins built in these journeys are mirrored from the SDK's `examples/` directory where possible, and the scaffold engine's reference bundle:

- **SDK examples:** [`Agenticstiger/forge-cli-sdk/examples/`](https://github.com/Agenticstiger/forge-cli-sdk/tree/main/examples)
- **Custom-scaffold reference bundle:** [`Agenticstiger/data-product-forge-custom-scaffold/tests/fixtures/reference_bundle/`](https://github.com/Agenticstiger/data-product-forge-custom-scaffold/tree/main/tests/fixtures/reference_bundle)

Every code block in the journeys is copy-paste runnable — no `# ...` stubs, no `raise NotImplementedError`.
