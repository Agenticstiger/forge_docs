# Environment Variables

The environment variables the CLI reads, grouped by what they configure. This page was rebuilt from the `data-product-forge` 0.18.1 source. A variable is listed with the behaviour its read site implements; where a variable that earlier versions of this page listed does nothing in 0.18.1, [it is named below](#variables-with-no-effect-in-0-18-1).

```bash
fluid doctor --env          # runtime kill switches: current value, source, default
```

`fluid doctor --env` prints only the switches `doctor` knows about (forge copilot stages, cost ceilings, run id, the OpenTofu and federation timeouts, `DBT_EXECUTABLE`, telemetry). The rest are read where they are used.

::: tip How values are parsed
There is no single rule. Some variables accept only `1`, some accept `1`/`true`/`yes`/`on`, and a few treat any non-empty value as set, including `0`. The tables say which where it matters. When in doubt, use `1` to turn something on and unset the variable to turn it off.
:::

## CLI behaviour

| Variable | Effect |
|---|---|
| `FLUID_LOG_LEVEL` | Default of `--log-level`: `DEBUG`, `INFO`, `WARNING` or `ERROR`. Default `INFO`. |
| `FLUID_LOG_FILE` | Default of `--log-file`: also write logs to this file. |
| `FLUID_QUIET` | `1` suppresses banners, the agent progress panel and the capability-warning print. Only the value `1` counts. |
| `FLUID_NONINTERACTIVE` | `1` suppresses the same chrome and skips the interactive `fluid forge` surfaces. Only the value `1` counts. It does not change whether `fluid apply` prompts; see [Operating in CI](./operating-in-ci.md#non-interactive-operation). |
| `FLUID_NO_TUI` | `1` silences the agent progress panel. |
| `FLUID_BANNER` | `1`, `true`, `yes` or `on` opts in to the roadmap teaser banner. As of 0.18.1 it prints nothing: the teaser's last milestone has passed and the banner expired on 2026-05-07. |
| `FLUID_BANNER_TODAY` | Overrides "today" in the banner's date arithmetic. Test use only. |
| `FLUID_BUILD_PROFILE` | `experimental` (default) or `stable`; `stable` curates the registered command set. |
| `FLUID_RUN_ID` | Pre-seeds the cross-stage run id instead of generating one. Set it in CI to correlate the stages of one pipeline run. |
| `FLUID_TELEMETRY` | `1` enables anonymous usage telemetry, `0` forces it off and overrides the config file. Off by default. |
| `DO_NOT_TRACK` | When set, all telemetry is off, whatever else is configured. |
| `FLUID_SHOW_REGISTRATION` | `1`, `true` or `yes` prints the provider and extension registration lines that `--log-level DEBUG` also prints. |

## Project, region and paths

| Variable | Effect |
|---|---|
| `FLUID_PROVIDER` | Default of the global `--provider`. A binding's `platform` wins over it when a plan resolves the provider. |
| `FLUID_PROJECT` | Default of the global `--project`; the GCP provider also reads it as a project fallback. |
| `FLUID_REGION` | Default of the global `--region`. The flag's own default is `europe-west3`. |
| `FLUID_DEFAULT_REGION` | A project-wide region for the class-based provider plan path. The order is `--region`, the contract's `region`, a binding's `location.region`, then `FLUID_DEFAULT_REGION`, then `AWS_REGION` and `AWS_DEFAULT_REGION`, then `eu-west-1`. |
| `FLUID_ENV` | **Not** a default for `--env`: `validate`, `bundle`, `plan` and `apply` ignore it, so pass `--env`. It is read by `fluid generate artifacts` (the env baked into scheduled DAGs), by `fluid schedule-sync --env`, and by the dotenv credential store, which loads `.env.<env>`. Generated pipelines set it as a build parameter and pass `--env "${FLUID_ENV:-dev}"` to each stage. |
| `FLUID_HOME` | Base directory for the copilot `config.yaml` and `prices.json`, and for artifact paths. Default `~/.fluid`. |
| `FLUID_CONFIG` | Path of the copilot `config.yaml`; wins over `FLUID_HOME`. |
| `FLUID_USER_HOME` | Overrides the user-global FLUID directory (`~/.fluid`). |
| `FLUID_WORKSPACE_ROOT` | Overrides the directory that holds the workspace-local `.fluid/` state. Default: the working directory. |
| `FLUID_SECRETS_FILE` | Path of a dotenv-style file that is loaded last, over the process environment, when a command hydrates the project's `.env` files (`.env`, `.env.<env>`, `.env.local`, then this file). Best effort, and it needs `python-dotenv`. It is not an encrypted file. |
| `FLUID_UPSTREAM_CONTRACTS` | Colon-separated extra directories searched for upstream contracts, next to the contract's own workspace. Used when `fluid forge` and the dbt source generator look up an upstream's schema, and when an embedded-SQL build binds a `consumes[]` entry to its upstream's binding. Each root is searched down to four directory levels for `contract.fluid.yaml` or `contract.fluid.json`; build output and VCS directories such as `.git` and `node_modules` are skipped. |

## Contract loading and the DuckDB sandbox

| Variable | Effect |
|---|---|
| `FLUID_REF_ROOT` | Widens the directory tree a `$ref` may resolve under (CLI 0.18.0). Ignored, with a `ref_root_env_ignored` warning, for a contract that lies outside it. See [Composing a contract with `$ref`](../concepts/contract-refs.md). |
| `FLUID_DUCKDB_ALLOWED_DIRS` | Directories, separated by `os.pathsep`, where a contract may also declare inputs and outputs for the local DuckDB engine (CLI 0.18.0). Set by the operator, never by the contract. See the [DuckDB sandbox](./duckdb-sandbox.md). |
| `FLUID_LOCAL_DUCKDB_PATH` | Database file for the legacy `fluid_build.contract_tests` module. Default `:memory:`. |

## Apply, state and OpenTofu

| Variable | Effect |
|---|---|
| `FLUID_STATE_BACKEND` | Default of `--state-backend` for `fluid apply`, `fluid diff` and `fluid verify --state-drift`: `s3://<bucket>[/<key>]` or `gcs://<bucket>[/<prefix>]` (see [Remote state](../cli/apply.md#remote-state)). A spec that names only a bucket gives every contract its own key (see below); the flag does not. An empty `--state-backend ""` forces local state for one run. |
| `FLUID_TOFU_TIMEOUT_SECONDS` | Wall-clock cap per `tofu` invocation. Default `1800`. A timed-out call reports exit code 124. |
| `FLUID_OPENTOFU_VERSION` | Pins the OpenTofu version that [`fluid apply --ensure-opentofu`](../cli/apply.md) installs when `tofu` is missing. |
| `FLUID_REDSHIFT_WORKGROUP`, `FLUID_REDSHIFT_DATABASE`, `FLUID_REDSHIFT_SQL` | Set by the generated AWS module for its Redshift Serverless statements. They are outputs of the generator, not settings. |
| `SNOWFLAKE_ORGANIZATION_NAME`, `SNOWFLAKE_ACCOUNT_NAME` | The account identity that the generated module's Snowflake provider 2.x expects. fluid derives them from a `SNOWFLAKE_ACCOUNT` in `<org>-<account>` form when they are not set. |
| `SNOWFLAKE_ACCOUNT` | Blanked in the environment handed to `tofu` once a complete v2 identity resolves, because provider 2.x errors on seeing it. Unchanged as a source credential; see [Credential resolver](./credential-resolver.md). |

With a bucket-only `FLUID_STATE_BACKEND`, the remote state key is `fluid/<id>/<provider>/terraform.tfstate` (GCS prefix `fluid/<id>/<provider>`), so one contract applied to two clouds through overlays keeps two states. A spec that names a key is used as written. The first apply after upgrading to 0.17.0 moves state from the old key `fluid/<id>/terraform.tfstate` when it holds this provider's resources; the errors that can follow are in [Production troubleshooting](./production-troubleshooting.md#state-and-region-errors).

```bash
export FLUID_STATE_BACKEND=s3://acme-fluid-state     # bucket only: per-contract, per-provider keys
fluid apply runtime/plan.json --bundle runtime/bundle.tgz --env aws --yes
```

## Command Center

`fluid publish` and `fluid apply` read different variables. Publishing to the Command Center uses the catalog configuration; `fluid apply` reuses that configuration to report each run, and falls back to the reporter's own variables.

| Variable | Read by | Effect |
|---|---|---|
| `FLUID_CC_ENDPOINT` (or `FLUID_CATALOG_FLUID_CC_URL`) | `fluid publish`, and `fluid apply` run reports | Command Center base URL for the `fluid-command-center` catalog target. |
| `FLUID_API_KEY` (or `FLUID_CATALOG_FLUID_CC_TOKEN`) | same | API key sent as `X-API-Key`. |
| `FLUID_BEARER_TOKEN` | same | Bearer token, when the catalog's auth type is `bearer`. |
| `FLUID_CC_ORG_ID` | same | Organization id sent as `X-Organization-Id`. A set but blank value is an error (`cc_organization_id_blank`). Without it, the organization comes from `organization_id` or an `organization` slug in the FLUID config, else from the credential's only organization. |
| `FLUID_COMMAND_CENTER_URL`, `FLUID_COMMAND_CENTER_API_KEY` | `fluid market` and `fluid marketplace` detection, the observability reporter, and as the fallback for `fluid apply` run reports | They do not change where `fluid publish` sends a contract. |
| `FLUID_COMMAND_CENTER_ENABLED` | the reporter and `fluid apply` run reports | `0`, `false`, `no` or `off` turns off apply run reports. |
| `FLUID_COMMAND_CENTER_TIMEOUT` | the reporter | Request timeout in seconds. Default `5`. |
| `FLUID_COMMAND_CENTER_HOST_ALLOWLIST` | detection, the reporter, apply run reports | Comma-separated host suffixes allowed even when they resolve to a private address. Loopback is always allowed. |
| `FLUID_DISABLE_CC_DETECTION` | `fluid market`, `fluid marketplace` | `true`, `1` or `yes` skips the Command Center auto-detection. |
| `FLUID_API_URL` | `fluid marketplace` | Explicit marketplace API URL; wins over detection. |

`fluid apply` registers each run at `POST /api/v1/executions` and closes it with a `PATCH`, best effort: an unreachable Command Center costs a warning line and at most the timeout, never the exit code. With no organization, nothing is sent. It reports the product id, contract version, hash, env, provider, mode, state location, resource addresses, change counts, timings and the builds it ran. It does not send secrets, headers or `tofu` output. Under Jenkins (`JENKINS_URL` set) the runner is tagged `jenkins`.

## Generated pipelines and Airflow workers

The CLI itself does not read these; the generated pipeline and the generated DAG do.

| Variable | Read by | Effect |
|---|---|---|
| `FLUID_PACKAGE_SPEC` | the generated Jenkins stage 0 | Package spec installed into the workspace venv. Defaults to the generating CLI version with the extras the contract needs, for example `data-product-forge[local]==0.18.1`. |
| `FLUID_PIP_INDEX_URL`, `FLUID_PIP_EXTRA_INDEX_URL` | the generated install step | Primary and extra pip index. Blank means PyPI. pip takes the highest version across both, so for private packages use one mirror that proxies PyPI in `FLUID_PIP_INDEX_URL` and leave the extra index empty; see [Operating in CI](./operating-in-ci.md#install). |
| `FLUID_ALLOW_PRERELEASE` | the generated install step | `true` adds `pip --pre`. |
| `FLUID_CONFIG_PATH` | set by generated pipelines | `./fluid_config`. Nothing in the CLI reads it. |
| `FLUID_PROJECT_DIR` | the generated Airflow DAG, on the worker | Directory that holds the product checkout. Required. |
| `FLUID_BIN` | the generated Airflow DAG | The `fluid` executable on the worker. Default `fluid`. |
| `FLUID_DAG_ENV_PASSTHROUGH` | the generated Airflow DAG | Space-separated extra variable names handed to the `fluid apply` process. A name that starts with `AIRFLOW` never passes, so the worker's Airflow configuration and connection variables stay out of `fluid`. |
| `FLUID_DAG_CONTRACT`, `FLUID_DAG_ENV`, `FLUID_DAG_BUILD_ID`, `FLUID_DAG_CONTRACT_ENV` | the generated Airflow DAG | Set by the DAG's task from constants in the file; do not set them on the worker. |

See [Airflow](./airflow.md) for which variables reach `fluid apply` on the worker and [Operating in CI](./operating-in-ci.md) for the pipeline parameters.

## Build runners, masking and lineage

| Variable | Effect |
|---|---|
| `FLUID_PII_HASH_SECRET` | Salt for `strategy: hash` in `policy.privacy.masking`. At least 16 bytes. An unset salt refuses the build rather than hashing without one. |
| `FLUID_PII_TOKENIZATION_KEY` | HMAC key for `strategy: tokenize` and the `tokenize_pii` hook. At least 32 bytes for masking. Unset, the masking build is refused. |
| `FLUID_PII_ENCRYPTION_SECRET_KEY` | Base64 of a 16, 24 or 32 byte AES key for `strategy: encrypt`. |
| `FLUID_RUNNER_HOST_OVERRIDE` | Host the runners use to reach containers they start. Wins over `TESTCONTAINERS_HOST_OVERRIDE`. |
| `FLUID_DBT_FORWARD_ENV` | Extra environment variable names or prefixes the dbt runner forwards. |
| `DBT_EXECUTABLE` | The dbt command the runner and the `--dbt-validate` and `--dbt-tests-key auto` probes resolve first: an absolute path, a bare name on `PATH`, or a multi-token wrapper. Falls back to `dbt` on `PATH`, then the active venv. |
| `FLUID_DBT_TESTS_KEY` | `auto` (default), `tests` or `data_tests`: which YAML key generated dbt tests attach under. The `--dbt-tests-key` flag wins. |
| `DBT_DOCKER_IMAGE` | A prebuilt image for the dbt container fallback. |
| `DBT_BOOTSTRAP_IMAGE` | Base image the dbt container fallback installs dbt into. Default `python:3.12-slim`. |
| `DBT_ADAPTER_PACKAGE` | Overrides the pip package that fallback installs. Without it the install is `dbt-<adapter><2` plus `dbt-core<2`; setting it is how you opt in to dbt 2. |
| `FLUID_SOURCE_DATABASE`, `FLUID_SOURCE_SCHEMA` | Read through dbt's `env_var()` in generated `sources.yml`: when set, they supply a source's database and schema before the dbt target's own. |
| `FLUID_ROLLBACK_KEEP_LAST_N` | Per-product retention of `.fluid/rollback-state.json`. Default `20`. |
| `FLUID_OPENLINEAGE_URL` (or the standard `OPENLINEAGE_URL`) | Base URL of an OpenLineage receiver. Without one, no lineage is emitted. |
| `FLUID_OPENLINEAGE_ENDPOINT` | Path appended to the URL. |
| `FLUID_OPENLINEAGE_API_KEY` (or `OPENLINEAGE_API_KEY`) | Bearer key for the receiver. |
| `FLUID_OPENLINEAGE_TIMEOUT_SECONDS` | Request timeout. Default `5`. |
| `FLUID_OPENLINEAGE_ALLOW_PRIVATE` | Defaults to allowing private receiver addresses; `false` restores the public-only gate. Link-local and metadata addresses stay blocked. |
| `FLUID_WEBHOOK_HOST_ALLOWLIST` | Comma-separated host suffixes the build webhook alerter may call; see [Network safety](./network-safety.md). |

Masking is applied only on the DuckDB acquisition landing path. See [Production troubleshooting](./production-troubleshooting.md#builds-and-masking) for the errors.

## Verify, import and cloud APIs

| Variable | Effect |
|---|---|
| `FLUID_ATHENA_OUTPUT_LOCATION` | Default of `fluid verify --athena-output-location`: where Athena writes the row-count result. A workgroup that enforces its own location wins. |
| `FLUID_ATHENA_WORKGROUP` | Default of the Athena workgroup for the row-count query. Default `primary`. |
| `FLUID_ATHENA_TIMEOUT_SECONDS` | Query timeout. Default `300`. |
| `FLUID_IMPORT_AIRBYTE_URL` | Airbyte API base URL for `fluid import airbyte`. The importer has no default endpoint: without `--server-url` or this variable it refuses before building a client. |
| `GOOGLE_PROJECT`, `GOOGLE_CLOUD_PROJECT`, `GCLOUD_PROJECT`, `CLOUDSDK_CORE_PROJECT` | Read in this order for the BigQuery load project when the binding names none. |
| `BIGQUERY_EMULATOR_HOST` | Points the BigQuery client at an emulator. fluid then uses anonymous credentials, so no token reaches the emulator. |
| `AWS_ENDPOINT_URL_S3`, `AWS_ENDPOINT_URL` | Point DuckDB's S3 access at a non-AWS endpoint, such as a local object-store emulator; `AWS_ENDPOINT_URL_S3` wins when both are set, and `AWS_IGNORE_CONFIGURED_ENDPOINT_URLS=true` turns the override off. A value that is not an `http(s)` URL naming a host, or that carries a user and password, is ignored with a warning. When DuckDB cannot be pointed at a valid override the build fails with `ObjectStoreEndpointError` rather than write to AWS. |
| `FLUID_GCP_PROJECT` | Counted by the `fluid forge` welcome scan as a sign that GCP is configured. |

A BigQuery binding that declares no `location.region` gets a load job with no location, so the job runs where the table is. Pin `location.region` in the binding when the data's location matters.

## Federation and network safety

| Variable | Effect |
|---|---|
| `FLUID_FEDERATION_TIMEOUT_SECONDS` | Per-git-operation cap when `fluid apply` fetches a federated upstream digest. Default `30`. A non-numeric, zero, negative or non-finite value is ignored with a `federation_timeout_invalid` warning. |
| `FLUID_FEDERATION_HOST_ALLOWLIST` | Comma-separated host suffixes a federation endpoint may use even when they resolve to a private address. |
| `FLUID_ALLOW_METADATA_SERVICE` | `1` lets the metadata-source credential resolver fall back to the cloud metadata service. Same as `--allow-metadata-service`. See [Credential resolver](./credential-resolver.md). |
| `FLUID_AUDIT_ROOT` | Redirects where `fluid mcp output-port` writes audit events (default `~/.fluid/store/audit/`), for example to a path a SIEM forwards. When the contract's `agentPolicy.auditRequired` is true and this is unset, the gateway prints a notice that names the default. |

## Catalog publish-side registrars

See the [catalog overview](../cli/catalogs/overview.md).

| Variable | Effect |
|---|---|
| `FLUID_CATALOG_DATAHUB_URL`, `FLUID_CATALOG_DATAHUB_TOKEN` | DataHub endpoint and token. |
| `FLUID_CATALOG_DATAHUB_SPEC_BASE_URL` | Base URL for spec source documents. |
| `FLUID_CATALOG_DATAHUB_MAX_RETRIES` | Retry count for DataHub calls. |
| `FLUID_CATALOG_DMM_URL`, `FLUID_CATALOG_DMM_TOKEN` | Data Mesh Manager endpoint and API key. |
| `FLUID_CATALOG_OPENMETADATA_URL`, `FLUID_CATALOG_OPENMETADATA_TOKEN` | OpenMetadata endpoint and bearer token. |

## Cost and budget gates

See [cost tracking](./cost-tracking.md).

| Variable | Effect |
|---|---|
| `FLUID_COST_LIMIT_USD` | Per-run LLM cost ceiling in USD. |
| `FLUID_COST_LIMIT_USD_PER_RUN` | Per-run ceiling shown in the progress prefix. |
| `FLUID_COST_LIMIT_USD_PER_PRODUCT` | Per-product LLM cost ceiling, enforced in the agent coordinator. |
| `FLUID_STAGE_BUDGET_<STAGE>_S` | Wall-clock budget in seconds for one forge pipeline stage, for example `FLUID_STAGE_BUDGET_LOGICAL_S`. Stage names are lowercase in the code (`logical`, `builder`, `readme`, `transformation`, `validator`). |
| `FLUID_MISSION_TIMEOUT_SECONDS` | Overrides a mission's wall-clock budget. |
| `FLUID_PRICES_JSON` | Path of a price override file. Without it: `$FLUID_HOME/prices.json`, then `~/.fluid/prices.json`. |
| `FLUID_TOKEN_COUNTER` | `chars` switches token counting to a character estimate. Any other value keeps the default counter. |

## LLM provider and routing

See [LLM providers](./llm-providers.md) and the [LiteLLM backend](./litellm-backend.md).

| Variable | Effect |
|---|---|
| `FLUID_LLM_PROVIDER` | Default provider. |
| `FLUID_LLM_MODEL` | Default model. |
| `FLUID_LLM_API_KEY` | API key used when no provider-specific key is set. |
| `FLUID_LLM_ENDPOINT` | Overrides the model endpoint. |
| `FLUID_LLM_TIMEOUT_SECONDS` | Per-call timeout. Default `120`. |
| `FLUID_LLM_STREAMING` | Default on; `0`, `false`, `no` or `off` disables streaming. |
| `FLUID_LLM_ROUTING_ENDPOINT`, `FLUID_LLM_ROUTING_MODEL` | Optional routing endpoint and model. |
| `FLUID_LLM_MODEL_PREFLIGHT` | Runs a model-availability check before the first call. |
| `FLUID_LLM_BACKEND` | `litellm` routes every LLM call through the unified backend. |
| `FLUID_LLM_FALLBACK_CHAIN` | Fallback model chain for the router. |
| `FLUID_LITELLM_MODEL_PREFIX` | Prefix prepended to the model name for providers LiteLLM names differently. |
| `FLUID_TIERED` | Uses per-stage model tiers when an LLM is configured. |
| `FLUID_OPENAI_STRICT_SCHEMA` | `1`, `true`, `yes` or `on` hardens the response schema for OpenAI strict mode. |
| `FLUID_GEMINI_RESPONSE_SCHEMA` | `1` sends the response schema to Gemini. Off by default. |
| `FLUID_FORGE_AGENT` | Selects a keyless coding-agent provider (`claude-code`, `codex`, `cursor`, `kiro`). |
| `FLUID_FORGE_AGENT_MODE`, `FLUID_FORGE_AGENT_TIMEOUT_SECONDS`, `FLUID_FORGE_AGENT_CWD` | Drive mode (`envelope` or `agentic`), per-invocation wall-clock cap, and working directory for the agent CLI. |
| `FLUID_AGENT_WEB_TOOLS` | `1` exposes the `web_search` and `web_fetch` agent tools. |
| `FLUID_WEB_SEARCH_PROVIDER` | Forces the web-search backend. |

Provider-specific keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `AWS_*` for Bedrock, the Vertex settings) follow the underlying SDKs and are read by LiteLLM.

## Forge copilot

| Variable | Effect |
|---|---|
| `FLUID_FORGE_NO_PICKER` | Skips the mode menu on bare `fluid forge`. Any non-empty value counts. |
| `FLUID_FORGE_NO_PREVIEW` | Skips the pre-write preview panel. Any non-empty value counts. |
| `FLUID_FORGE_NO_STREAMING_PREVIEW` | Disables the live contract-growth panel. Any non-empty value counts. |
| `FLUID_FORGE_NO_WELCOME` | Suppresses the welcome scan. Any non-empty value counts. |
| `FLUID_FORGE_PICKER_ALWAYS` | Shows the picker even for return users. |
| `FLUID_FORGE_AUTO_CI` | `0`, `false`, `no` or `off` disables the CI scaffold that a forge run otherwise emits. |
| `FLUID_FORGE_OFFLINE` | `1` forces the local, no-network guided interview. Same as `--offline`. |
| `FLUID_FORGE_AUTO_RESUME`, `FLUID_FORGE_NO_PRUNE_HINT` | `1` resumes an interrupted run without asking, and hides the prune hint. |
| `FLUID_FORGE_LEGACY_COPILOT` | Uses the linear runtime instead of the staged copilot. Any non-empty value counts. |
| `FLUID_FORGE_STAGED_COPILOT`, `FLUID_FORGE_STAGED_TOOL_LOOP` | `1` selects the experimental staged copilot and tool loop. |
| `FLUID_FORGE_DRIFT_GUARD` | Enables the semantic-drift guard. Opt-in. |
| `FLUID_FORGE_DB_TOOLS`, `FLUID_FORGE_DB_URI` | Enable the row-capped `fetch_sample_rows` agent tool, and the connection URI it uses. |
| `FLUID_FORGE_TOOL_SEARCH` | Enables lazy tool-search deferral in the agent loop. |
| `FLUID_GITHUB_MCP`, `FLUID_SNOWFLAKE_MCP`, `FLUID_DBT_MCP` | Enable delegation to the hosted GitHub, Snowflake and dbt MCP servers. |
| `FLUID_HOSTED_MCP_TIMEOUT_SECONDS` | Per-operation timeout for hosted MCP calls. |
| `FLUID_COPILOT_AGENT_LOOP` | `1`, `true`, `yes` or `on` selects the multi-turn agent loop. Same as `--agent-loop`. |
| `FLUID_COPILOT_JUDGE`, `FLUID_COPILOT_ENRICHMENT`, `FLUID_JUDGE_SELF_CRITIQUE`, `FLUID_COPILOT_SELF_EVAL`, `FLUID_COPILOT_CHECKPOINT`, `FLUID_COPILOT_PII_CLASSIFIER` | On by default; `0`, `false`, `no` or `off` skips that stage. |
| `FLUID_COPILOT_POST_SYNTHESIS`, `FLUID_COPILOT_EPISODIC_MEMORY` | On by default; only the value `0` turns them off. |
| `FLUID_COPILOT_SEMANTIC_MEMORY` | Opts in to semantic-memory writes and lookups. |
| `FLUID_COPILOT_FORCE_INTERVIEW` | Forces the interview even when it would otherwise be skipped. Any non-empty value counts. |
| `FLUID_COPILOT_PARALLEL_PHYSICAL` | On by default; `0`, `false`, `no` or `off` runs the physical-modeling stages one at a time. |
| `FLUID_INTERVIEW_LEGACY` | `1` reverts to the legacy bootstrap interview. |
| `FLUID_AGENT_COMPACT_AFTER` | Compact the agent context after this many turns. Default `6`. |
| `FLUID_COMPACTION_STRATEGY` | `truncate`, `summarize` or `hybrid`. |
| `FLUID_PROMPT_OVERLAYS`, `FLUID_PROMPT_PROFILE`, `FLUID_OVERLAY_STRICT`, `FLUID_OVERLAY_PUBLIC_KEYS` | Prompt overlays and profile for `fluid forge`; strict mode and the keys that verify signed overlays. |
| `FLUID_FORGE_WATCH_INTERVAL`, `FLUID_FORGE_WATCH_DEBOUNCE` | Poll interval and debounce, in seconds, for `fluid forge` watch mode. |

## MCP output port

Read by `fluid mcp output-port`; see [MCP](./mcp.md).

| Variable | Effect |
|---|---|
| `FLUID_MCP_AUTH_MODE` | `shared-token` (default), `jwt` or `none`. |
| `FLUID_MCP_AUTH_TOKEN` | The shared token. |
| `FLUID_MCP_JWT_ISSUER`, `FLUID_MCP_JWT_AUDIENCE`, `FLUID_MCP_JWT_JWKS_URL` | Required for `jwt` mode. |
| `FLUID_MCP_JWT_ALGORITHMS`, `FLUID_MCP_JWT_CLAIM_MAPPING` | Accepted algorithms, and extra claim mappings merged over the defaults. |
| `FLUID_MCP_RATE_LIMIT`, `FLUID_MCP_RATE_WINDOW_SECONDS` | Sliding-window rate limit. Default `60` calls per `60` seconds; `0` disables it. |
| `FLUID_MCP_MAX_CONCURRENCY` | In-flight tool calls per gateway process. Default `8`; `0` disables. |
| `FLUID_MCP_CIRCUIT_THRESHOLD`, `FLUID_MCP_CIRCUIT_WINDOW_SECONDS`, `FLUID_MCP_CIRCUIT_COOLDOWN_SECONDS` | Circuit breaker. Defaults `5` failures, `60` s window, `30` s cooldown. |
| `FLUID_MCP_AUDIT_WEBHOOK_URL`, `FLUID_MCP_AUDIT_WEBHOOK_HEADER_AUTH`, `FLUID_MCP_AUDIT_WEBHOOK_TIMEOUT_SECONDS` | Forward audit events to a webhook. |
| `FLUID_AUDIT_MAX_AGE_DAYS`, `FLUID_AUDIT_MAX_TOTAL_MB` | Audit rotation. Defaults `30` days and `256` MB. |

## Store, secrets and encryption

| Variable | Effect |
|---|---|
| `FLUID_STORE_BACKEND` | Memory store for the forge copilot: `file` (default), `sqlite`, `postgres` or `vector`; `0`, `none`, `null` or `disabled` turns persistence off. |
| `FLUID_STORE_ROOT` | Root of the `file` backend. Default `~/.fluid/store`. |
| `FLUID_STORE_PATH` | Database file of the `sqlite` backend. |
| `FLUID_STORE_DSN` | Connection string of the `postgres` backend. Required for it. |
| `FLUID_STORE_VECTOR_BACKING` | Backing store of the `vector` backend: `file` (default), `sqlite` or `postgres`. |
| `FLUID_SECRETS_INMEMORY` | `1` keeps `fluid secrets` values in memory instead of the OS keychain. Tests only. |
| `FLUID_ENCRYPTION_KEY`, `FLUID_ENCRYPTION_PASSPHRASE` | Fernet key, or a passphrase it is derived from, for the encrypted credential store. |
| `FLUID_ALLOW_PLAINTEXT_AI_SECRETS` | Legacy plaintext fallback for AI provider secrets. |
| `FLUID_ALLOW_PLAINTEXT_SOURCE_SECRETS` | Legacy plaintext secrets in `sources.yaml`; the file must also be mode 600. |

## Marketplace

| Variable | Effect |
|---|---|
| `FLUID_PUBLIC_REGISTRY` | Public registry URL used when `FLUID_MARKETPLACE_FALLBACK=public`. |
| `FLUID_MARKETPLACE_FALLBACK` | `local` (default), `public` or `none`: what `fluid marketplace` uses when no Command Center marketplace is available. |
| `FLUID_MARKET_CACHE_TTL` | Cache lifetime in **minutes**. |
| `FLUID_MARKET_DEFAULT_LIMIT` | Default page size for `fluid market`. |
| `FLUID_MARKET_MIN_QUALITY` | Minimum quality score for listed products. |
| `FLUID_MARKET_TIMEOUT` | Request timeout in seconds. |

## Plugins and providers

| Variable | Effect |
|---|---|
| `FLUID_PROVIDERS` | Comma-separated provider modules to load instead of the default set. |
| `FLUID_PLUGIN_STRICT_COMPAT` | `1`, `true` or `yes` fails on a plugin compatibility mismatch instead of warning. |
| `FLUID_PLUGINS_ALLOWLIST`, `FLUID_PLUGINS_BLOCKLIST` | Allow or block plugins by name. See [plugins](../cli/plugins.md). |

## Variables with no effect in 0.18.1

Earlier versions of this page listed the variables below. In 0.18.1 nothing reads them, or what reads them is not part of the running CLI, so setting them changes nothing. No consumer was found for these in the 0.18.1 source.

| Variable | What to use instead |
|---|---|
| `FLUID_SAFE_MODE`, and the global `--safe-mode` flag | Neither refuses a network call. See [Network safety](./network-safety.md) for the checks that do exist. |
| `FLUID_AUTO_CONFIRM` | `fluid apply --yes`. `fluid apply` asks for confirmation only on an interactive terminal. |
| `FLUID_DRY_RUN`, `FLUID_DEBUG`, `FLUID_TRACE`, `FLUID_PROFILING`, `FLUID_RICH_OUTPUT` | `--dry-run`, `--debug`, `--profile`, `--no-color` on the command. |
| `FLUID_MAX_FILE_SIZE_MB`, `FLUID_PARALLEL_OPERATIONS`, `FLUID_CACHE_ENABLED`, `FLUID_CACHE_TTL_SECONDS`, `FLUID_TIMEOUT_SECONDS` | None. |
| `FLUID_LOG_FORMAT` | Read into the config object, but `FLUID_LOG_FORMAT=text` did not change the stderr format when measured on 0.18.1. |
| `FLUID_DIAG_OUT_DIR` | `fluid doctor --out-dir`. `doctor` sets this variable for the diagnostic script it starts; it does not read it. |
| `FLUID_CONFIG_PATH` | None. Generated pipelines set it; the CLI does not read it. |
| `FLUID_DOMAIN`, `FLUID_LAYER_PROPERTY_ID`, `FLUID_PRODUCT_TYPE_PROPERTY_ID`, `FLUID_TIME_GRAINS`, `FLUID_LLM_TEMPERATURE`, `FLUID_MAJORS` | None. These are not read anywhere in the package. |
| `FLUID_EXTRA_PIP_SPECS` | Named in a note that `fluid generate ci` prints for engines it cannot install, but no generated pipeline reads it. Put the extras in `--fluid-package-spec`. |
| `FLUID_MARKET_URL` | Named in the `market_discovery_failed` suggestion, but not read. Use `FLUID_API_URL`, `FLUID_PUBLIC_REGISTRY` and `FLUID_MARKETPLACE_FALLBACK`. |

## Python 3.10 and the litellm cap

litellm 1.98.0 added a module that imports `NotRequired` straight from `typing`, which landed there in Python 3.11, so importing litellm raised `ImportError` on 3.10 while its metadata still declared 3.10 support. `pyproject.toml` therefore splits the pin on an environment marker: `litellm>=1.83.7,<2` on 3.11 and newer, `litellm>=1.83.7,<1.98` below it. The `>=1.83.7` floor is the same on both branches. The second line goes away once upstream guards that import.

## See also

- [Operating in CI](./operating-in-ci.md): the pipeline parameters and the variables a runner needs
- [Production troubleshooting](./production-troubleshooting.md): errors and what to do
- [LiteLLM backend](./litellm-backend.md): LLM variables in context
- [Cost tracking](./cost-tracking.md): the LLM cost ceilings in context. The acquisition `cost.budget` is described under [source-aligned acquisition](./source-aligned-acquisition.md#cost-tracking-and-budget-gates)
- [Network safety](./network-safety.md): SSRF allowlists in context
- [Catalog overview](../cli/catalogs/overview.md): publish-side variables in context
- [`fluid generate iac`](../cli/generate-iac.md): IaC engine variables in context
