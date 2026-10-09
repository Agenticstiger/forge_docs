# `fluid policy compile`

Compile a contract's `accessPolicy` into provider-specific IAM / GRANT bindings. Pure-function shape: contract in, JSON out. No cloud calls.

`0.8.0` added the unified `fluid policy {check,compile,apply}` subcommand group. The older `fluid policy-compile` form is still registered in 0.18.1, prints no deprecation notice, and takes the same arguments.

This command runs as part of stage 3 (`fluid generate artifacts`) but is also available standalone.

## Syntax

```bash
# New idiomatic form
fluid policy compile CONTRACT [--env ENV] [--out PATH]

# Older form (same behaviour)
fluid policy-compile CONTRACT [--env ENV] [--out PATH]
```

## Key options

| Option | Description |
| --- | --- |
| `CONTRACT` | Path to `contract.fluid.yaml` (positional, required). |
| `--env` | Overlay env to apply before compiling. |
| `--out` | Output bindings path (default `runtime/policy/bindings.json`). |

## Examples

```bash
# New idiomatic form
fluid policy compile contract.fluid.yaml
fluid policy compile contract.fluid.yaml --env prod
fluid policy compile contract.fluid.yaml --out build/bindings.json

# Hyphenated form (still registered)
fluid policy-compile contract.fluid.yaml --env prod
```

## Warnings

*([forge-cli #710](https://github.com/Agenticstiger/forge-cli/pull/710), unreleased)* Each compiler warning goes into the `warnings` array of the output file, and each one other than `No grants found in accessPolicy` is also printed to stderr, as a `policy_compile_warning` log line at WARNING level. Warnings leave the exit code at `0`. A warning can be the only sign that a grant compiled to no binding. A `read` grant on an AWS Iceberg expose that Lakekeeper catalogs compiles to the S3 bucket binding only, and prints:

```bash
fluid policy compile contract.fluid.yaml
```

```text
{"time": "...", "level": "WARNING", "name": "fluid.cli", "message": "policy_compile_warning", "warning": "Iceberg expose 'orders' is cataloged in 'lakekeeper', not AWS Glue, so no table grant was compiled for group:analysts@acme.com ['read']. Enforce it in the 'lakekeeper' catalog's own access control.", "out": "runtime/policy/bindings.json"}
```

A contract with no `accessPolicy` grants gets `No grants found in accessPolicy` in the file only: no grant is left unenforced. [`fluid policy apply`](./policy-apply.md#notes) prints the file's warnings again. Before #710 the warnings were written only to the file.

## Errors

| Code | When | Exit |
| --- | --- | --- |
| `ERR_POLICY_COMPILER_CRASHED` | *([forge-cli #710](https://github.com/Agenticstiger/forge-cli/pull/710), unreleased)* The policy compiler raised an exception. No bindings file is written; one from an earlier run is left as it was. | 1 |
| `ERR_POLICY_COMPILE_FAILED` | The command failed outside the compiler, for example because the contract or overlay is missing or does not parse, or the bindings file cannot be written. | 1 |

`policy compile` does not validate the contract against its schema, so a value of the wrong type where the compiler reads (`accessPolicy`, its `grants`, a grant's `permissions`, an expose's `binding` and `binding.location`) reaches the compiler. When it crashes there, the error names each such value by path and expected type, never by its content. A grant written as a bare string:

```yaml
accessPolicy:
  grants:
    - group:analysts@acme.com
```

```text
❌ policy_compiler_crashed  [ERR_POLICY_COMPILER_CRASHED]
  error: policy compile failed on contract values of the wrong type: accessPolicy.grants[0] is not of type 'object'

💡 Suggestions:
  • Run 'fluid validate <contract>': policy compile reads accessPolicy and exposes without validating them against the contract schema
  • If the contract validates, re-run with 'fluid --log-level DEBUG policy compile <contract>' to see the compiler's traceback

📖 Documentation: https://agenticstiger.github.io/forge_docs/cli/policy-compile.html#errors
```

When the schema finds no such error, the message is the compiler's own exception: `policy compiler failed: <exception type>: <message>`. The policy step of [`fluid generate artifacts`](./generate-artifacts.md) fails with the same error. Before #710 a crash wrote a bindings file with no bindings and the crash as a warning, and exited `0`, so the next stage read it as no grants to enforce.

## Notes

- Loads the contract with the requested env overlay and emits a JSON document with `bindings` and `warnings` arrays at the `--out` path.
- The compiler embeds `provider` and `project` on each binding so [`fluid policy apply`](./policy-apply.md) can target the right account without extra flags.
- Pair with [`fluid policy check`](./policy-check.md) for static linting and [`fluid policy apply`](./policy-apply.md) for the stage-8 hand-off to the provider (it changes no permissions in 0.18.1).
