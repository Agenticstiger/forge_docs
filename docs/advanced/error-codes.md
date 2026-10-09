# Error codes

A failure the CLI raises as a catalogued error prints an event name and a stable `ERR_` code, then suggestions and a link to this site. This page explains the parts of that output and lists the events that carry curated suggestions.

```bash
fluid verify missing.fluid.yaml
```

```text
...
❌ contract_file_not_found  [ERR_CONTRACT_FILE_NOT_FOUND]
  path: missing.fluid.yaml

💡 Suggestions:
  • Check that the contract file path is correct
  • Run 'ls *.fluid.yaml' to see contracts in the current directory

📖 Documentation: https://agenticstiger.github.io/forge_docs/advanced/production-troubleshooting.html
```

| Part | What it is |
|---|---|
| `❌ contract_file_not_found` | The event name, in snake case. It is stable, and it is the name this site's pages use |
| `[ERR_CONTRACT_FILE_NOT_FOUND]` | The code: `ERR_` and the event name in upper case. Parse this in CI rather than the message text, which changes |
| `path:` and other indented lines | Facts the raise site attached: a path, a mode, a `hint` |
| `💡 Suggestions` | Next steps. A raise site may supply its own, and then they replace the catalog's, so the same event can print different suggestions from different commands. `fluid plan missing.fluid.yaml` prints the same code with three other suggestions |
| `📖 Documentation` | A link chosen from a fixed route table. An event with no dedicated page links to [Production troubleshooting](./production-troubleshooting.md), without an anchor |

An event the catalog does not list still prints its `ERR_` code, with no curated suggestions and the same fallback link. [Production troubleshooting](./production-troubleshooting.md) covers events by name, for example `bundle_env_mismatch`, `plan_env_mismatch` and the `state_*` family.

Build runners, providers and imports raise a second kind of error that prints as a panel with `why`, `fix` and `doc` rows. Those are in [Typed CLI errors](./typed-cli-errors.md).

## Where the links land

The route table sends an event to one of these pages, and the entries below name the page for each event.

