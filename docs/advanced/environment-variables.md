# Environment Variables

Canonical index of `FLUID_*` environment variables on `v0.8.6`. Grouped by category. Where a cluster has its own dedicated page, the cluster header links out to the page rather than duplicating its content.

> **Convention:** truthy values are `1` / `true` / `yes` (case-insensitive); falsy values are `0` / `false` / `no` / empty. Numeric vars accept plain integers unless noted otherwise.

## CLI behaviour

| Variable | Purpose |
|---|---|
| `FLUID_LOG_LEVEL` | Logging level — `DEBUG` / `INFO` / `WARNING` / `ERROR`. |
| `FLUID_LOG_FILE` | Write structured logs to this file in addition to stderr. |
| `FLUID_LOG_FORMAT` | `text` (default) or `json`. |
| `FLUID_QUIET` | Suppress non-essential output. Set by `--quiet`. |
| `FLUID_NONINTERACTIVE` | Skip prompts; use defaults. Set by `--non-interactive`. |
| `FLUID_NO_TUI` | Disable rich TUI overlays in long-running commands. |
| `FLUID_AUTO_CONFIRM` | Skip the destructive-apply confirmation prompt. Equivalent to `--yes`. |
| `FLUID_DEBUG` | Enable verbose debug output. |
| `FLUID_DRY_RUN` | Inhibit side-effects globally where supported. |
| `FLUID_BANNER` / `FLUID_BANNER_TODAY` | Suppress / override the daily banner. |
| `FLUID_RICH_OUTPUT` | Force rich-coloured output (default: auto-detect from TTY). |
| `FLUID_TRACE` | Emit per-call timing traces. |

## Project & workspace

| Variable | Purpose |
|---|---|
| `FLUID_HOME` | Override the on-disk home directory (default `~/.fluid`). |
| `FLUID_PROJECT` | Cloud project / account identifier (BigQuery project, Snowflake account, etc.). |
| `FLUID_PROVIDER` | Default infrastructure provider (`aws` / `gcp` / `snowflake` / `local`). |
| `FLUID_REGION` / `FLUID_DEFAULT_REGION` | Default cloud region. |
| `FLUID_CONFIG` / `FLUID_CONFIG_PATH` | Override the project config file location. |
| `FLUID_ENV` | Default environment overlay name (`dev` / `staging` / `prod`). |
| `FLUID_DOMAIN` | Default `--domain` hint for `fluid forge`. |
| `FLUID_BUILD_PROFILE` | `experimental` (all commands) or `stable` (curated set). |
| `FLUID_RUN_ID` | Override the auto-generated run ID. |
| `FLUID_TIME_GRAINS` | Default grain enum for time-windowed tests (`hour,day,week,…`). |
| `FLUID_DIAG_OUT_DIR` | Where `fluid doctor` writes its diagnostic bundle. |

## LLM provider & routing

See the [LiteLLM backend](./litellm-backend.md) page for the full picture; the canonical names below are honoured by every LLM-driven command.

| Variable | Purpose |
|---|---|
| `FLUID_LLM_PROVIDER` | Default provider (`openai` / `anthropic` / `gemini` / `bedrock` / `vertex` / `ollama`, etc.). |
| `FLUID_LLM_MODEL` | Default model name (uses LiteLLM's model-name conventions). |
| `FLUID_LLM_API_KEY` | Fallback API key when a provider-specific env var is not set. |
| `FLUID_LLM_ENDPOINT` | Override the model endpoint URL. |
| `FLUID_LLM_STREAMING` | Toggle streaming responses (default on for capable models). |
| `FLUID_LLM_STRUCTURED_OUTPUTS` | Toggle structured-output mode where the provider supports it. |
| `FLUID_LLM_TEMPERATURE` | Default sampling temperature. |
| `FLUID_LLM_TIMEOUT_SECONDS` | Per-call LLM timeout. |
| `FLUID_LLM_ROUTING_ENDPOINT` / `FLUID_LLM_ROUTING_MODEL` | Optional routing-proxy endpoint and model alias. |
| `FLUID_LITELLM_MODEL_PREFIX` | Override the LiteLLM prefix for niche providers (e.g. `bedrock/`, `azure/`). |
| `FLUID_LLM_MODEL_PREFLIGHT` | Run a model-availability check before the first call. |
| `FLUID_OPENAI_STRICT_SCHEMA` | Force strict JSON-schema mode on OpenAI structured outputs. |
| `FLUID_GEMINI_RESPONSE_SCHEMA` | Override Gemini's response schema for structured outputs. |
| `FLUID_TIERED` | Use provider-local model tiers (`small` / `medium` / `large`) instead of explicit model names. |
| `FLUID_PRICES_JSON` | Path to a custom price table used when LiteLLM can't report a `usage.cost`. |
| `FLUID_TOKEN_COUNTER` | Override the token-counter implementation (`tiktoken` / `litellm` / `heuristic`). |

Provider-specific keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `AWS_*` for Bedrock, `GOOGLE_APPLICATION_CREDENTIALS` / `VERTEX_PROJECT` / `VERTEX_LOCATION` for Vertex) follow the underlying SDK conventions and are read directly by LiteLLM.

