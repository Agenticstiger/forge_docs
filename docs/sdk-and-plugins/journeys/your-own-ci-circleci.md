# CircleCI — the bundle template

> Part of [you have your own CI/CD setup, no problem](./your-own-ci.md). Read steps 0–2 there first — they set up the bundle repo and manifest that this template plugs into.

The complete `.circleci/config.yml.j2` template, ready to drop into your bundle's `templates/` directory.

## What this template does

- `jobs:` block defines validate + one deploy job per entry in the contract's `targets` variable.
- `workflows:` block sequences them: validate runs first; deploys run on main; prod has an approval gate via `type: approval`.
- Uses CircleCI's built-in Python image (`cimg/python:3.12`) — no Docker layer setup needed.

## `templates/.circleci/config.yml.j2`

```jinja
# Auto-generated CircleCI config for {{ product_id }}
# Rendered from {{ bundle.name }}@{{ bundle.version }} - do not edit by hand.

version: 2.1

jobs:
  validate:
    docker:
      - image: cimg/python:3.12
    steps:
      - checkout
      - run: pip install "data-product-forge=={{ fluid_cli_version | default('0.18.1') }}"
      - run: fluid validate contract.fluid.yaml --strict
{% for env_name, t in targets.items() %}
  deploy-{{ env_name }}:
    docker:
      - image: cimg/python:3.12
    steps:
      - checkout
      - run: pip install "data-product-forge=={{ fluid_cli_version | default('0.18.1') }}"
      - run: fluid apply contract.fluid.yaml --env {{ env_name }} --yes
{%- endfor %}

workflows:
  ci:
    jobs:
      - validate
{%- for env_name, t in targets.items() %}
{%- if env_name == "prod" %}
      # Manual approval gate: pauses until a human clicks "Approve" in the UI.
      - hold-{{ env_name }}:
          type: approval
          requires: [validate]
          filters: { branches: { only: [main] } }
      - deploy-{{ env_name }}:
          requires: [hold-{{ env_name }}]
          filters: { branches: { only: [main] } }
{%- else %}
      - deploy-{{ env_name }}:
          requires: [validate]
          filters: { branches: { only: [main] } }
{%- endif %}
{%- endfor %}
```

## What the template reads from the contract

The template uses the render-context names the engine provides (`product_id`, `owner`, `bundle`, ...) and one pattern variable, `targets`, which the product team supplies under `patterns[].variables` in their contract. The bundle manifest from [step 2](./your-own-ci.md#step-2-write-the-bundle-manifest) declares a JSON Schema for `targets`, so a missing or malformed value fails before any file is written.

```yaml
# contract.fluid.yaml (the product team's side)
extensions:
  customScaffold:
    libraries:
      - id: my-ci
        source: { kind: path, path: ../my-org-ci-bundle }
    patterns:
      - use: my-ci:circleci
        variables:
          targets:
            dev:  { provider: gcp, project: order-events-dev,  region: us-central1 }
            prod: { provider: gcp, project: order-events-prod, region: us-east1 }
```

This template reads only each target's name (`dev`, `prod`, ...); `provider` and `region` are validated by the manifest schema but not rendered.

## Why `type: approval` for prod

CircleCI's `type: approval` is a no-op job that pauses the workflow until a human clicks "Approve" in the UI. It's the cheapest gate you can ship:

- No external apps; nothing to install.
- The approver is recorded in the workflow log automatically.
- Combine with **Contexts** (org-scoped secret bundles) to scope what credentials are available *after* the approval — so a malicious workflow can't bypass approval and still get the prod secrets.

## Adding cloud credentials via Contexts

The template above doesn't show credential resolution — CircleCI prefers them injected via [Contexts](https://circleci.com/docs/contexts/) (org-level) rather than per-job. Once your platform team has created contexts `prod-aws-deploy`, `staging-aws-deploy`, etc., attach them in the workflow:

```yaml
workflows:
  ci:
    jobs:
      - deploy-prod:
          requires: [validate]
          context: prod-aws-deploy        # ← attaches AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
          type: approval
          filters: { branches: { only: [main] } }
```

You can extend the Jinja template to do this — add `context: {{ env_name }}-{{ t.provider }}-deploy` inside the per-env loop. The platform team owns the context name → secret mapping.

## Per-cloud orb shortcut

If your org uses CircleCI's official cloud orbs, the template gets shorter:

| Cloud | Orb | Replaces |
|---|---|---|
| `aws` | `circleci/aws-cli@5.x` | manual `aws configure` steps |
| `gcp` | `circleci/gcp-cli@3.x` | manual `gcloud auth activate-service-account` |

Add at the top of the rendered config:

```yaml
orbs:
  aws-cli: circleci/aws-cli@5.0
```

…then `aws-cli/setup` in the deploy job's steps does the OIDC dance for you.

## Next

- Back to the [main journey](./your-own-ci.md) — steps 4–7 (Dockerfile, README, static files, tagging, consumption).
- Other CI variants: [GitLab CI](./your-own-ci-gitlab.md), [GitHub Actions](./your-own-ci-github.md), [Jenkins](./your-own-ci-jenkins.md).
