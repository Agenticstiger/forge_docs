# Jenkins — the bundle template

> Part of [you have your own CI/CD setup, no problem](./your-own-ci.md). Read steps 0–2 there first — they set up the bundle repo and manifest that this template plugs into.

The complete `Jenkinsfile.j2` template, ready to drop into your bundle's `templates/` directory.

## What this template does

- Declarative pipeline syntax (`pipeline { … }`) — works with any Jenkins ≥ 2.290.
- One `stage('Deploy: <env>')` per environment declared in the contract.
- Uses Jenkins's built-in `input` block for the prod approval gate — pipeline pauses, a human clicks "Deploy to prod" before the stage runs.
- Resolves credentials per environment via [`withCredentials`](https://www.jenkins.io/doc/pipeline/steps/credentials-binding/) — no plaintext keys in the Jenkinsfile.

## `templates/Jenkinsfile.j2`

```jinja
// Auto-generated Jenkinsfile for {{ contract.metadata.id }}
// Rendered from my-org-ci-bundle@{{ bundle.version }} — do not edit by hand.

pipeline {
    agent any

    environment {
        PRODUCT_ID    = "{{ contract.metadata.id }}"
        PRODUCT_OWNER = "{{ contract.metadata.owner.email }}"
    }

    stages {
        stage('Validate') {
            steps {
                sh 'python -m pip install --quiet "data-product-forge=={{ fluid_cli_version | default(\'0.8.3\') }}"'
                sh 'fluid validate contract.fluid.yaml --strict'
            }
        }

{% for env_name, env in contract.environments.items() %}
        stage('Deploy: {{ env_name }}') {
            when { branch 'main' }
            {% if env_name == "prod" -%}
            input {
                message "Approve prod deploy of {{ contract.metadata.id }}?"
                ok "Deploy to prod"
            }
            {%- endif %}
            steps {
                {% if env.cloud.provider == "aws" -%}
                withCredentials([[$class: 'AmazonWebServicesCredentialsBinding',
                                 credentialsId: 'aws-{{ env_name }}-{{ env.cloud.account }}']]) {
                    sh 'fluid apply contract.fluid.yaml --env {{ env_name }} --yes'
                }
                {%- elif env.cloud.provider == "gcp" -%}
                withCredentials([file(credentialsId: 'gcp-{{ env_name }}-{{ env.cloud.project }}', variable: 'GOOGLE_APPLICATION_CREDENTIALS')]) {
                    sh 'fluid apply contract.fluid.yaml --env {{ env_name }} --yes'
                }
                {%- endif %}
            }
        }
{% endfor %}
    }
}
```

## Per-cloud credential conventions

The template assumes your Jenkins credentials are named with a per-env-per-account scheme:

| Cloud | Credential type | Naming convention | Renders to |
|---|---|---|---|
| `aws` | AWS Credentials (CloudBees AWS Credentials plugin) | `aws-<env>-<account>` | `aws-prod-333333333333` |
| `gcp` | Secret file (Google credentials JSON) | `gcp-<env>-<project>` | `gcp-prod-order-events-prod` |

Pre-create these in **Manage Jenkins → Credentials**. The template renders the right ID per env — the platform team only needs to keep credential names in sync with the contract's `environments` block.

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

## Jenkins-specific install-mode (pypi vs. dev-source)

If your Jenkins doesn't have internet egress, the forge-cli has a built-in [Jenkinsfile-generator](/forge_docs/cli/scaffold-ci.html) with two install modes:

- `--install-mode pypi` (production) — uses 4 build-time Jenkins parameters: `FLUID_PACKAGE_SPEC`, `FLUID_PIP_INDEX_URL`, `FLUID_PIP_EXTRA_INDEX_URL`, `FLUID_ALLOW_PRERELEASE`.
- `--install-mode dev-source` (lab) — uses `PYTHONPATH=/forge-cli-src` and fails loud if the mount is missing.

The bundle pattern above uses pypi-mode by default (`pip install` over the public index). For dev-source mode, replace the `python -m pip install` line in the template with:

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