## Forge copilot

| Variable | Purpose |
|---|---|
| `FLUID_FORGE_NO_PICKER` | Skip the 5-mode menu and land straight in the legacy single-shot interview. |
| `FLUID_FORGE_NO_PREVIEW` | Skip the pre-write preview panel. |
| `FLUID_FORGE_NO_STREAMING_PREVIEW` | Disable live streaming of the contract preview. |
| `FLUID_FORGE_NO_WELCOME` | Suppress the welcome scan. |
| `FLUID_FORGE_AUTO_CI` | Auto-emit the CI scaffold after a forge run. |
| `FLUID_FORGE_LEGACY_COPILOT` | Fall back to the pre-`0.8.3` copilot path. |
| `FLUID_FORGE_STAGED_COPILOT` | Use the staged-copilot experimental loop. |
| `FLUID_FORGE_STAGED_TOOL_LOOP` | Use the staged tool-loop experimental loop. |
| `FLUID_COPILOT_AGENT_LOOP` | Override the copilot agent-loop driver. |
| `FLUID_COPILOT_EPISODIC_MEMORY` / `FLUID_COPILOT_SEMANTIC_MEMORY` | Toggle memory backends. |
| `FLUID_COPILOT_FORCE_INTERVIEW` | Force the interactive interview even when `--non-interactive` would otherwise skip it. |
| `FLUID_COPILOT_PARALLEL_PHYSICAL` | Run physical-modeling agents in parallel. |
| `FLUID_COPILOT_SELF_EVAL` | Enable the copilot's self-evaluation pass. |
| `FLUID_AGENT_COMPACT_AFTER` | Compact agent context after N turns. |
| `FLUID_COMPACTION_STRATEGY` | `truncate` / `summarize` / `hybrid`. |

## Catalog publish-side registrars

See [catalog overview](../cli/catalogs/overview.md).

| Variable | Purpose |
|---|---|
| `FLUID_CATALOG_DATAHUB_URL` | DataHub GMS endpoint. Falls back to `DATAHUB_GMS_URL`. |
| `FLUID_CATALOG_DATAHUB_TOKEN` | DataHub PAT. Falls back to `DATAHUB_GMS_TOKEN`. |
| `FLUID_CATALOG_DATAHUB_SPEC_BASE_URL` | Base URL for spec source documents. |
| `FLUID_CATALOG_DMM_URL` | Data Mesh Manager endpoint. Default `https://api.datamesh-manager.com`. Falls back to `DMM_API_URL`. |
| `FLUID_CATALOG_DMM_TOKEN` | DMM API key. Falls back to `DMM_API_KEY`. |
| `FLUID_CATALOG_OPENMETADATA_URL` | OpenMetadata REST endpoint. |
| `FLUID_CATALOG_OPENMETADATA_TOKEN` | OpenMetadata bearer token. |
| `FLUID_LAYER_PROPERTY_ID` | DataHub structured-property URN for `metadata.layer`. |
| `FLUID_PRODUCT_TYPE_PROPERTY_ID` | DataHub structured-property URN for `metadata.productType`. |

## FLUID Command Center

| Variable | Purpose |
|---|---|
| `FLUID_COMMAND_CENTER_URL` | Command Center base URL. |
| `FLUID_COMMAND_CENTER_API_KEY` | Command Center API key. |
| `FLUID_COMMAND_CENTER_ENABLED` | Master enable / disable toggle. |
| `FLUID_COMMAND_CENTER_HOST_ALLOWLIST` | Comma-separated host suffixes for the publish-side SSRF allowlist. |
| `FLUID_COMMAND_CENTER_TIMEOUT` | Per-request timeout (seconds). |
| `FLUID_CC_ENDPOINT` | Legacy alias for `FLUID_COMMAND_CENTER_URL`. |
| `FLUID_DISABLE_CC_DETECTION` | Skip the auto-detection probe at CLI start. |
| `FLUID_API_KEY` / `FLUID_API_URL` / `FLUID_BEARER_TOKEN` / `FLUID_OIDC_TOKEN` | Generic auth fallbacks. |

## Cost & budget gates

See [cost tracking](./cost-tracking.md).

| Variable | Purpose |
|---|---|
| `FLUID_COST_LIMIT_USD` | Global cost cap across a CLI invocation. |
| `FLUID_COST_LIMIT_USD_PER_PRODUCT` | Per-product cap. |
| `FLUID_COST_LIMIT_USD_PER_RUN` | Per-run cap. |
| `FLUID_STAGE_BUDGET_<STAGE>` | Per-stage budget (`FLUID_STAGE_BUDGET_PLAN`, `FLUID_STAGE_BUDGET_APPLY`, etc.). |

## Store, secrets, encryption

