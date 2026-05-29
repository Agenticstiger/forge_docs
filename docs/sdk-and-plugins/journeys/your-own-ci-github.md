# GitHub Actions — the bundle template

> Part of [you have your own CI/CD setup, no problem](./your-own-ci.md). Read steps 0–2 there first — they set up the bundle repo and manifest that this template plugs into.

The complete `.github/workflows/ci.yml.j2` template, ready to drop into your bundle's `templates/` directory.

## What this template does

- One `validate` job + one `deploy-<env>` job per environment declared in the contract.
- Uses **GitHub Environments** for the `prod` approval gate (configure approvers in repo settings → Environments).
- Authenticates via OIDC (no long-lived cloud keys) — switches on `env.cloud.provider`.
- `needs: validate` makes every deploy job depend on a green validate.

## `templates/.github/workflows/ci.yml.j2`

```jinja
# Auto-generated GitHub Actions workflow for {{ contract.metadata.id }}
# Rendered from my-org-ci-bundle@{{ bundle.version }} — do not edit by hand.

name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  workflow_dispatch:

# OIDC requires id-token: write on jobs that mint a cloud token.
permissions:
  id-token: write
  contents: read

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - uses: actions/setup-python@v6
        with:
          python-version: "3.12"
      - run: pip install "data-product-forge=={{ fluid_cli_version | default('0.8.6') }}"
      - run: fluid validate contract.fluid.yaml --strict

{% for env_name, env in contract.environments.items() %}
  deploy-{{ env_name }}:
    needs: validate
    runs-on: ubuntu-latest
    {% if env_name == "prod" -%}
    environment:
      name: production              # requires an approver gate in repo settings
    {%- endif %}
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    steps:
      - uses: actions/checkout@v5
      - uses: actions/setup-python@v6
        with:
          python-version: "3.12"
      - run: pip install "data-product-forge=={{ fluid_cli_version | default('0.8.6') }}"
      {% if env.cloud.provider == "aws" -%}
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::{{ env.cloud.account }}:role/forge-deploy
          aws-region: {{ env.cloud.region }}
      {%- elif env.cloud.provider == "gcp" -%}
      - uses: google-github-actions/auth@v3
        with:
          # Replace <pool> / <provider> with your Workload Identity Pool's IDs.
          workload_identity_provider: projects/{{ env.cloud.project }}/locations/global/workloadIdentityPools/<pool>/providers/<provider>
          service_account: forge-deploy@{{ env.cloud.project }}.iam.gserviceaccount.com
      {%- endif %}
      - run: fluid apply contract.fluid.yaml --env {{ env_name }} --yes

{% endfor %}
```

## Per-cloud detail

| Cloud | Authentication action | Required setup |
|---|---|---|
| `aws` | [`aws-actions/configure-aws-credentials@v4`](https://github.com/aws-actions/configure-aws-credentials) | Pre-create `arn:aws:iam::<account>:role/forge-deploy` with a trust policy that scopes to your repo via the GitHub OIDC issuer. |
| `gcp` | [`google-github-actions/auth@v3`](https://github.com/google-github-actions/auth) | Pre-create a Workload Identity Pool + Provider for `token.actions.githubusercontent.com` and a service account with `roles/iam.workloadIdentityUser`. |

Snowflake authentication is left out of the template above (Snowflake doesn't have an OIDC story in GitHub Actions yet). For Snowflake deploys, set `SNOWFLAKE_PRIVATE_KEY` as a repo secret and add a step that writes it to a key file before `fluid apply`.

## Why GitHub Environments for prod

Environment-based protection rules are the most discoverable, audit-friendly approval gate GitHub offers:

- **Approvers** — up to 6 named users/teams must click approve before the job starts.
- **Wait timer** — optional delay before a protected job runs.
- **Branch policy** — restrict the environment to specific branches/tags.
- **Audit log** — every approval lands in the org audit log automatically.

No external apps; no separate approval workflow. Configure once in repo settings → Environments → `production`.

## Next

- Back to the [main journey](./your-own-ci.md) — steps 4–7 (Dockerfile, README, static files, tagging, consumption).
- Other CI variants: [GitLab CI](./your-own-ci-gitlab.md), [Jenkins](./your-own-ci-jenkins.md), [CircleCI](./your-own-ci-circleci.md).
