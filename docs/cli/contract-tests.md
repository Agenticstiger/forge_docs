# `fluid contract-tests`

Run schema compatibility and consumer-impact tests against a contract.

## Syntax

```bash
fluid contract-tests CONTRACT [--env ENV] [--baseline PATH]
```

## Key options

| Option | Description |
| --- | --- |
| `CONTRACT` | Path to `contract.fluid.yaml` (positional, required). |
| `--env` | Overlay env to apply before testing. |
| `--baseline` | Baseline schema signature JSON to compare against. |

## Examples

```bash
fluid contract-tests contract.fluid.yaml
fluid contract-tests contract.fluid.yaml --env prod
fluid contract-tests contract.fluid.yaml --baseline runtime/schema-baseline.json
```

## Notes

- Returns exit code `0` when the contract is compatible, `2` when incompatibilities are found, and `1` on internal failures.
- The baseline is the schema signature you want to detect breaking changes against — typically captured from the previous release.
- Compares the contract loaded with overlays against the baseline; any incompatibility is printed as a bullet under the failure message.
- Pair with [`fluid contract-validation`](./contract-validation.md) when you also need to validate the contract against actual deployed resources.
