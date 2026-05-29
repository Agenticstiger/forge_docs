# GitLab CI — the bundle template

> Part of [you have your own CI/CD setup, no problem](./your-own-ci.md). Read steps 0–2 there first — they set up the bundle repo and manifest that this template plugs into.

The complete `.gitlab-ci.yml.j2` template, ready to drop into your bundle's `templates/` directory.

## What this template does

- Three stages: **validate**, **build**, **deploy**.
- One deploy job per environment declared in the contract.
- Switches on `env.cloud.provider` (`aws` / `gcp` / `snowflake`) to inject the right env vars per cloud.
- The `prod` deploy is gated with `when: manual` so production deploys require a click in the UI.

## `templates/.gitlab-ci.yml.j2`

```jinja
# Auto-generated GitLab CI for {{ contract.metadata.id }}
# Rendered from my-org-ci-bundle@{{ bundle.version }} — do not edit by hand.

stages: [validate, build, deploy]

variables:
  PRODUCT_ID: {{ contract.metadata.id }}
  PRODUCT_OWNER: {{ contract.metadata.owner.email }}

validate:
  stage: validate
  image: python:3.12
  script:
    - pip install --quiet "data-product-forge=={{ fluid_cli_version | default('0.8.6') }}"
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

{% for env_name, env in contract.environments.items() %}
deploy:{{ env_name }}:
  stage: deploy
  image: python:3.12
  variables:
{% if env.cloud.provider == "aws" %}
    AWS_ACCOUNT: "{{ env.cloud.account }}"
    AWS_REGION:  {{ env.cloud.region }}
{% elif env.cloud.provider == "gcp" %}
    GCP_PROJECT: {{ env.cloud.project }}
    GCP_REGION:  {{ env.cloud.region }}
{% elif env.cloud.provider == "snowflake" %}
    SF_ACCOUNT:   "{{ env.cloud.account }}"
    SF_WAREHOUSE: {{ env.cloud.warehouse }}
    SF_ROLE:      {{ env.cloud.role }}
{% endif %}
  script:
    - pip install --quiet "data-product-forge=={{ fluid_cli_version | default('0.8.6') }}"
    - fluid apply contract.fluid.yaml --env {{ env_name }} --yes
  environment:
    name: {{ env_name }}
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
      {% if env_name == "prod" %}when: manual{% endif %}

{% endfor %}
```

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
