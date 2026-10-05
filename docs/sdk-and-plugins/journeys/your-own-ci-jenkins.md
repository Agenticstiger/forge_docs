# Jenkins — the bundle template

> Part of [you have your own CI/CD setup, no problem](./your-own-ci.md). Read steps 0–2 there first — they set up the bundle repo and manifest that this template plugs into.

The complete `Jenkinsfile.j2` template, ready to drop into your bundle's `templates/` directory.

## What this template does

- Declarative pipeline syntax (`pipeline { … }`) — works with any Jenkins ≥ 2.290.
- One `stage('Deploy: <env>')` per entry in the contract's `targets` variable.
- Uses Jenkins's built-in `input` block for the prod approval gate — pipeline pauses, a human clicks "Deploy to prod" before the stage runs.
- Resolves credentials per environment via [`withCredentials`](https://www.jenkins.io/doc/pipeline/steps/credentials-binding/) — no plaintext keys in the Jenkinsfile.

## `templates/Jenkinsfile.j2`

```jinja
// Auto-generated Jenkinsfile for {{ product_id }}
// Rendered from {{ bundle.name }}@{{ bundle.version }} - do not edit by hand.

pipeline {
    agent any

    environment {
        PRODUCT_ID    = "{{ product_id }}"
        PRODUCT_OWNER = "{{ owner.email }}"
    }

    stages {
        stage('Validate') {
            steps {
                sh 'python -m pip install --quiet "data-product-forge=={{ fluid_cli_version | default("0.18.1") }}"'
                sh 'fluid validate contract.fluid.yaml --strict'
            }
        }
{% for env_name, t in targets.items() %}
        stage('Deploy: {{ env_name }}') {
            when { branch 'main' }
{%- if env_name == "prod" %}
            input {
                message "Approve prod deploy of {{ product_id }}?"
                ok "Deploy to prod"
            }
{%- endif %}
            steps {
{%- if t.provider == "aws" %}
                withCredentials([[$class: 'AmazonWebServicesCredentialsBinding',
                                 credentialsId: 'aws-{{ env_name }}-{{ t.account }}']]) {
                    sh 'fluid apply contract.fluid.yaml --env {{ env_name }} --yes'
                }
{%- elif t.provider == "gcp" %}
                withCredentials([file(credentialsId: 'gcp-{{ env_name }}-{{ t.project }}', variable: 'GOOGLE_APPLICATION_CREDENTIALS')]) {
                    sh 'fluid apply contract.fluid.yaml --env {{ env_name }} --yes'
                }
{%- endif %}
            }
        }
{% endfor %}
    }
}
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
      - use: my-ci:jenkins
        variables:
          targets:
            dev:  { provider: gcp, project: order-events-dev,  region: us-central1 }
            prod: { provider: aws, account: "333333333333",     region: eu-west-1 }
```

## Per-cloud credential conventions

The template assumes your Jenkins credentials are named with a per-env-per-account scheme:

| Cloud | Credential type | Naming convention | Renders to |
|---|---|---|---|
| `aws` | AWS Credentials (CloudBees AWS Credentials plugin) | `aws-<env>-<account>` | `aws-prod-333333333333` |
| `gcp` | Secret file (Google credentials JSON) | `gcp-<env>-<project>` | `gcp-prod-order-events-prod` |

Pre-create these in **Manage Jenkins → Credentials**. The template renders the right ID per env — the platform team only needs to keep credential names in sync with the `targets` the product teams declare.

## Why the `input` block for prod

Three reasons it's the world-class choice on Jenkins:

1. **Discoverable.** Anyone looking at the pipeline page sees a "Deploy to prod" button. No separate approval app to install.
2. **Auditable.** Jenkins records who approved and when in the build log. Combine with `submitter` to scope approval to a specific group:
   ```groovy
   input {
       message "Approve prod deploy?"
       submitter "data-platform-admins"   // group name from your auth provider
       ok "Deploy"
   }
   ```
3. **Timeout-aware.** Wrap with `timeout(time: 1, unit: 'HOURS')` to auto-abort a stale approval — no abandoned pipelines holding agent slots.

## Jenkins-specific install mode (pypi vs. dev-source)

If you would rather not hand-write the Jenkinsfile, `fluid generate ci --system jenkins` emits one, with two install modes (see [`fluid generate ci`](../../cli/generate.md#fluid-generate-ci)):

- `--install-mode pypi` (default) installs `data-product-forge` from a package index. The pipeline exposes the install source as build parameters: `FLUID_PACKAGE_SPEC`, `FLUID_PIP_INDEX_URL`, `FLUID_PIP_EXTRA_INDEX_URL` and `FLUID_ALLOW_PRERELEASE`. pip takes the highest version across every index it is given, so for private packages use one mirror that proxies PyPI in `FLUID_PIP_INDEX_URL` and leave `FLUID_PIP_EXTRA_INDEX_URL` empty; see [Operating in CI](../../advanced/operating-in-ci.md#install).
- `--install-mode dev-source` (contributor labs) installs from a `/forge-cli-src` bind mount and fails loudly if the mount is missing.

The Jenkinsfile that `fluid generate ci` writes gives every parameter a default and reads each with the same default, so a job's first build, which runs without parameters, still works. Observed against a live Jenkins on 4-5 October 2026: Jenkins learns a pipeline's parameters from its first build, so a `buildWithParameters` call against a job that has never run is refused. Trigger one plain build first, then switch to parameterised triggers.

The bundle template above installs from the package index (`pypi` behaviour). For dev-source behaviour, replace the `python -m pip install` line in the template with:

```groovy
sh '''
  if [ ! -d /forge-cli-src ]; then
    echo "ERROR: /forge-cli-src not mounted; this Jenkinsfile expects dev-source mode" >&2
    exit 1
  fi
  export PYTHONPATH=/forge-cli-src
  fluid validate contract.fluid.yaml --strict
'''
```

## Next

- Back to the [main journey](./your-own-ci.md) — steps 4–7 (Dockerfile, README, static files, tagging, consumption).
- Other CI variants: [GitLab CI](./your-own-ci-gitlab.md), [GitHub Actions](./your-own-ci-github.md), [CircleCI](./your-own-ci-circleci.md).
