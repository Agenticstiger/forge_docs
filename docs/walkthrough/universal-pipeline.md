# Universal Pipeline

One hand-written Jenkinsfile for every provider, with no provider branches in it: the contract's `binding.platform` selects the provider.

**Docs baseline:** CLI `0.18.1`

::: tip Starting a new pipeline?
`fluid generate ci --system jenkins` writes a pipeline for you that runs the bundle chain, checks the digests between stages and gives every parameter a default, so the first build runs with them. See [Jenkins CI/CD](./jenkins-cicd.md) and [The 11-stage pipeline](./11-stage-pipeline.md). This page is for teams that keep a Jenkinsfile of their own and want one that does not change per cloud.
:::

---

## The Problem

Traditional CI/CD pipelines grow provider-specific branches:

```groovy
// DON'T DO THIS — brittle, doesn't scale
if (provider == 'gcp') {
    withCredentials([file(credentialsId: 'gcp-key', variable: 'GCP_KEY')]) {
        sh "gcloud auth activate-service-account --key-file=$GCP_KEY"
        sh "fluid apply contract.yaml --provider gcp --project $GCP_PROJECT"
    }
} else if (provider == 'aws') {
    withCredentials([usernamePassword(credentialsId: 'aws-creds', ...)]) {
        sh "fluid apply contract.yaml --provider aws"
    }
} else if (provider == 'snowflake') {
    // ... more branching
}
```

Every new provider means editing the Jenkinsfile. Every credential format needs its own block. Every CLI call needs provider flags.

## The Solution

The pipeline carries no provider logic. The contract declares `binding.platform`, and the CLI reads it.

### How It Works

```
┌────────────────────────────────────────────────────────────┐
│                         Jenkinsfile                         │
│                   Zero provider logic                      │
│                                                            │
│   Setup ──▶ Validate ──▶ Export ──▶ Compile IAM ──▶ Plan   │
│     │                                                      │
│     ▼                                                      │
│   Apply ──▶ Apply IAM ──▶ Execute ──▶ Airflow DAG         │
│                                                            │
│   Credential auto-detection:                               │
│   • JSON file? → GCP service account                      │
│   • KEY=VALUE file? → AWS / Snowflake / anything           │
└────────────────────────────────────────────────────────────┘
         │                  │                  │
    ┌────▼────┐       ┌────▼────┐       ┌────▼────┐
    │   GCP   │       │   AWS   │       │Snowflake│
    │ BigQuery│       │S3+Athena│       │  Table  │
    └─────────┘       └─────────┘       └─────────┘
    Same commands.     Same commands.    Same commands.
```

### Key Design Decisions

| Decision | Implementation |
|----------|---------------|
| **Credentials** | Single Jenkins Secret File → auto-detect JSON (GCP) vs env vars (everything else) |
| **Provider detection** | CLI reads `binding.platform` from contract — no `--provider` flag |
| **Project and region** | Read from the expose's `binding.location`; the credentials supply the identity. The pipeline passes no `--project` or `--region` |
| **Dependencies** | Single `requirements.txt` per example (not `requirements-aws.txt`) |
| **Env loading** | `set -a; . .fluid-env; set +a` in every stage — works for any provider |

## The Jenkinsfile

This is the complete Jenkinsfile. The same file runs against GCP, AWS and Snowflake contracts:

::: danger Do not run this Jenkinsfile with production credentials as written
It demonstrates a provider-agnostic structure. It also has these defects:

- **Credentials come from the checkout.** With `CREDENTIALS_ID` empty, Setup copies a `.env` from the repository into `.fluid-creds`. Every stage then runs `set -a; . .fluid-env`, which executes the file as shell. Anyone whose change the job builds controls what runs with the build's credentials.
- **The secret is copied out of `withCredentials`.** Setup writes the Secret File into the workspace (`.fluid-creds`, `.fluid-env`, `.gcp-key.json`) and every stage sources it, including `pip3 install -r requirements.txt` in Execute Builds, which runs code from the repository's dependencies with the credentials in its environment.
- **Build permission is root on the host.** `FLUID_IMAGE` is a free-text parameter and the agent mounts `/var/run/docker.sock`, so whoever may start a build can run any image with control of the host's Docker daemon.
- **A build picks its own credentials.** `CREDENTIALS_ID` is free text, so a build of a dev branch can name the production credential.
- **The credentials are long-lived and broad.** The header comment shows an `AKIA...` access key and `SNOWFLAKE_ROLE=SYSADMIN`.
- **`main` deploys to production without a gate.** `ENV` is `prod` on `main`, and `fluid apply --yes` runs with no `input` step before it.