| Variable | Purpose |
|---|---|
| `FLUID_STORE_BACKEND` | `file` (default) / `sqlite` / `postgres`. |
| `FLUID_STORE_DSN` | Connection string when `FLUID_STORE_BACKEND=sqlite|postgres`. |
| `FLUID_STORE_PATH` / `FLUID_STORE_ROOT` | Override the file-store path. |
| `FLUID_STORE_VECTOR_BACKING` | Vector-store backend (`duckdb` / `lancedb`). |
| `FLUID_SECRETS_FILE` | Path to an encrypted secrets file. |
| `FLUID_SECRETS_INMEMORY` | Use the in-memory secrets store (tests only). |
| `FLUID_ENCRYPTION_KEY` / `FLUID_ENCRYPTION_PASSPHRASE` | Fernet key / passphrase for the encrypted credential store. |
| `FLUID_ALLOW_PLAINTEXT_AI_SECRETS` | Legacy plaintext fallback for AI provider secrets (chmod 600 enforced). |
| `FLUID_ALLOW_PLAINTEXT_SOURCE_SECRETS` | Legacy plaintext fallback for catalog-source secrets. Disables the OS-keyring default. |

## Network safety / SSRF

See [network safety](./network-safety.md).

| Variable | Purpose |
|---|---|
| `FLUID_WEBHOOK_HOST_ALLOWLIST` | Comma-separated host suffixes the webhook alerter is allowed to call. |
| `FLUID_FEDERATION_HOST_ALLOWLIST` | Same, for the federation digests fetcher. |
| `FLUID_COMMAND_CENTER_HOST_ALLOWLIST` | Same, for Command Center publish. |
| `FLUID_ALLOW_METADATA_SERVICE` | Allow outbound calls to cloud metadata services (169.254.169.254). Off by default. |
| `FLUID_SAFE_MODE` | Master kill-switch for outbound network operations. |

## Source-aligned acquisition & build runners

| Variable | Purpose |
|---|---|
| `FLUID_RUNNER_HOST_OVERRIDE` | Override the runner host (wins over `TESTCONTAINERS_HOST_OVERRIDE`). |
| `FLUID_DBT_FORWARD_ENV` | Extra env-var keys / prefixes the dbt runner forwards. |
| `FLUID_PII_TOKENIZATION_KEY` | HMAC key for PII tokenization (production-only). |
| `FLUID_PARALLEL_OPERATIONS` | Max parallelism for runner operations. |
| `FLUID_UPSTREAM_CONTRACTS` | Search path for upstream `contract.fluid.yaml` references. |
| `FLUID_ROLLBACK_KEEP_LAST_N` | Retention window for the rollback store. |

## OpenTofu / IaC

See [`fluid generate iac`](../cli/generate-iac.md).

| Variable | Purpose |
|---|---|
| `FLUID_TOFU_TIMEOUT_SECONDS` | Per-`tofu` subprocess timeout. Default `1800`. |

## Marketplace

| Variable | Purpose |
|---|---|
| `FLUID_PUBLIC_REGISTRY` | Override the public marketplace registry URL. |
| `FLUID_MARKET_CACHE_TTL` | Local cache TTL (seconds). |
| `FLUID_MARKET_DEFAULT_LIMIT` | Default page size for `fluid market list`. |
| `FLUID_MARKET_MIN_QUALITY` | Filter listed products by minimum quality score. |
| `FLUID_MARKET_TIMEOUT` | Per-request timeout. |
| `FLUID_MARKETPLACE_FALLBACK` | Fallback registry URL when the primary is unreachable. |

## Caching

| Variable | Purpose |
|---|---|
| `FLUID_CACHE_ENABLED` | Master cache toggle. |
| `FLUID_CACHE_TTL_SECONDS` | Default cache TTL. |
| `FLUID_DISCOVERY_CACHE` | Override the discovery cache path. |

## Install / package management

| Variable | Purpose |
|---|---|
| `FLUID_ALLOW_PRERELEASE` | Allow `pip install --pre`-style upgrades during in-CLI bootstraps. |
| `FLUID_PACKAGE_SPEC` | Override the `data-product-forge` install spec for bootstrap scripts. |
| `FLUID_EXTRA_PIP_SPECS` | Extra packages installed alongside the CLI. |
| `FLUID_PIP_INDEX_URL` / `FLUID_PIP_EXTRA_INDEX_URL` | Custom PyPI indexes. |
| `FLUID_MAJORS` | Pin the major-version line during bootstraps. |
| `FLUID_MAX_FILE_SIZE_MB` | Reject contract / artifact files larger than this. |

## See also

- [LiteLLM backend](./litellm-backend.md) — LLM env vars in context
- [Cost tracking](./cost-tracking.md) — cost-budget gates in context
- [Network safety](./network-safety.md) — SSRF allowlists in context
- [Catalog overview](../cli/catalogs/overview.md) — publish-side catalog env vars in context
- [`fluid generate iac`](../cli/generate-iac.md) — IaC engine env vars in context
