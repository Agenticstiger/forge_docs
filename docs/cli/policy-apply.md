# `fluid policy apply`

Stage 8 of the 11-stage pipeline. Reads the compiled bindings file from [`fluid policy compile`](./policy-compile.md) and hands it to the contract's provider.

::: warning As of 0.18.1 this stage changes no cloud permissions
In 0.18.1 `fluid policy apply` does not create IAM bindings, GRANTs or policies on the providers this page lists. The GCP provider reports the compiled bindings and applies none. Every other provider has no policy applier, so the command prints a warning and exits `0`. Access resources reach the cloud through [`fluid apply`](./apply.md), which provisions them with OpenTofu. See [What each provider does](#what-each-provider-does).
:::

The unified `fluid policy {check,compile,apply}` group was added in `0.8.0`. The older `fluid policy-apply` form is still registered in 0.18.1 and behaves the same; it prints no deprecation notice.

## Syntax

```bash
fluid policy apply BINDINGS [--mode {check,enforce}]

# Older form, same behaviour
fluid policy-apply BINDINGS [--mode {check,enforce}]
```

## Key options

| Option | Description |
| --- | --- |
| `BINDINGS` | Path to compiled bindings file, typically `runtime/policy/bindings.json` (positional, required). |
| `--mode` | `check` (default) or `enforce`. In 0.18.1 neither mode mutates a provider (see below), so the value only changes the `mode` the provider reports. |

The provider is not a flag of this command. Set it before the subcommand (`fluid --provider gcp policy apply ...`) or with `FLUID_PROVIDER`.

## What each provider does

| Provider named in the bindings | What `fluid policy apply` does |
| --- | --- |
| `gcp` | Reports the compiled bindings and returns `status: ok` with `applied: 0`, in both modes. The provider's own message says GCP IAM is provisioned declaratively by `fluid apply` from the contract, and that this stage does not mutate IAM through the Google SDK. |
| `aws`, `snowflake`, `local`, and any other provider without an applier | Prints `No policy bindings were enforced` and says the provider has no standalone policy applier. Exit `0`. |
| any provider, `bindings` empty | Succeeds without resolving a provider. A contract with no `accessPolicy` grants compiles to zero bindings. |

For the cloud providers the grants, masking and row-access policies come from `fluid apply` (stage 7). For GCP that includes the column-level policy tags that `policy.authz.columnRestrictions` produces; `fluid policy compile` does not model them, so they never appear in `bindings.json`.

The AWS case, measured against 0.18.1 with the bindings file from [`fluid policy compile`](./policy-compile.md):

```text
⚠️  No policy bindings were enforced — the 'aws' provider has no standalone
policy applier. For cloud providers, IAM/GRANT, masking and row-access policies
are emitted and applied during `fluid apply` (stage 7), so `fluid policy-apply`
is a no-op for this provider.
```

::: tip Constructing a cloud provider can call the cloud
`fluid policy apply` builds the provider named in the bindings before it knows the provider has nothing to apply. With an AWS bindings file on a machine that had AWS credentials, the log line `provider_initialized` carried the caller's account id, so the AWS SDK had made an identity call. Run it where that is acceptable, or leave this stage out of a pipeline whose providers have no applier.
:::

## Pipeline ordering

Stage 8 runs **after** stage 7 apply and **before** stage 9 verify. The Jenkins and 7-system CI templates from `fluid generate ci` wire it in. The stage is self-gated on `dist/artifacts/policy/bindings.json` existing, so contracts that do not emit policy bindings skip it.

## Examples

### Report the compiled bindings

```bash
fluid policy apply runtime/policy/bindings.json
# exit 0 when the provider returns ok or noop; exit 1 for any other status
```

### Pass the provider explicitly

```bash
fluid --provider gcp policy apply runtime/policy/bindings.json --mode enforce
```

### Older hyphenated form

```bash
fluid policy-apply runtime/policy/bindings.json --mode enforce
# same as: fluid policy apply runtime/policy/bindings.json --mode enforce
```

## Errors

| Code | When | Exit |
| --- | --- | --- |
| [`ERR_PROVIDER_NOT_SPECIFIED`](./providers.md#err-provider-not-specified) | The bindings carry a binding with no `provider`, and neither `--provider` nor `FLUID_PROVIDER` is set. | 2 |
| [`ERR_PROVIDER_UNKNOWN`](./providers.md#err-provider-unknown) | The bindings name a provider that is not registered. | 2 |
| `ERR_POLICY_APPLY_FAILED` | The file is not valid JSON, or the provider raised. Passing a contract instead of a bindings file ends here. | 1 |

## Notes

- Provider and project are read from the first binding that sets them. `fluid policy compile` writes both from the contract's `binding.platform` and `binding.location`. A provider given by flag or environment overrides the file's.
- Returns `0` for `ok` or `noop` results, `1` otherwise.
- Compile bindings first with [`fluid policy compile`](./policy-compile.md); see [`fluid policy check`](./policy-check.md) for static linting of the access policy.
- Both spellings share one argument set. Prefer `fluid policy apply` in new code; the hyphenated form is still registered in 0.18.1.
