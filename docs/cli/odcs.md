# `fluid odcs`

Convert between FLUID contracts and the Open Data Contract Standard (ODCS) v3.1.0 from Bitol.io, in either direction.

## Syntax

```bash
fluid odcs export CONTRACT [--output PATH] [--format FMT] [--no-quality] [--no-sla]
fluid odcs import ODCS_FILE [--output PATH] [--format FMT]
fluid odcs validate ODCS_FILE [--report PATH] [--roundtrip] [--no-vowl]
fluid odcs info
```

## Key options

### `odcs export`

| Option | Description |
| --- | --- |
| `CONTRACT` | Path to FLUID contract file. |
| `--output`, `-o` | Output file path. Default: the contract file's name without its last extension, plus `-odcs` and the format. `contract.fluid.yaml` writes `contract.fluid-odcs.yaml`. |
| `--format`, `-f` | Output format: `yaml` or `json`. Default `yaml`. |
| `--no-quality` | Exclude quality checks from the output. |
| `--no-sla` | Exclude SLA properties from the output. |

### `odcs import`

| Option | Description |
| --- | --- |
| `ODCS_FILE` | Path to ODCS contract file. |
| `--output`, `-o` | Output file path. Default: the input file's name without its last extension, plus `-fluid` and the format. `contract.fluid-odcs.yaml` writes `contract.fluid-odcs-fluid.yaml`. |
| `--format`, `-f` | Output format: `yaml` or `json`. Default `yaml`. |

### `odcs validate`

