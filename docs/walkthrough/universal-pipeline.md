# Universal Pipeline

One Jenkinsfile. Every provider. Zero if/then logic.

**Status:** ✅ Production (GCP, AWS, Snowflake tested)  
**Lines of code:** 228  
**Provider-specific logic:** None

::: warning Compatibility note
This walkthrough includes some older `0.7.1` contract-era examples. The primary docs baseline now tracks CLI `0.8.0`, current scaffolded contracts use `fluidVersion: 0.7.2`, and orchestration docs prefer `fluid generate schedule --scheduler airflow`.
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

The FLUID Universal Pipeline eliminates all provider logic from CI/CD. The **contract is the single source of truth** — it declares `binding.platform`, and the CLI reads it automatically.

### How It Works

```
┌────────────────────────────────────────────────────────────┐
│                    Jenkinsfile (228 lines)                  │
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
| **Project detection** | CLI reads from bindings.json or `FLUID_PROVIDER` env var — no `--project` flag |
| **Dependencies** | Single `requirements.txt` per example (not `requirements-aws.txt`) |
| **Env loading** | `set -a; . .fluid-env; set +a` in every stage — works for any provider |

## The Jenkinsfile

This is the complete, production-tested Jenkinsfile used by all three provider examples:

```groovy
#!/usr/bin/env groovy
/**
 * FLUID Pipeline v0.7.1 — Provider-Agnostic
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
        string(name: 'FLUID_IMAGE',    defaultValue: 'localhost:5000/fluid-forge-cli:beta-latest',
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
                      --out standards/product.odps.json || true
                    fluid odcs export ${CONTRACT_FILE} \
                      --out standards/product.odcs.yaml || true
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
                        --out runtime/policy/bindings.json || {
                        echo '{"bindings":[],"warnings":["policy-compile unavailable"]}' \
                          > runtime/policy/bindings.json
                    }
                '''
            }
        }

        stage('Generate Plan') {
            steps {
                sh '''
                    set -a; . .fluid-env; set +a
                    mkdir -p plans
                    fluid plan ${CONTRACT_FILE} \
                      --env ${ENV} --out plans/plan-${ENV}.json || true
                '''
            }
        }

        stage('Run Tests') {
            steps {
                sh '''
                    set -a; . .fluid-env; set +a
                    fluid contract-tests ${CONTRACT_FILE} || true
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
                                --mode ${params.ENFORCE_IAM ? 'enforce' : 'check'} \
                              || true
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
                    fluid execute ${CONTRACT_FILE}
                '''
            }
        }

        stage('Generate Airflow DAG') {
            steps {
                sh '''
                    mkdir -p airflow-dags
                    CONTRACT_ID=$(grep -m1 "^id:" ${CONTRACT_FILE} \
                      | cut -d" " -f2 | tr -d "\"" | tr "." "_")
                    fluid generate-airflow ${CONTRACT_FILE} \
                        --out airflow-dags/data_product_${ENV}.py \
                        --dag-id "${CONTRACT_ID}_${ENV}" || true
                    [ -f airflow-dags/data_product_${ENV}.py ] \
                      && python3 -m py_compile airflow-dags/data_product_${ENV}.py \
                      && echo "DAG valid"
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
            cleanWs()
        }
    }
}
```

## Side-by-Side: Same Pipeline, Different Clouds

The Jenkinsfile **never changes**. Only the contract and credentials differ.

### What Differs Per Provider

| | GCP | AWS | Snowflake |
|---|-----|-----|-----------|
| **Contract** | `binding.platform: gcp` | `binding.platform: aws` | `binding.platform: snowflake` |
| **Format** | `bigquery_table` | `parquet` | `snowflake_table` |
| **Location** | `project`, `dataset`, `table` | `bucket`, `path`, `region`, `database`, `table` | `account`, `database`, `schema`, `table` |
| **Credential file** | GCP SA JSON key | `AWS_ACCESS_KEY_ID=...` | `SNOWFLAKE_ACCOUNT=...` |
| **IAM output** | BigQuery `dataViewer`/`dataOwner` | S3/Glue/Athena actions | Snowflake `GRANT SELECT/INSERT` |
| **Jenkinsfile** | **Identical** | **Identical** | **Identical** |
| **CLI commands** | **Identical** | **Identical** | **Identical** |

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
| 2 | Validate | `fluid validate` | Check contract against 0.7.1 JSON schema |
| 3 | Export | `fluid odps export` / `fluid odcs export` | Generate interop standards |
| 4 | Compile IAM | `fluid policy-compile` | Convert `accessPolicy` → provider-native IAM |
| 5 | Plan | `fluid plan` | Generate execution plan |
| 6 | Tests | `fluid contract-tests` | Run contract validation tests |
| 7 | Apply Infra | `fluid apply` | Deploy cloud resources |
| 8 | Apply IAM | `fluid policy-apply` | Enforce IAM/RBAC bindings |
| 9 | Execute | `fluid execute` | Run build scripts (ingest, transform) |
| 10 | Airflow DAG | `fluid generate-airflow` | Generate production orchestration |
| 11 | Summary | — | Print artifacts and results |

## Jenkins Setup

### Prerequisites

- Jenkins with Docker Pipeline plugin
- FLUID CLI Docker image in a registry (e.g., `localhost:5000/fluid-forge-cli:beta-latest`)
- One Secret File credential per provider environment

### Creating a Pipeline Job

1. **New Item** → **Multibranch Pipeline** (or **Pipeline**)
2. **Source**: Point to your git repo containing the contract + `Jenkinsfile`
3. **Parameters**: Configure via the first build or pre-set:
   - `CREDENTIALS_ID` → your Jenkins Secret File credential ID
   - `CONTRACT_FILE` → `contract.fluid.yaml` (default)
   - `FLUID_IMAGE` → your CLI Docker image
4. **Build** → All 11 stages run automatically

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
