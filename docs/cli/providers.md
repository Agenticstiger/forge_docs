# `fluid providers`

List the infrastructure providers this install has registered: the deployment targets `--provider` and the contract's `binding.platform` can resolve to.

## Syntax

```bash
fluid providers [--debug]
```

## Key options

| Option | Description |
| --- | --- |
| `--debug` | Print discovery metadata for each provider: where it was registered from, its module, and the metadata it declares (display name, version, supported platforms, tags). |

## Example

```bash
fluid providers
```

```json
{
  "providers": [
    "aws",
    "datamesh_manager",
    "gcp",
    "local",
    "redshift",
    "snowflake"
  ]
}
```

The output is already JSON; `fluid providers --json` is not a flag.

With `--debug`, each name becomes an object. This is the first entry, trimmed:

```json
{
  "providers": [
    {
      "name": "aws",
      "source": "explicit",
      "module": "fluid_build.providers.aws.provider",
      "info": {
        "name": "aws",
        "display_name": "Amazon Web Services",
        "supported_platforms": ["aws", "s3", "redshift", "athena", "glue"],
        "tags": ["aws", "cloud", "s3", "glue", "athena", "redshift"],
        ...
      }
    },
    ...
  ]
}
```

`source` is `explicit` for providers the CLI registers itself and `entrypoint` for providers discovered through the `fluid_build.providers` entry-point group. In the 0.18.1 install used for this page `snowflake` was the one reported as `entrypoint`. `--debug` also writes discovery log lines to the terminal before the JSON.

## When a provider cannot be found

A command reaches a provider by one of two routes, and each fails with its own message.

**1. You name it: `--provider` or `FLUID_PROVIDER`.** The flag is global, so it goes before the subcommand (`fluid --provider gcp ...`) or in the environment. The value is checked against the list above before the command runs. Anything else exits 2:

```text
⚠️ Unknown provider 'nope' — installed providers: aws, datamesh_manager, gcp, local, redshift, snowflake (see `fluid providers`)
```

This check carries no `ERR_` code. A subcommand that also declares its own `--provider` (for example `fluid export`) is checked the same way after parsing. `--provider gcp` additionally prints `Provider 'gcp' requires --project to be specified` unless the global `--project` (or `FLUID_PROJECT`) is set; the line is a warning, and the command carries on.

**2. The contract names it.** Without a flag, `apply` and `plan` read the platform from the contract: the first `exposes[].binding.platform`, then a top-level `binding.platform`, then `builds[].execution.runtime.platform`. They print the result as `Detected provider: local`. `fluid policy apply` reads `provider` from the compiled bindings file instead. If that name is not registered, or no provider can be determined, the command fails with one of the codes below. Every one prints a link to this page.

<a id="err-provider-unknown"></a>

### `ERR_PROVIDER_UNKNOWN`, exit 2

The contract (or bindings file) names a provider that is not registered. Here `binding.platform: azure` in a quickstart contract:

```text
❌ provider_unknown  [ERR_PROVIDER_UNKNOWN]
  requested: azure
  available: ['aws', 'datamesh_manager', 'gcp', 'local', 'redshift',
'snowflake']

💡 Suggestions:
  • Run 'fluid providers' to see the available providers
  • Valid built-ins: local, gcp, snowflake, aws, azure
```

Fix: use a name from `available`, or install a package that registers the provider. As of 0.18.1 the second suggestion is wrong about `azure`: it is not registered, so it is not a valid built-in. See [Known gaps](#known-gaps).

<a id="err-provider-not-specified"></a>

### `ERR_PROVIDER_NOT_SPECIFIED`, exit 2

No provider was passed, none is in the environment, and none could be read from the file. Reproduced with a bindings file whose bindings carry no `provider`:

```bash
fluid policy apply bindings.json --mode enforce
```

```text
❌ provider_not_specified  [ERR_PROVIDER_NOT_SPECIFIED]

💡 Suggestions:
  • Pass a provider: --provider local|gcp|snowflake|aws|azure
  • Or set the FLUID_PROVIDER environment variable
  • Run 'fluid providers' to list the available providers
```

Fix: `fluid --provider <name> policy apply ...`, or `export FLUID_PROVIDER=<name>`.

<a id="err-provider-not-found"></a>

### `ERR_PROVIDER_NOT_FOUND`, exit 1

Raised when an action in an execution plan names a provider that is missing from the running registry. The suggestions are to check the spelling and to install the provider's extra, for example:

```bash
pip install 'data-product-forge[gcp]'
```

The package defines `local`, `gcp`, `snowflake` and `aws` extras.

<a id="err-provider-blocked-by-policy"></a>

### `ERR_PROVIDER_BLOCKED_BY_POLICY`, exit 2

The provider is installed, and an operator policy removed it. `FLUID_PLUGINS_BLOCKLIST` names it, or `FLUID_PLUGINS_ALLOWLIST` is set and does not. Reproduced with the quickstart contract (`binding.platform: local`):

```bash
FLUID_PLUGINS_BLOCKLIST=local fluid apply contract.fluid.yaml --yes
```

```text
Detected provider: local, project: gold.customer.analytics_360_v1
❌ provider_blocked_by_policy  [ERR_PROVIDER_BLOCKED_BY_POLICY]
  requested: local
```

`fluid plugins --role provider` shows the effective policy:

```text
  provider  (4)
    • aws                          allowed
      from=data-product-forge 0.18.1
    ...
    • local                        BLOCKED (allow/block policy)
      from=data-product-forge 0.18.1
```

Fix: unset or amend the variable. See [`fluid plugins`](./plugins.md#operator-governance).

If the same blocked name arrives through `--provider local`, the global check reports `Unknown provider 'local'` instead, because a blocked provider is already absent from the registry that check reads.

<a id="err-reserved-provider-name"></a>

### `ERR_RESERVED_PROVIDER_NAME`, exit 1

Raised by [`fluid provider-init`](./provider-init.md) when the name you chose belongs to a built-in:

```text
❌ reserved_provider_name  [ERR_RESERVED_PROVIDER_NAME]
  name: aws
```

Fix: choose another name. The reserved names are listed on the `provider-init` page.

## Known gaps

As of 0.18.1:

- `azure` appears in the `--provider` choices of `fluid export` and in the `ERR_PROVIDER_*` suggestions, and `fluid init` and `fluid import` accept `--provider azure` at parse time, but no Azure provider is registered. `fluid --provider azure ...`, `fluid export --provider azure`, `fluid init --provider azure` and `fluid import dbt --provider azure` all exit 2 with `Unknown provider 'azure'`.
- `confluent` is accepted by `fluid generate iac --provider`, and `databricks` is listed for `fluid contract-validation --provider`. Neither is registered either, so the same global check rejects them with exit 2.

## Notes

- These are deployment targets: providers that `fluid apply` can provision infrastructure against.
- `datamesh_manager` and `redshift` are registered here and are not in the `provider` role that [`fluid plugins`](./plugins.md) lists. That role holds the providers discovered through entry points, and `fluid providers` holds the larger registry.
- Spec-export formats (ODCS, ODPS, ODPS-Bitol) are **not** providers; they do not deploy infrastructure. List them with [`fluid exporters`](./exporters.md) instead.
- See the [provider guides](/forge_docs/providers/) for target-specific documentation.