| Option | Description |
| --- | --- |
| `ODCS_FILE` | Path to an ODCS file to validate against the v3.1.0 JSON schema. |
| `--report PATH` | Write a structured JSON validation report to this path (for CI gates). *(since 0.21.0, [forge-cli #725](https://github.com/Agenticstiger/forge-cli/pull/725))* A file that is not valid YAML, or that the [YAML limits](./validate.md#yaml-limits) refuse, is reported too, as a failed `parse` pass. |
| `--roundtrip` | Also verify the contract round-trips losslessly through `OdcsProvider.import_contract` → `render` and report any diff. Requires `deepdiff`, which ships only in the `dev` extra — without it the pass reports `ModuleNotFoundError`. |
| `--no-vowl` | Skip the vowl second-pass even if installed. |

### `odcs info`

No options. Prints exporter info (version, spec URL, schema status).

## Examples

```bash
fluid odcs export contract.fluid.yaml
fluid odcs export contract.fluid.yaml -o contract.json -f json --no-sla
fluid odcs import third-party-contract.yaml -o my-contract.fluid.yaml
fluid odcs validate contract.odcs.yaml
```

## Quality rules in the export

*On forge-cli `main`, not yet in a release ([forge-cli #910](https://github.com/Agenticstiger/forge-cli/pull/910)).* A FLUID `dq.rules` threshold is the share of rows that **pass**. ODCS `nullValues`, `duplicateValues` and `invalidValues` count the rows that **fail**. Up to 0.30.1 the exporter copied the threshold across, so `threshold: 1.0` with `operator: ">="` came out as "at least one null". Every ODCS export is affected, among them the contracts [`fluid publish --target datamesh-manager`](./publish.md) sends. The export now mirrors the share:

| `dq.rules` rule | Exported as |
| --- | --- |
| `completeness`, threshold 1.0 | `nullValues` with `mustBe: 0` |
| `completeness`, a partial share, as in `>= 0.95` | The null share, as a percentage: `nullValues` with `mustBeLessOrEqualTo: 5` and `unit: percent` |
| `uniqueness`, threshold 1.0 | `duplicateValues` with `mustBe: 0` |
| `uniqueness`, a partial share | Not exported, with a warning: no ODCS metric equals a share of distinct values over the non-null ones |
| `valid_values`, any threshold | `invalidValues` with `mustBe: 0`, as `fluid test` checks it |
| `freshness` | A `text` rule, as before |

A threshold with no `operator` reads as `>=`, as `fluid test` reads it. A threshold that is not a number from 0 to 1 is not exported. The SodaCL exporter already worked this way.

*On forge-cli `main`, not yet in a release ([forge-cli #921](https://github.com/Agenticstiger/forge-cli/pull/921)).* **A rule lands on the columns it checks.** Up to 0.30.1 a completeness rule on `"a, b"`, or with no selector, was exported as an object-level `nullValues` check that named no column. Now:

- `completeness` and `valid_values` give one check for each listed column, matched in any case;
- `uniqueness` gives one check, for one column;
- a rule that selects no column, or a column the schema does not declare, or (for `uniqueness`) several columns, is **not exported**. The export logs a warning that names the rule and the reason, and the rule is still carried verbatim under `customProperties.fluidExtras`.
- A document that was exported before and imported again no longer doubles the rule.

Seen on forge-cli `main`, for a contract with `completeness` rules on `order_id` (threshold 1.0), on `email` (`>= 0.95`, severity `warn`) and on the selector `"order_id, email"`, a `uniqueness` rule at `>= 0.99`, and a rule on a column the schema lacks. The `email` property gets:

```yaml
- id: email_mostly
  description: completeness check on email
  dimension: completeness
  severity: warning
  type: library
  unit: percent
  metric: nullValues
  mustBeLessOrEqualTo: 5
```

and the two rules the export cannot express are named:

```text
dq rule 'id_unique' (type 'uniqueness') on expose 'orders' has no ODCS v3.1.0 quality form: its threshold >= 0.99 is a partial uniqueness share (distinct over non-null values), which no ODCS duplicateValues count or percent equals; only full uniqueness (threshold 1.0 with >= or ==) is expressible. It is NOT exported as ODCS quality; it rides along verbatim under customProperties.fluidExtras so nothing is lost. ...
dq rule 'ghost' (type 'completeness') on expose 'orders' has no ODCS v3.1.0 quality form: it selects 'nosuchcol', which the expose's schema does not declare. It is NOT exported as ODCS quality; it rides along verbatim under customProperties.fluidExtras so nothing is lost. ...
```

A consumer that read the old export, such as a data quality engine or a catalog that seeds assertions from `quality`, sees thresholds that mean the opposite of what it saw. Re-export and re-publish.

## Notes

- ODCS is bidirectional: `export` goes FLUID -> ODCS, `import` goes ODCS -> FLUID. The underlying exporter was modularised under `providers/odcs/` in `v0.8.3` with paired `to_fluid()` / `to_odcs()` mappers and per-level `odcs_passthrough` buckets for lossless round-trip. As of `0.10.0`, ODCS is a spec exporter (surfaced by [`fluid exporters`](./exporters.md)), not a registered cloud provider — it is not listed by [`fluid providers`](./providers.md).
- Validation uses the bundled ODCS v3.1.0 JSON Schema from Bitol.io. Validation runs by default on every export (`ODCS_VALIDATE=true`); failures warn rather than raise. Hard-fail via `ODCS_VALIDATE_STRICT=true`. *(since 0.15.0)* That schema is now validated with the 2019-09 dialect it declares rather than with Draft 7, which **ignored** the nine `unevaluatedProperties: false` guards it carries — so an export that validated clean on `0.14.1` may now warn. Same change, same cause, as [`fluid validate-artifacts` → Schema dialect](./validate-artifacts.md#schema-dialect-since-0-15-0).
- **`description` field mapping.** ODCS models `description` as an object of string fields (`purpose`, `limitations`, `usage`); FLUID models it as a single string, so converting needs a type check in both directions. *(since 0.15.0)* The exporter mirrors the importer: a mapping passes through as siblings under `description`, a string is still wrapped as `{purpose: <string>}`, and an empty mapping emits no `description` key at all. Previously the exporter wrapped **unconditionally**, so a mapping came out as `description.purpose: {purpose: …, limitations: …, usage: …}` — an object where the schema declares a string, i.e. invalid ODCS written with only a warning (or, on installs carrying the optional `vowl` validator via `data-product-forge[odcs-strict]`, an aborted `fluid generate artifacts` that wrote no artifacts at all). Round-trips never saw it, because the import path stashes the original object in metadata passthrough and the exporter reads it back; only a caller rendering a document it had not imported reached the broken branch. The old shape was already schema-invalid, so only a consumer written against the bug breaks.
- *(since 0.21.0, [forge-cli #725](https://github.com/Agenticstiger/forge-cli/pull/725))* `validate` and `import` read YAML through the same [limits](./validate.md#yaml-limits) as FLUID contracts, and report a file they refuse, or one that is not valid YAML, as a failed validation or import with exit 1. A `.YAML` or `.YML` suffix in upper case is read as YAML.
- The unified [`fluid odps`](./odps-bitol.md#unified-fluid-odps-since-v0-8-3) command also accepts a lone ODCS file under `fluid odps import` — useful when you want one entry point for both spec families.
- For Bitol.io's data-product variant (ODPS-Bitol), use [`fluid odps-bitol`](./odps-bitol.md). For the official ODPS (Open Data Product Initiative), use [`fluid odps`](./odps.md).
- To publish ODCS contracts to Entropy Data alongside a data product, see [`fluid datamesh-manager publish --with-contract`](./datamesh-manager.md).
