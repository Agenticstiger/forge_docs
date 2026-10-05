# GitLab CI — the bundle template

> Part of [you have your own CI/CD setup, no problem](./your-own-ci.md). Read steps 0–2 there first — they set up the bundle repo and manifest that this template plugs into.

The complete `.gitlab-ci.yml.j2` template, ready to drop into your bundle's `templates/` directory.

## What this template does

- Three stages: **validate**, **build**, **deploy**.
- One deploy job per entry in the contract's `targets` variable.
- Switches on each target's `provider` (`aws` / `gcp` / `snowflake`) to inject the right variables per cloud.
- The `prod` deploy is gated with `when: manual` so production deploys require a click in the UI.

## `templates/.gitlab-ci.yml.j2`

```jinja
# Auto-generated GitLab CI for {{ product_id }}
# Rendered from {{ bundle.name }}@{{ bundle.version }} - do not edit by hand.

stages: [validate, build, deploy]

variables:
  PRODUCT_ID: {{ product_id }}
  PRODUCT_OWNER: {{ owner.email }}

validate:
  stage: validate
  image: python:3.12
  script:
    - pip install --quiet "data-product-forge=={{ fluid_cli_version | default('0.18.1') }}"
    - fluid validate contract.fluid.yaml --strict

build:
  stage: build
  image: docker:24
  services: [docker:24-dind]
  script:
    - docker build -t $CI_REGISTRY_IMAGE:$CI_COMMIT_SHORT_SHA .
    - docker push $CI_REGISTRY_IMAGE:$CI_COMMIT_SHORT_SHA
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
{% for env_name, t in targets.items() %}
deploy:{{ env_name }}:
  stage: deploy
  image: python:3.12
  variables:
{%- if t.provider == "aws" %}
    AWS_ACCOUNT: "{{ t.account }}"
    AWS_REGION: {{ t.region }}
{%- elif t.provider == "gcp" %}
    GCP_PROJECT: {{ t.project }}
    GCP_REGION: {{ t.region }}
{%- elif t.provider == "snowflake" %}
    SF_ACCOUNT: "{{ t.account }}"
    SF_WAREHOUSE: {{ t.warehouse }}
    SF_ROLE: {{ t.role }}
{%- endif %}
  script:
    - pip install --quiet "data-product-forge=={{ fluid_cli_version | default('0.18.1') }}"
    - fluid apply contract.fluid.yaml --env {{ env_name }} --yes
  environment:
    name: {{ env_name }}
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
{%- if env_name == "prod" %}
      when: manual
{%- endif %}
{% endfor %}
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
      - use: my-ci:main
        variables:
          targets:
            dev:     { provider: gcp, project: order-events-dev,     region: us-central1 }
            staging: { provider: gcp, project: order-events-staging, region: us-central1 }
            prod:    { provider: gcp, project: order-events-prod,    region: us-east1 }
```

Each target needs `provider` and `region`. The keys the template reads beyond that depend on the provider: `account` (aws, snowflake), `project` (gcp), `warehouse` and `role` (snowflake). The template does not render a variables block for a provider it has no branch for.

## Per-cloud detail

The deploy job's `variables:` block injects what each cloud needs:

| Cloud | Variables injected | Authentication pattern |
|---|---|---|
| `aws` | `AWS_ACCOUNT`, `AWS_REGION` | Pair with a `before_script` that runs `aws sts assume-role-with-web-identity` using GitLab OIDC (no long-lived keys). |
| `gcp` | `GCP_PROJECT`, `GCP_REGION` | Pair with a `before_script` that runs `gcloud auth print-identity-token` against your workload identity pool. |
| `snowflake` | `SF_ACCOUNT`, `SF_WAREHOUSE`, `SF_ROLE` | Use Snowflake key-pair auth — store the private key in GitLab CI/CD variables masked + protected. |

For a fully OIDC-based deploy job, extend the deploy stage with a per-provider `before_script` block; the bundle pattern lets you keep that platform-team-owned.

## Why `when: manual` for prod

It's the cheapest, most discoverable approval gate GitLab ships. Every team understands "click the play button to deploy prod"; no separate approval-app config needed. If you need stronger guardrails (multiple approvers, audit log), upgrade to GitLab Premium's protected-environment rules — the bundle template stays the same.

## Next

- Back to the [main journey](./your-own-ci.md) — steps 4–7 (Dockerfile, README, static files, tagging, consumption).
- Other CI variants: [GitHub Actions](./your-own-ci-github.md), [Jenkins](./your-own-ci-jenkins.md), [CircleCI](./your-own-ci-circleci.md).
