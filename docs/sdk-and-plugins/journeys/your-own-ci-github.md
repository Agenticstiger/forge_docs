# GitHub Actions — the bundle template

> Part of [you have your own CI/CD setup, no problem](./your-own-ci.md). Read steps 0–2 there first — they set up the bundle repo and manifest that this template plugs into.

The complete `.github/workflows/ci.yml.j2` template, ready to drop into your bundle's `templates/` directory.

## What this template does

- One `validate` job + one `deploy-<env>` job per entry in the contract's `targets` variable.
- Uses **GitHub Environments** for the `prod` approval gate (configure approvers in repo settings → Environments).
- Authenticates via OIDC (no long-lived cloud keys) — switches on each target's `provider`.
- `needs: validate` makes every deploy job depend on a green validate.

## `templates/.github/workflows/ci.yml.j2`

```jinja
# Auto-generated GitHub Actions workflow for {{ product_id }}
# Rendered from {{ bundle.name }}@{{ bundle.version }} - do not edit by hand.

name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  workflow_dispatch:

# Least privilege: the workflow default is read-only. OIDC needs id-token: write,
# and only the deploy jobs below ask for it.
permissions:
  contents: read

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - uses: actions/setup-python@v6
        with:
          python-version: "3.12"
      - run: pip install "data-product-forge=={{ fluid_cli_version | default('0.18.1') }}"
      - run: fluid validate contract.fluid.yaml --strict
{% for env_name, t in targets.items() %}
  deploy-{{ env_name }}:
    needs: validate
    runs-on: ubuntu-latest
    permissions:
      id-token: write               # lets this job request an OIDC token
      contents: read
{%- if env_name == "prod" %}
    environment:
      name: production              # requires an approver gate in repo settings
{%- endif %}
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    steps:
      - uses: actions/checkout@v5
      - uses: actions/setup-python@v6
        with:
          python-version: "3.12"
      - run: pip install "data-product-forge=={{ fluid_cli_version | default('0.18.1') }}"
{%- if t.provider == "aws" %}
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::{{ t.account }}:role/forge-deploy
          aws-region: {{ t.region }}
{%- elif t.provider == "gcp" %}
      - uses: google-github-actions/auth@v3
        with:
          # Replace <pool> / <provider> with your Workload Identity Pool's IDs.
          workload_identity_provider: projects/{{ t.project_number }}/locations/global/workloadIdentityPools/<pool>/providers/<provider>
          service_account: forge-deploy@{{ t.project }}.iam.gserviceaccount.com
{%- endif %}
      - run: fluid apply contract.fluid.yaml --env {{ env_name }} --yes
{% endfor %}
```

::: tip Pin actions by commit SHA
A tag such as `actions/checkout@v5` can be moved. If your policy requires it, pin each `uses:` to a full commit SHA and keep the tag in a comment: `uses: actions/checkout@<full-commit-sha> # v5`.
:::

::: warning `id-token: write` reaches every step of the job
Any step in a job that has `id-token: write` can request an OIDC token, the `pip install` step included. Keep the permission on the deploy jobs only, as the template does, and keep those jobs to the steps that need the cloud.
:::

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
      - use: my-ci:github
        variables:
          targets:
            dev:  { provider: gcp, project: order-events-dev,  project_number: "111111111111", region: us-central1 }
            prod: { provider: aws, account: "333333333333",          region: eu-west-1 }
```

The GitHub template needs `account` for an `aws` target, and `project` plus `project_number` for a `gcp` target. A Workload Identity provider path uses the project **number**, not the project id.

## Per-cloud detail

| Cloud | Authentication action | Required setup |
|---|---|---|
| `aws` | [`aws-actions/configure-aws-credentials@v4`](https://github.com/aws-actions/configure-aws-credentials) | Pre-create `arn:aws:iam::<account>:role/forge-deploy` with a trust policy that pins the token's `sub` claim, as shown below. |
| `gcp` | [`google-github-actions/auth@v3`](https://github.com/google-github-actions/auth) | Pre-create a Workload Identity Pool + Provider for `token.actions.githubusercontent.com` with an attribute condition, as shown below, and a service account with `roles/iam.workloadIdentityUser`. |

### Scope the trust to one repository and environment

A trust policy that accepts any token from the GitHub OIDC issuer lets any repository on GitHub assume the role. Pin the token's subject. A job that declares `environment: production`, like the `prod` deploy job in the template, sends `sub` as `repo:<org>/<repo>:environment:production`. A job without an environment, like the other deploy jobs, sends `repo:<org>/<repo>:ref:refs/heads/main` when it runs on `main`.

For the AWS role, the production trust policy is:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::<account>:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
          "token.actions.githubusercontent.com:sub": "repo:<org>/<repo>:environment:production"
        }
      }
    }
  ]
}
```

For a non-production role, set the `sub` value to `repo:<org>/<repo>:ref:refs/heads/main`.

For GCP, set an attribute condition on the Workload Identity provider, so the provider rejects tokens from other repositories before any service-account binding is evaluated:

```text
# provider used by the production deploy job
assertion.repository == '<org>/<repo>' && assertion.environment == 'production'

# provider used by a non-production deploy job
assertion.repository == '<org>/<repo>' && assertion.ref == 'refs/heads/main'
```

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