For a pipeline you will run, use `fluid generate ci --system jenkins`. Its Jenkinsfile has no `.env` fallback and no Docker socket mount, takes credentials from the agent or from Jenkins credentials you bind, and defaults `APPLY_MODE` to `dry-run`. See [Jenkins CI/CD](./jenkins-cicd.md#give-the-pipeline-credentials), and [Require approval before apply](./jenkins-cicd.md#require-approval-before-apply) for the gate.
:::

```groovy
#!/usr/bin/env groovy
/**
 * FLUID universal pipeline — provider-agnostic
 *
 * This pipeline runs ANY FLUID data product on ANY provider without modification.
 * Zero provider-specific logic lives here — the contract is the single source of truth.
 *
 * Credentials convention:
 *   Create a Jenkins "Secret File" credential containing shell-exportable env vars:
 *
 *   GCP credentials file:          AWS credentials file:         Snowflake credentials file:
 *     (raw SA JSON key works too)   AWS_ACCESS_KEY_ID=AKIAxxx    SNOWFLAKE_ACCOUNT=xxx
 *     GCP_PROJECT=my-project        AWS_SECRET_ACCESS_KEY=xxx    SNOWFLAKE_USER=xxx
 *                                   AWS_REGION=eu-central-1      SNOWFLAKE_PASSWORD=xxx
 *                                   S3_BUCKET=my-bucket          SNOWFLAKE_WAREHOUSE=COMPUTE_WH
 *                                                                SNOWFLAKE_ROLE=SYSADMIN
 *
 *   For GCP, the Secret File can be the raw service-account JSON key —
 *   the pipeline auto-detects JSON vs env-file format.
 *
 * Adding a new provider:
 *   1. Add a provider to the FLUID CLI (fluid_build/providers/)
 *   2. Set binding.platform in your contract
 *   3. Create a credentials file with the env vars your provider needs
 *   4. That's it — this Jenkinsfile doesn't change
 */

pipeline {
    agent {
        docker {
            image "${params.FLUID_IMAGE}"
            alwaysPull true
            args '-v /var/run/docker.sock:/var/run/docker.sock --entrypoint='
        }
    }

    environment {
        HOME = "${WORKSPACE}"
        ENV  = "${BRANCH_NAME == 'main' ? 'prod' : BRANCH_NAME == 'develop' ? 'staging' : 'dev'}"
    }

    parameters {
        string(name: 'CONTRACT_FILE',  defaultValue: 'contract.fluid.yaml',
               description: 'FLUID contract file')
        string(name: 'FLUID_IMAGE',    defaultValue: 'registry.example.com/fluid-cli:latest',
               description: 'FLUID CLI Docker image')
        string(name: 'CREDENTIALS_ID', defaultValue: '',
               description: 'Jenkins Secret File credential ID (leave empty for .env fallback)')
        booleanParam(name: 'RUN_EXECUTION', defaultValue: true,
               description: 'Execute builds after infrastructure apply')
        booleanParam(name: 'ENFORCE_IAM',   defaultValue: true,
               description: 'Enforce IAM/RBAC policies from contract')
    }

    options {
        timeout(time: 30, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '20'))
        disableConcurrentBuilds()
    }

    stages {
        // ── Setup: load credentials, detect provider ─────────
        stage('Setup') {
            steps {
                script {
                    if (!fileExists(params.CONTRACT_FILE)) {
                        error "Contract not found: ${params.CONTRACT_FILE}"
                    }
                    if (params.CREDENTIALS_ID) {
                        withCredentials([file(credentialsId: params.CREDENTIALS_ID,
                                              variable: 'CREDS_FILE')]) {
                            sh "cp \$CREDS_FILE ${WORKSPACE}/.fluid-creds"
                        }
                    } else if (fileExists('.env')) {
                        sh "cp .env ${WORKSPACE}/.fluid-creds"
                    }
                }
                // Auto-detect: JSON → GCP key; otherwise → env vars
                sh '''
                    if [ -f .fluid-creds ]; then
                        if python3 -c "import json; d=json.load(open('.fluid-creds')); \
                           assert d.get('type')=='service_account'" 2>/dev/null; then
                            cp .fluid-creds .gcp-key.json
                            PROJECT=$(python3 -c "import json; \
                              print(json.load(open('.gcp-key.json')).get('project_id',''))")
                            printf "GOOGLE_APPLICATION_CREDENTIALS=%s/.gcp-key.json\n\
                              GCP_PROJECT=%s\n" "$WORKSPACE" "$PROJECT" > .fluid-env
                            echo "Loaded GCP service account (project: ${PROJECT})"
                        else
                            grep -v '^#' .fluid-creds | grep -v '^$' \
                              | sed 's/^export //' > .fluid-env
                            echo "Loaded credentials from env file"
                        fi
                    else
                        touch .fluid-env
                        echo "No credentials file — using inherited environment"
                    fi
                '''
                sh '''
                    set -a; . .fluid-env; set +a
                    echo "=================================================="
                    echo "  FLUID Pipeline"
                    echo "=================================================="
                    echo "Contract : ${CONTRACT_FILE}"
                    echo "Env      : ${ENV}"
                    fluid --version 2>/dev/null || echo "CLI version unavailable"
                    python3 --version
                '''
            }
        }

        // ── Validate → Export → Compile → Plan → Test ────────
        stage('Validate Contract') {
            steps {
                sh '''
                    set -a; . .fluid-env; set +a
                    mkdir -p reports
                    fluid validate ${CONTRACT_FILE} --verbose \
                      2>&1 | tee reports/validation.log
                '''
            }
        }

        stage('Export Standards') {
            steps {
                sh '''
                    mkdir -p standards
                    fluid odps export ${CONTRACT_FILE} \
                      --out standards/product.odps.json
                    fluid odcs export ${CONTRACT_FILE} \
                      --output standards/product.odcs.yaml
                '''
            }
        }

        stage('Compile IAM Policies') {
            steps {
                sh '''
                    set -a; . .fluid-env; set +a
                    mkdir -p runtime/policy
                    fluid policy-compile ${CONTRACT_FILE} \
                        --env ${ENV} \
                        --out runtime/policy/bindings.json
                '''
            }
        }

        stage('Generate Plan') {
            steps {
                sh '''
                    set -a; . .fluid-env; set +a
                    mkdir -p plans
                    fluid plan ${CONTRACT_FILE} \
                      --env ${ENV} --out plans/plan-${ENV}.json
                '''
            }
        }

        stage('Run Tests') {
            steps {
                sh '''
                    set -a; . .fluid-env; set +a
                    if [ -f contract-baseline/baseline.schema.json ]; then
                        fluid contract-tests ${CONTRACT_FILE} \
                          --baseline contract-baseline/baseline.schema.json
                    else
                        echo "No contract-baseline/baseline.schema.json: nothing to compare against"
                    fi
                '''
            }
        }

        // ── Apply infrastructure + IAM ───────────────────────
        stage('Apply Infrastructure') {
            steps {
                sh '''
                    set -a; . .fluid-env; set +a
                    mkdir -p runtime
                    fluid apply ${CONTRACT_FILE} \
                        --env ${ENV} --yes \
                        --report runtime/apply-report-${ENV}.html
                '''
            }
        }

        stage('Apply IAM Policies') {
            steps {
                sh """
                    set -a; . .fluid-env; set +a
                    if [ -f runtime/policy/bindings.json ]; then
                        COUNT=\$(python3 -c "import json; \
                          print(len(json.load(open('runtime/policy/bindings.json')) \
                          .get('bindings',[])))" 2>/dev/null || echo 0)
                        if [ "\$COUNT" != "0" ]; then
                            echo "Applying \$COUNT IAM binding(s)..."
                            fluid policy-apply runtime/policy/bindings.json \
                                --mode ${params.ENFORCE_IAM ? 'enforce' : 'check'}
                        else
                            echo "No IAM bindings to apply"
                        fi
                    fi
                """
            }
        }

        // ── Execute builds + generate Airflow DAG ────────────
        stage('Execute Builds') {
            when { expression { params.RUN_EXECUTION } }
            steps {
                sh '''
                    set -a; . .fluid-env; set +a
                    [ -f requirements.txt ] && pip3 install --quiet -r requirements.txt
                    fluid apply ${CONTRACT_FILE} --env ${ENV} --yes \
                        --mode amend-and-build
                '''
            }
        }

        stage('Generate Airflow DAG') {
            steps {
                sh '''
                    fluid generate schedule ${CONTRACT_FILE} \
                        --scheduler airflow --env ${ENV} \
                        --output airflow-dags/
                    for dag in airflow-dags/*.py; do
                        python3 -m py_compile "$dag" && echo "DAG valid: $dag"
                    done
                '''
            }
        }

        // ── Summary ──────────────────────────────────────────
        stage('Summary') {
            steps {
                sh '''
                    echo "=================================================="
                    echo "  FLUID Pipeline Complete"
                    echo "=================================================="
                    grep -m1 "^id:" ${CONTRACT_FILE}   | cut -d" " -f2
                    grep -m1 "^name:" ${CONTRACT_FILE}  | cut -d" " -f2-
                    echo "Env: ${ENV}"
                    echo ""
                    echo "Artifacts:"
                    ls -lh reports/*.log 2>/dev/null                    || true
                    ls -lh runtime/apply-report-${ENV}.html 2>/dev/null || true
                    ls -lh runtime/policy/bindings.json 2>/dev/null     || true
                    ls -lh airflow-dags/*.py 2>/dev/null                || true
                '''
            }
        }
    }

    post {
        always {
            sh 'rm -f .fluid-creds .fluid-env .gcp-key.json 2>/dev/null || true'
            archiveArtifacts artifacts: '**/*.log, **/*.json, **/*.html, **/*.py',
                             allowEmptyArchive: true
            deleteDir()
        }
    }
}
```

## Side-by-Side: Same Pipeline, Different Clouds

The Jenkinsfile does not change. The contract's binding and the credentials do. Keep each cloud's binding in an overlay (`overlays/<name>.yaml` beside the contract) and select it with `--env`; this pipeline derives its `ENV` from the branch name, so name the overlays `dev`, `staging` and `prod`, or make `ENV` a build parameter when the overlays are named for clouds. See [Switch clouds](../recipes/switch-clouds.md).

### What Differs Per Provider

| | GCP | AWS | Snowflake |
|---|-----|-----|-----------|
| **Contract** | `binding.platform: gcp` | `binding.platform: aws` | `binding.platform: snowflake` |
| **Format** | `bigquery_table` | `parquet` | `snowflake_table` |
| **Location** | `project`, `dataset`, `table` | `bucket`, `path`, `region`, `database`, `table` | `account`, `database`, `schema`, `table` |
| **Credential file** | GCP SA JSON key | `AWS_ACCESS_KEY_ID=...` | `SNOWFLAKE_ACCOUNT=...` |
| **Jenkinsfile** | **Identical** | **Identical** | **Identical** |
| **CLI commands** | **Identical** | **Identical** | **Identical** |

::: warning AWS: `accessPolicy` alone is not enforced
Since 0.17.0, `fluid validate` warns when an `aws` binding has `accessPolicy.grants` and no `governance.lakeFormation.grants`, because the AWS emitter does not write `accessPolicy`. The Validate stage above runs without `--strict`, so it is a warning here; a pipeline that validates with `--strict`, as the generated Jenkins pipeline does by default, fails on it.
:::

### Credential Auto-Detection

The Setup stage uses a single code path:

```bash
# The pipeline does this automatically:
if file_is_json_with_type_service_account:
    # GCP path
    export GOOGLE_APPLICATION_CREDENTIALS=.gcp-key.json
    export GCP_PROJECT=$(json .project_id)
else:
    # Everything else — AWS, Snowflake, Azure, Databricks...
    source the key=value pairs as env vars
```

This means **adding a new provider** requires zero Jenkinsfile changes:

1. Implement the provider in the CLI (`fluid_build/providers/`)
2. Set `binding.platform` in the contract
3. Create a credentials file with the env vars your provider needs
4. Push — the same pipeline runs

## Stages Reference

| # | Stage | Command | Purpose |
|---|-------|---------|---------|
| 1 | Setup | — | Load credentials, detect format, print summary |
| 2 | Validate | `fluid validate` | Check the contract against the schema for its `fluidVersion` |
| 3 | Export | `fluid odps export` / `fluid odcs export` | Generate interop standards |
| 4 | Compile IAM | `fluid policy-compile` | Convert `accessPolicy` → provider-native IAM |
| 5 | Plan | `fluid plan` | Generate execution plan |
| 6 | Tests | `fluid contract-tests` | Compare the schema with a committed baseline |
| 7 | Apply Infra | `fluid apply` | Deploy cloud resources |
| 8 | Apply IAM | `fluid policy-apply` | Hand the compiled bindings to the provider; changes no permissions in 0.18.1 |
| 9 | Execute | `fluid apply --mode amend-and-build` | Run build scripts (ingest, transform) |
| 10 | Airflow DAG | `fluid generate schedule` | Generate the Airflow DAG for the environment |
| 11 | Summary | — | Print artifacts and results |

### The contract-test baseline

`fluid contract-tests` compares the contract's schema with a baseline you commit. Without `--baseline` it prints that it skipped and exits 0, so the stage tests nothing until the baseline exists. Write it once, from a contract you have reviewed:

```bash
mkdir -p contract-baseline
fluid contract-tests contract.fluid.yaml --write-baseline contract-baseline/baseline.schema.json
```

```text
✅ Baseline written to contract-baseline/baseline.schema.json
```

Create the directory first: as of 0.18.1, `--write-baseline` does not create it, and fails with `contract_tests_failed` and `No such file or directory`. Commit the file. The pipeline then compares every build with it:

```bash
fluid contract-tests contract.fluid.yaml --baseline contract-baseline/baseline.schema.json
```

```text
✅ Contract tests passed
```

The comparison is exact equality of each expose's column names, types, nullability and order. Adding a column fails it, as does removing, retyping, reordering or changing the nullability of one:

```text
❌ Contract tests failed — 1 incompatibility(ies) found
   • genre_preferences.favourite: column added
```

The command exits 2 on an incompatibility and 1 for a missing or unreadable baseline. It is a schema-change gate, not a consumer-impact check: a deliberate schema change means writing a new baseline in the same commit.

## Jenkins Setup

### Prerequisites

- Jenkins with Docker Pipeline plugin
- A Docker image with the `fluid` CLI installed (`pip install data-product-forge`, with the extra for your provider), in a registry the agents can pull from
- One Secret File credential per provider environment

### Creating a Pipeline Job

1. **New Item** → **Multibranch Pipeline** (or **Pipeline**)
2. **Source**: Point to your git repo containing the contract + `Jenkinsfile`
3. **Parameters**: Jenkins learns a Pipeline's parameters from a run, so `buildWithParameters` is refused for a job that has never run (observed on a Jenkins controller on 4 to 5 October 2026). The Jenkinsfile that `fluid generate ci` writes gives every parameter a fallback for that first build. This hand-written one reads `params.FLUID_IMAGE` and the others without one, so put the defaults you need in the file. After the first build, set:
   - `CREDENTIALS_ID` → your Jenkins Secret File credential ID
   - `CONTRACT_FILE` → `contract.fluid.yaml` (default)
   - `FLUID_IMAGE` → your CLI Docker image
4. **Build** → Every stage runs in order. A stage that fails stops the build

### Credential Convention

| Provider | Jenkins Credential Type | File Contents |
|----------|----------------------|---------------|
| GCP | Secret File | Raw service account JSON key |
| AWS | Secret File | `AWS_ACCESS_KEY_ID=...` + `AWS_SECRET_ACCESS_KEY=...` + `AWS_REGION=...` + `S3_BUCKET=...` |
| Snowflake | Secret File | `SNOWFLAKE_ACCOUNT=...` + `SNOWFLAKE_USER=...` + `SNOWFLAKE_PASSWORD=...` + ... |

All use the same Jenkins Secret File credential type. The pipeline auto-detects the format.

## See Also

- [AWS Provider](/forge_docs/providers/aws) — S3, Glue, Athena deployment
- [Snowflake Provider](/forge_docs/providers/snowflake) — Snowflake Data Cloud deployment
- [GCP Provider](/forge_docs/providers/gcp) — BigQuery, GCS deployment
- [CLI Reference](/forge_docs/cli/) — Full command docs