| Link goes to | Used by |
|---|---|
| [`fluid providers`](../cli/providers.md) | The provider events |
| [`fluid secrets`](../cli/secrets.md) | `copilot_missing_llm_api_key` |
| [Sovereignty](../concepts/sovereignty.md) | The policy and sovereignty events, except `policy_compiler_crashed` |
| [`fluid policy compile`, Errors](../cli/policy-compile.md#errors) | `policy_compiler_crashed` *(unreleased, [forge-cli #710](https://github.com/Agenticstiger/forge-cli/pull/710))* |
| [`fluid verify-signature`](../cli/verify-signature.md) | The signing events |
| [Getting started](../getting-started/README.md) | `opentofu_engine_install_failed` |
| [Typed CLI errors](./typed-cli-errors.md) | The schema-version events and the connectivity events |
| [Production troubleshooting](./production-troubleshooting.md) | Events not listed above |

## The catalogued events

The suggestions below are the CLI's own wording as of 0.18.1. Where a suggestion is out of date, a note under it says so.

## Providers

### provider_not_specified

`ERR_PROVIDER_NOT_SPECIFIED`. The documentation link lands on [`fluid providers`](../cli/providers.md).

- Pass a provider: --provider local|gcp|snowflake|aws|azure
- Or set the FLUID_PROVIDER environment variable
- Run 'fluid providers' to list the available providers

### provider_not_found

`ERR_PROVIDER_NOT_FOUND`. The documentation link lands on [`fluid providers`](../cli/providers.md).

- Run 'fluid providers' to see the available providers
- Check the provider name spelling
- Install the provider extra, e.g. pip install 'data-product-forge[gcp]'

### provider_unknown

`ERR_PROVIDER_UNKNOWN`. The documentation link lands on [`fluid providers`](../cli/providers.md).

- Run 'fluid providers' to see the available providers
- Valid built-ins: local, gcp, snowflake, aws, azure

As of 0.18.1 the second suggestion names `azure`, but `fluid providers` lists `aws`, `datamesh_manager`, `gcp`, `local`, `redshift` and `snowflake`, and `--provider azure` is refused as unknown.

### provider_blocked_by_policy

`ERR_PROVIDER_BLOCKED_BY_POLICY`. The documentation link lands on [`fluid providers`](../cli/providers.md).

- This provider is named in FLUID_PLUGINS_BLOCKLIST, or an FLUID_PLUGINS_ALLOWLIST is set and does not name it
- Run 'fluid plugins --role provider' to see the effective policy
- Unset or amend the env var to re-enable it

### reserved_provider_name

`ERR_RESERVED_PROVIDER_NAME`. The documentation link lands on [`fluid providers`](../cli/providers.md).

- Choose a provider name that is not a reserved built-in

## Contract files and loading

### contract_required

`ERR_CONTRACT_REQUIRED`. The documentation link lands on [Production troubleshooting](./production-troubleshooting.md).

- Pass the contract path: fluid &lt;command&gt; path/to/contract.fluid.yaml
- Or run from a directory that contains a single contract.fluid.yaml
- Scaffold one with 'fluid init' or 'fluid forge'

### contract_not_found

`ERR_CONTRACT_NOT_FOUND`. The documentation link lands on [Production troubleshooting](./production-troubleshooting.md).

- Check that the contract file path is correct
- Ensure the file has a .yaml, .yml, or .json extension
- Scaffold one with 'fluid init' or 'fluid forge'

### contract_file_not_found

`ERR_CONTRACT_FILE_NOT_FOUND`. The documentation link lands on [Production troubleshooting](./production-troubleshooting.md).

- Check that the contract file path is correct
- Run 'ls *.fluid.yaml' to see contracts in the current directory

### contract_load_failed

`ERR_CONTRACT_LOAD_FAILED`. The documentation link lands on [Production troubleshooting](./production-troubleshooting.md).

- Verify the YAML/JSON syntax is valid
- Check file permissions and that the encoding is UTF-8
- Run 'fluid validate &lt;contract&gt;' for a detailed report

### missing_contract

`ERR_MISSING_CONTRACT`. The documentation link lands on [Production troubleshooting](./production-troubleshooting.md).

- Pass the contract path: fluid &lt;command&gt; path/to/contract.fluid.yaml
- Or run from a directory that contains a single contract.fluid.yaml
- Scaffold one with 'fluid init' or 'fluid forge'

### loader_import_failed

`ERR_LOADER_IMPORT_FAILED`. The documentation link lands on [Production troubleshooting](./production-troubleshooting.md).

- Check that the loader module path is importable (on PYTHONPATH)
- Verify the module has no syntax/import errors: python -c 'import &lt;module&gt;'

### loader_missing_functions

`ERR_LOADER_MISSING_FUNCTIONS`. The documentation link lands on [Production troubleshooting](./production-troubleshooting.md).

- The loader module must define the required entry-point functions — check its API
- Define the expected functions (e.g. load/run) — see the custom-loader docs

## Schema versions

### invalid_schema_version

`ERR_INVALID_SCHEMA_VERSION`. The documentation link lands on [Typed CLI errors, Validation & schema](./typed-cli-errors.md#validation-schema).

- Set a supported fluidVersion (current line: 0.7.x)
- Run 'fluid validate &lt;contract&gt;' to see the supported versions

### contract_version_unsupported

`ERR_CONTRACT_VERSION_UNSUPPORTED`. The documentation link lands on [Typed CLI errors, Validation & schema](./typed-cli-errors.md#validation-schema).

- Migrate the contract to the current 0.7.x schema
- Pre-0.7 contracts (0.4.0 / 0.5.x) are no longer supported

### invalid_min_version

`ERR_INVALID_MIN_VERSION`. The documentation link lands on [Typed CLI errors, Validation & schema](./typed-cli-errors.md#validation-schema).

- Use a valid PEP 440 / semver version string for the minimum bound

### invalid_max_version

`ERR_INVALID_MAX_VERSION`. The documentation link lands on [Typed CLI errors, Validation & schema](./typed-cli-errors.md#validation-schema).

- Use a valid PEP 440 / semver version string for the maximum bound

## Validation

### validation_failed

`ERR_VALIDATION_FAILED`. The documentation link lands on [Production troubleshooting](./production-troubleshooting.md).

- Run 'fluid validate &lt;contract&gt; --verbose' for the full error list
- Check required fields and the schema reference for your fluidVersion

### validation_error

`ERR_VALIDATION_ERROR`. The documentation link lands on [Production troubleshooting](./production-troubleshooting.md).

- Run 'fluid validate &lt;contract&gt; --verbose' for details

## Bundles

### bundle_not_found

`ERR_BUNDLE_NOT_FOUND`. The documentation link lands on [Production troubleshooting](./production-troubleshooting.md).

- Run 'fluid bundle &lt;contract&gt; --format tgz' to produce a bundle first
- Check the bundle path you passed

### bundle_manifest_invalid

`ERR_BUNDLE_MANIFEST_INVALID`. The documentation link lands on [Production troubleshooting](./production-troubleshooting.md).

- Re-create the bundle with 'fluid bundle' — the manifest is malformed

### bundle_missing_contract

`ERR_BUNDLE_MISSING_CONTRACT`. The documentation link lands on [Production troubleshooting](./production-troubleshooting.md).

- Re-create the bundle with 'fluid bundle' — it has no contract entry

### bundle_source_missing

`ERR_BUNDLE_SOURCE_MISSING`. The documentation link lands on [Production troubleshooting](./production-troubleshooting.md).

- Re-create the bundle with 'fluid bundle' — a referenced source file is absent

### bundle_load_failed

`ERR_BUNDLE_LOAD_FAILED`. The documentation link lands on [Production troubleshooting](./production-troubleshooting.md).

- The bundle is corrupt or truncated — re-create it with 'fluid bundle &lt;contract&gt;'

## Plan and apply

The state refusals (`state_shared_with_another_provider`, `state_migration_ambiguous` and the other `state_*` events) are described on [OpenTofu state](../concepts/state.md). The refusal for an env with no overlay (`overlay_declared_but_missing`) and the `bundle_env_mismatch` refusal are on [Environments and overlays](../concepts/environments-and-overlays.md); `plan_env_mismatch` is in [Production troubleshooting](./production-troubleshooting.md).

### planner_failed

`ERR_PLANNER_FAILED`. The documentation link lands on [Production troubleshooting](./production-troubleshooting.md).

- Run 'fluid validate &lt;contract&gt;' first to rule out a contract problem

### output_write_failed

`ERR_OUTPUT_WRITE_FAILED`. The documentation link lands on [Production troubleshooting](./production-troubleshooting.md).

- Check that the --out path is writable and the parent directory exists

### no_builds

`ERR_NO_BUILDS`. The documentation link lands on [Production troubleshooting](./production-troubleshooting.md).

- No build runners matched — check the contract's build/transform config
- Run 'fluid apply &lt;contract&gt; --mode amend-and-build' only when builds are defined

### verify_failed

`ERR_VERIFY_FAILED`. The documentation link lands on [Production troubleshooting](./production-troubleshooting.md).

- Run 'fluid verify &lt;contract&gt; --verbose' to see which reconciliation check failed

### opentofu_engine_install_failed

`ERR_OPENTOFU_ENGINE_INSTALL_FAILED`. The documentation link lands on [Getting started](../getting-started/README.md).

- Install OpenTofu &gt;= 1.6.0 and ensure 'tofu' is on PATH
- See https://opentofu.org/docs/intro/install/

### opentofu_init_failed

`ERR_OPENTOFU_INIT_FAILED`. The documentation link lands on [Typed CLI errors, Connectivity & secrets](./typed-cli-errors.md#connectivity-secrets).

- Check provider credentials and network access, then retry

### opentofu_plan_failed

`ERR_OPENTOFU_PLAN_FAILED`. The documentation link lands on [Production troubleshooting](./production-troubleshooting.md).

- Run 'fluid plan &lt;contract&gt;' and inspect the emitted plan for the failing action

### opentofu_region_moved

`ERR_OPENTOFU_REGION_MOVED`. The documentation link lands on [Production troubleshooting](./production-troubleshooting.md).

- If the resources should stay where they are, set the binding's location.region to the region the error names
- If they should move, empty and remove them there first (tofu destroy in the state directory the error names, with AWS_REGION set to the old region), then apply again

## Generate

### generate_iac_failed

`ERR_GENERATE_IAC_FAILED`. The documentation link lands on [Production troubleshooting](./production-troubleshooting.md).

- Run 'fluid validate &lt;contract&gt;' first to rule out a contract problem
- Re-run with --provider explicitly set if auto-detect picked the wrong cloud

### generate_iac_provider_mismatch

`ERR_GENERATE_IAC_PROVIDER_MISMATCH`. The documentation link lands on [Production troubleshooting](./production-troubleshooting.md).

- Drop --provider and let the cloud auto-detect from the contract's binding
- Or change the contract's exposes[].binding.platform to the cloud you meant to target — that is how a data product is retargeted, not --provider

### generate_iac_empty_module

`ERR_GENERATE_IAC_EMPTY_MODULE`. The documentation link lands on [Production troubleshooting](./production-troubleshooting.md).

- Check the contract's exposes[].binding carries the location fields the target cloud's emitter needs (bucket/dataset/database)
- Run 'fluid validate &lt;contract&gt;' — the Iceberg and Confluent binding gates name the specific field a skipped resource was missing
- Pass --allow-empty only if a resource-free module is genuinely intended

### generate_iac_aws_account_required

`ERR_GENERATE_IAC_AWS_ACCOUNT_REQUIRED`. The documentation link lands on [Production troubleshooting](./production-troubleshooting.md).

- Set AWS_ACCOUNT_ID to the account the module will be applied in, then re-run 'fluid generate iac' (it never looks the account up in AWS)
- 'fluid apply' resolves the account itself and needs no AWS_ACCOUNT_ID

### generate_ci_failed

`ERR_GENERATE_CI_FAILED`. The documentation link lands on [Production troubleshooting](./production-troubleshooting.md).

- Check the --system value is a supported CI provider and the contract validates
- Run 'fluid validate &lt;contract&gt;', then re-run with a supported --system (github_actions|gitlab|jenkins|azure_devops|...)

### validate_artifacts_input_missing

`ERR_VALIDATE_ARTIFACTS_INPUT_MISSING`. The documentation link lands on [Production troubleshooting](./production-troubleshooting.md).

- Pass the generated-artifacts path produced by 'fluid generate artifacts'

## AI and copilot

### copilot_missing_llm_api_key

`ERR_COPILOT_MISSING_LLM_API_KEY`. The documentation link lands on [`fluid secrets`](../cli/secrets.md).

- Run 'fluid ai setup' to configure a provider interactively
- Or set a provider key: OPENAI_API_KEY / ANTHROPIC_API_KEY / GEMINI_API_KEY
- For local models: --llm-provider ollama (no key required)
- For keyless authoring: run forge from your IDE (mcp-sampling) or --llm-provider claude-code

### copilot_missing_llm_model

`ERR_COPILOT_MISSING_LLM_MODEL`. The documentation link lands on [Production troubleshooting](./production-troubleshooting.md).

- Set FLUID_LLM_MODEL or pass --llm-model
- Run 'fluid ai setup' to pick a default model

### copilot_llm_model_preflight_failed

`ERR_COPILOT_LLM_MODEL_PREFLIGHT_FAILED`. The documentation link lands on [Typed CLI errors, Connectivity & secrets](./typed-cli-errors.md#connectivity-secrets).

- Check the provider API key and network connectivity
- For Ollama, start the local server and pull the requested model
- Pass --llm-model with a known-available model

### model_not_found

`ERR_MODEL_NOT_FOUND`. The documentation link lands on [Production troubleshooting](./production-troubleshooting.md).

- Run 'fluid ai setup' to pick a model the provider actually serves
- List the provider's models, then pass --llm-model &lt;name&gt;

## Policy and sovereignty

### policy_compile_failed

`ERR_POLICY_COMPILE_FAILED`. The documentation link lands on [Sovereignty](../concepts/sovereignty.md).

- Check the agent-policy block in the contract; run 'fluid policy check &lt;contract&gt;'

### policy_compiler_crashed

*(unreleased, [forge-cli #710](https://github.com/Agenticstiger/forge-cli/pull/710))* `ERR_POLICY_COMPILER_CRASHED`. The documentation link lands on [`fluid policy compile`, Errors](../cli/policy-compile.md#errors).

- Run 'fluid validate &lt;contract&gt;': policy compile reads accessPolicy and exposes without validating them against the contract schema
- If the contract validates, re-run with 'fluid --log-level DEBUG policy compile &lt;contract&gt;' to see the compiler's traceback

### policy_apply_failed

`ERR_POLICY_APPLY_FAILED`. The documentation link lands on [Sovereignty](../concepts/sovereignty.md).

- Run 'fluid policy check &lt;contract&gt;' to surface the offending rule before apply

### sovereignty_violation

`ERR_SOVEREIGNTY_VIOLATION`. The documentation link lands on [Sovereignty](../concepts/sovereignty.md).

- Move the offending binding into an allowed region, or widen 'sovereignty.allowedRegions' in the contract
- Run 'fluid validate &lt;contract&gt;' to see the same findings with full detail
- Set 'sovereignty.enforcementMode: advisory' to report without blocking

## Product authoring

### product_new_failed

`ERR_PRODUCT_NEW_FAILED`. The documentation link lands on [Production troubleshooting](./production-troubleshooting.md).

- Check the target directory is writable and the productType is valid (SDP/ADP/CDP)
- Pick an empty/new target dir and pass --data-product-type SDP|ADP|CDP explicitly

### product_add_failed

`ERR_PRODUCT_ADD_FAILED`. The documentation link lands on [Production troubleshooting](./production-troubleshooting.md).

- Run 'fluid validate' on the contract first; --type must be source|exposure|dq

### product_add_expose_not_found

`ERR_PRODUCT_ADD_EXPOSE_NOT_FOUND`. The documentation link lands on [Production troubleshooting](./production-troubleshooting.md).

- The --expose target does not exist in the contract — list exposes with 'fluid status'
- Add the expose first, or target an existing exposeId

## Market and blueprints

### market_discovery_failed

`ERR_MARKET_DISCOVERY_FAILED`. The documentation link lands on [Typed CLI errors, Connectivity & secrets](./typed-cli-errors.md#connectivity-secrets).

- Check network access to the marketplace endpoint (FLUID_MARKET_URL)
- Bundled blueprints work offline: 'fluid market --blueprints'

The suggestion names `FLUID_MARKET_URL`, which the CLI does not read as of 0.18.1. The variables that apply are in [Environment variables](./environment-variables.md#variables-with-no-effect-in-0-18-1).

### missing_blueprint_parameter

`ERR_MISSING_BLUEPRINT_PARAMETER`. The documentation link lands on [Production troubleshooting](./production-troubleshooting.md).

- The blueprint requires a parameter — pass it with --param key=value

## Signing

### signing_bundle_missing

`ERR_SIGNING_BUNDLE_MISSING`. The documentation link lands on [`fluid verify-signature`](../cli/verify-signature.md).

- Produce the bundle first ('fluid bundle &lt;contract&gt; --format tgz'), then sign it

### signing_bundle_not_file

`ERR_SIGNING_BUNDLE_NOT_FILE`. The documentation link lands on [`fluid verify-signature`](../cli/verify-signature.md).

- The signing target must be a bundle file, not a directory
- Produce one with 'fluid bundle &lt;contract&gt; --format tgz', then sign that .tgz

### signing_key_ref_empty

`ERR_SIGNING_KEY_REF_EMPTY`. The documentation link lands on [`fluid verify-signature`](../cli/verify-signature.md).

- Provide a signing key reference (e.g. a cosign key or KMS key URI)
- See the signing setup in the supply-chain docs

## Schedule sync

### schedule_sync_dags_dir_missing

`ERR_SCHEDULE_SYNC_DAGS_DIR_MISSING`. The documentation link lands on [Production troubleshooting](./production-troubleshooting.md).

- Pass --dags-dir pointing at your Airflow DAGs directory

### schedule_sync_dags_dir_not_directory

`ERR_SCHEDULE_SYNC_DAGS_DIR_NOT_DIRECTORY`. The documentation link lands on [Production troubleshooting](./production-troubleshooting.md).

- The --dags-dir value must be an existing directory
- Create it (mkdir -p) or point --dags-dir at your Airflow dags/ folder

### schedule_sync_unhandled_scheme

`ERR_SCHEDULE_SYNC_UNHANDLED_SCHEME`. The documentation link lands on [Production troubleshooting](./production-troubleshooting.md).

- Use a supported destination scheme (file / scp / git+ssh) for --to

The suggestion names a `--to` flag. `fluid schedule-sync` takes `--destination`, and its help lists `file`, `ssh`, `git+ssh`, `s3` and `gs` destinations. See [`fluid schedule-sync`](../cli/schedule-sync.md).

## Rollback

### rollback_product_id_empty

`ERR_ROLLBACK_PRODUCT_ID_EMPTY`. The documentation link lands on [Production troubleshooting](./production-troubleshooting.md).

- Pass the product id to roll back: fluid rollback &lt;product-id&gt;

## See also

- [Production troubleshooting](./production-troubleshooting.md): diagnosis and fix by event name
- [Typed CLI errors](./typed-cli-errors.md): the panel-style errors and their exit codes
- [Environment variables](./environment-variables.md): the variables the suggestions name
