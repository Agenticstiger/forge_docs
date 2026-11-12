# `fluid doctor`

Check that the CLI and the machine it runs on are ready: copilot configuration, the memory store, the tools and Python libraries that individual commands shell out to or import, and the `FLUID_*` switches that change CLI behaviour.

## Syntax

```bash
fluid doctor [--scope SCOPE] [--env] [--json] [--features-only] [--strict] [--extended] [--out-dir DIR] [--verbose]
```

## Examples

Run the built-in checks. With no flags, `fluid doctor` reports copilot readiness, the active memory-store backend and feature availability:

```bash
fluid doctor
```

Check one area, for example the binaries that deploy and sign:

```bash
fluid doctor --scope infra
```

```text
fluid doctor — scope=infra
  ✓ binary:docker: 'docker' on PATH
  ✓ binary:helm: 'helm' on PATH
  ✓ binary:kubectl: 'kubectl' on PATH
  ✓ binary:tofu: 'tofu' on PATH
  ! binary:cosign: 'cosign' not found on PATH
      fix: install 'cosign' (see https://agenticstiger.github.io/forge_docs/cli/doctor.html)
5 checks  errors=0  warnings=1
```

That last `fix:` line points at this page. See [Installing what doctor checks](#installing-what-doctor-checks).

Gate a CI job on every check being clean:

```bash
fluid doctor --scope all --json | jq -e .ok
```

List the runtime switches the CLI recognises and what they are set to:

```bash
fluid doctor --env
```

## Options

| Option | Description |
| --- | --- |
| `--scope {authoring\|pipeline\|ingestion\|infra\|catalog\|all}` | Run one group of checks, or all of them. There is no default scope: without `--scope`, `fluid doctor` runs the checks described under [Without `--scope`](#without-scope). |
| `--env` | List the recognised `FLUID_*` runtime switches with their current value, source and default behaviour. See [`--env`](#env-the-runtime-switches). |
| `--json` | Machine-readable output. What it contains depends on the other flags; see [`--json`](#json-output). |
| `--features-only` | Run only the feature-availability check and skip the rest of the default run. |
| `--strict` | *(since 0.27.0, [forge-cli #786](https://github.com/Agenticstiger/forge-cli/pull/786))* Exit `1` whenever the summary says "Action needed", copilot readiness included. See [`--strict`](#strict). |
| `--extended`, `--comprehensive` | Also run a `scripts/diagnose.sh` that you provide in the current directory. See [`--extended`](#extended). |
| `--out-dir DIR` | Where `--extended` writes its diagnostic files. Default `runtime/diag`. |
| `--verbose`, `-v` | Show detailed output. |

## Without `--scope`

`fluid doctor` with neither `--scope` nor `--env` runs the default checks:

- **Forge copilot readiness**: whether an LLM provider and model are configured, and whether credentials are present. *On forge-cli `main`, not yet in a release ([forge-cli #850](https://github.com/Agenticstiger/forge-cli/pull/850)).* Its Endpoint row says `Provider default` when no endpoint is set and the provider picks its own address; through 0.28.0 it showed a `litellm://<provider>/<model>` label. A ready coding agent's row says `coding-agent://<name>`. With `FLUID_LLM_PROVIDER` set to `claude-code`, `codex`, `cursor` or `kiro`, the copilot is ready when the agent's CLI (`claude`, `codex`, `cursor-agent` or `kiro-cli`) is on `PATH`; the CLI's own sign-in is not checked. Without the CLI, the table says Setup needed and the panel names it: `The 'cursor-agent' CLI for cursor is not on PATH.` Through 0.28.0 these providers read "No API key found". With nothing configured and no terminal, readiness reports the provider a non-interactive forge run picks, or `Not selected` when that pick finds nothing; see [When nothing is configured](../advanced/llm-providers.md#when-nothing-is-configured). *On forge-cli `main`, not yet in a release ([forge-cli #852](https://github.com/Agenticstiger/forge-cli/pull/852)).* With no provider selected, the Message row that `--verbose` shows gives the same reason as forge's `copilot_no_llm_provider`, for example `No LLM provider is selected: OPENAI_API_KEY, ANTHROPIC_API_KEY are all set, so none of them is chosen. Pick one with --llm-provider or FLUID_LLM_PROVIDER.` Before #852 the row always read `No LLM provider configured. Run 'fluid ai setup' or set an API key env var.`, and forge fell back to `gemini` where readiness said `Not selected`. A `user:password@` in the endpoint shows as `***:***@`. *On forge-cli `main`, not yet in a release ([forge-cli #854](https://github.com/Agenticstiger/forge-cli/pull/854)).* Readiness now walks the ladder a run walks, so the Provider row names what a run uses: `FLUID_FORGE_AGENT` counts as naming the provider, and a provider that `FLUID_LLM_PROVIDER` names reports its catalog model, not the one `fluid ai setup` saved; see [Which provider a run uses](../advanced/llm-providers.md#which-provider-a-run-uses). *On forge-cli `main`, not yet in a release ([forge-cli #853](https://github.com/Agenticstiger/forge-cli/pull/853)).* The Auth row counts `FLUID_LLM_API_KEY` only when `FLUID_LLM_PROVIDER` or `FLUID_FORGE_AGENT` names the provider.
- **Memory store backend**: which backend holds copilot memory (`file`, `sqlite`, `postgres` or `vector`), where it lives, and whether it is readable and writable.
- **Provider readiness**: under `--verbose`, a **Databricks Provider** row reports `Not configured` when no `DATABRICKS_*` workspace variable is set, and otherwise whether the credential resolves under the same rules `fluid apply` uses, whether `DATABRICKS_WAREHOUSE_ID` is set and whether `databricks-sdk` is installed. It never opens a connection and never changes the exit code. See [Databricks](../providers/databricks.md#fluid-doctor-and-the-welcome-scan).
- **Feature availability**: a table of CLI components (the schema manager, the sovereignty and agent-policy validators, the provider action parsers for GCP, AWS and Snowflake, the dbt engine, the copilot, the LiteLLM backend and the agent web tools), each marked available, not available or not installed. `--features-only` prints just this table.

It prints a summary panel followed by the readiness and backend tables; the feature table appears under `--verbose` or when a feature is missing. The exit code is `1` when a feature the CLI treats as critical is unavailable, and `0` otherwise. A missing LLM key, a missing Snowflake driver and a missing dbt install do not change it, except that [`--strict`](#strict) also fails a copilot that is not ready.

## `--strict`

*(since 0.27.0, [forge-cli #786](https://github.com/Agenticstiger/forge-cli/pull/786))*

The summary panel says **Action needed** when a feature check fails or the copilot is not ready (its readiness table says "Setup needed"). Through 0.26.0 only the first case changed the exit code. A copilot that was not ready printed "Action needed" and the run still exited `0`, so a CI gate on `fluid doctor` could never fail for it.

With `--strict`, `fluid doctor` exits `1` whenever the summary says "Action needed", in the text report and with `--json`. The default exit code does not change.

```bash
fluid doctor --strict
```

`--json` carries the reason. Next to `store_backend` the payload now has `copilot_ready` and `action_needed`, so a CI job can tell a failed feature check from a copilot that is not set up:

```bash
fluid doctor --json | jq '{copilot_ready, action_needed}'
```

```json
{
  "copilot_ready": false,
  "action_needed": true
}
```

`--strict` belongs to the default run. `--features-only` prints no summary, and `--scope` and `--env` run their own checks, so all three ignore it.

## `--scope`: what each scope checks

Each scope is a fixed list of checks. A check reports `ok`, `warn` or `error`.

| Scope | Checks | Severity when it fails |
| --- | --- | --- |
| `authoring` | `schema:latest_version`: the newest stable schema bundled with the CLI is at least 0.7.3. | error |
| `pipeline` | `dispatcher:acquisition_engines`: the acquisition-engine dispatcher registers the expected six engines. Then one importability check for each runner module: `duckdb`, `dlt`, `meltano`, `airbyte`, `kafka_connect` and `debezium`. | error for the dispatcher, warn for a runner module |
| `ingestion` | Python libraries importable: `duckdb`, `dlt`, `httpx`, `snowflake.connector`. | warn |
| `infra` | Binaries on `PATH`: `docker`, `helm`, `kubectl`, `tofu`, `cosign`. | warn |
| `catalog` | The `datahub`, `openmetadata` and `datamesh_manager` registrar modules import. | warn |
| `all` | The checks of the five scopes above, in that order. | |

Two things the scopes do not do. They do not check credentials, network reachability or LLM readiness; for credentials use [`fluid auth status`](./auth.md). And a check that only looks at `PATH` or at `import` cannot tell you the tool works, only that it is present.

### Exit codes and severity

Missing tools and libraries are **warnings**, not errors. `fluid doctor --scope ingestion` on a machine without `duckdb` prints three `!` lines and exits `0`. The exit code is `1` only when a check reports an `error`, which in the scopes above means a broken engine dispatcher or a bundled schema older than 0.7.3.

To fail a job on a missing tool, read the structured output instead of the exit code:

```bash
fluid doctor --scope infra --json | jq -e .ok
```

`ok` is `true` only when every check is `ok`, so a single warning makes it `false` and `jq -e` exits `1`.

## `--json` output

The shape depends on which surface you asked for:

| Invocation | JSON |
| --- | --- |
| `fluid doctor --scope <s> --json` | `{"scope", "ok", "results": [...]}`, one result per check. |
| `fluid doctor --env --json` | `{"env": [...], "telemetry": {...}}`. |
| `fluid doctor --json` (no `--scope`, no `--env`) | The memory-store section, `{"store_backend": {...}}`. *(since 0.27.0, [forge-cli #786](https://github.com/Agenticstiger/forge-cli/pull/786))* It also carries `copilot_ready` and `action_needed`; see [`--strict`](#strict). Per-check results need `--scope`. |

A scoped result looks like this:

```bash
fluid doctor --scope authoring --json
```

```json
{
  "scope": "authoring",
  "ok": true,
  "results": [
    {
      "name": "schema:latest_version",
      "severity": "ok",
      "detail": "bundled latest version is 0.7.5",
      "fix": null,
      "doc": "https://agenticstiger.github.io/forge_docs/cli/doctor.html"
    }
  ]
}
```

`fix` carries the remedy for a failed check and is `null` for a passing one. `doc` points at this page.

## `--env`: the runtime switches

`fluid doctor --env` prints a table of the `FLUID_*` variables (and a few others, such as `DBT_EXECUTABLE` and `DO_NOT_TRACK`) that change how the CLI behaves. Each row shows the variable, its current value, a `Source` (`env` when you set it, `default` when you did not), the default behaviour and a one-line description. The last line of the output states whether anonymous telemetry is on; it is off unless you opt in.

With `--json`, each row is an object:

```bash
fluid doctor --env --json | jq '.env[] | select(.name == "FLUID_FEDERATION_TIMEOUT_SECONDS")'
```

```json
{
  "name": "FLUID_FEDERATION_TIMEOUT_SECONDS",
  "value": "(unset)",
  "source": "default",
  "default": "30s default",
  "description": "Per-git-operation cap when `fluid apply` fetches a federated upstream digest; raise it for a genuinely large upstream repo"
}
```

This lists the switches `fluid doctor` knows about. It is a convenient first look, not a substitute for the full table in [Environment variables](../advanced/environment-variables.md).

## `--extended`

`fluid doctor --extended` runs `bash scripts/diagnose.sh`, resolved relative to the **current directory**, with `FLUID_DIAG_OUT_DIR` set to `--out-dir`. As of 0.18.1 the `data-product-forge` package and the forge-cli repository do not include that script, so `--extended` works only in a directory where you have put one. Anywhere else the command prints the default report and then fails:

```text
CLI command error
❌ Extended diagnostics are not installed in this checkout.  [ERR_DOCTOR_EXTENDED_UNAVAILABLE]
  script: /path/to/project/scripts/diagnose.sh
  readme: /path/to/project/scripts/README.md
  hint: Run `fluid doctor` for built-in checks only.
```

The exit code is `1`. Leave `--extended` out unless your project provides its own `scripts/diagnose.sh`.

## The 0.28.0 install change

*(from 0.27.0)* `fluid doctor` prints one line once per run. On 0.27.0 it reads:

```text
AI/MCP move to extras in 0.28.0: pip install 'data-product-forge[standard]'
```

*(since 0.28.0, [forge-cli #837](https://github.com/Agenticstiger/forge-cli/pull/837))* On 0.28.0 the notice reads `AI and MCP are extras since 0.28.0: pip install 'data-product-forge[standard]'` and prints only when litellm or mcp is not installed (0.27.0 printed it every run), and a configured provider is no longer reported as ready when litellm is missing: the Next steps panel says `<provider> needs litellm, which is not installed` and prints `pip install 'data-product-forge[litellm]'`.

It also reports three optional packages in the AI checks: the LiteLLM backend, the MCP SDK and the OpenLineage client. Each shows its version when installed, or `Not installed (optional)` with the `pip install 'data-product-forge[<extra>]'` line. None of them is imported: doctor reads the version from the package metadata, so it makes no network call for litellm's cost map.

## Installing what doctor checks

The `fix:` line for a missing binary, and the `doc` field in `--json` output, point at this page. A warning matters only when you use the command that needs the tool.

| Check | Needed by | Install |
| --- | --- | --- |
| `tofu` | `fluid apply` against `aws`, `gcp`, `snowflake` and `confluent` bindings, which compile the contract to OpenTofu and run `tofu`. | Run `fluid apply --ensure-opentofu`: if `tofu` is missing, the CLI downloads a pinned, SHA-256-verified build before the apply. Or install it from [opentofu.org](https://opentofu.org/docs/intro/install/). Pin a version with `FLUID_OPENTOFU_VERSION`. |
| `cosign` | `fluid bundle --sign` and [`fluid verify-signature`](./verify-signature.md). | `brew install cosign`, or see the [cosign installation guide](https://docs.sigstore.dev/cosign/installation/). |
| `docker` | Managed-mode acquisition engines that provision infrastructure with Docker Compose. See [Source-aligned acquisition](../advanced/source-aligned-acquisition.md). | [Docker's install guide](https://docs.docker.com/get-docker/). |
| `helm`, `kubectl` | Managed-mode acquisition engines that provision infrastructure with Helm on Kubernetes. | [Helm install guide](https://helm.sh/docs/intro/install/) and [Kubernetes tools](https://kubernetes.io/docs/tasks/tools/). |
| `duckdb` | The `local` provider and DuckDB acquisition builds. | `pip install "data-product-forge[local]"`, which installs `duckdb` at the version the CLI requires for its contract-SQL sandbox. See [DuckDB sandbox](../advanced/duckdb-sandbox.md). |
| `dlt` | `dlt` acquisition builds. | `pip install dlt`. As of 0.18.1 `data-product-forge` has no `dlt` extra. |
| `litellm`, `mcp`, `openlineage` | *(from 0.27.0)* AI forge, `fluid mcp serve` and lineage emission. | Part of a base install through 0.27.0; since 0.28.0 install them with `pip install "data-product-forge[standard]"`, or `[ai]`, `[mcp]` or `[lineage]` for one. *(since 0.28.0, [forge-cli #837](https://github.com/Agenticstiger/forge-cli/pull/837))* |
| `httpx` | A core dependency of the CLI. | Installed with `data-product-forge`; a failure here points to a broken Python environment. |
| `snowflake.connector` | The `snowflake` provider. | `pip install "data-product-forge[snowflake]"`. The `fix:` line for this check reads `pip install snowflake`, which is not the package that provides the connector; use the extra. |

The `pipeline` and `catalog` scopes check modules that ship inside `data-product-forge`. If one fails to import, reinstall the package rather than installing a separate library:

```bash
pip install --force-reinstall data-product-forge
```

## Notes

- Use [`fluid describe --self`](./describe.md) to read what the CLI ships. `describe` reports what is installed; `doctor` reports whether the tools around it are present.
- For the first response to a failed run, the sequence in [Production troubleshooting](../advanced/production-troubleshooting.md) starts with `fluid doctor`.
