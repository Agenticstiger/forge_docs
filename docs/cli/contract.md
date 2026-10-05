# `fluid contract`

Work on a contract file: compute the digest that downstream products pin, merge reviewed field suggestions into a contract, and fill in the missing `layer` / `productType` twin.

## Syntax

```bash
fluid contract <subcommand> [options]
```

| Subcommand | What it does | Since |
| --- | --- | --- |
| [`digest`](#fluid-contract-digest) | Print the canonical `sha256` of a contract, the value `consumes[].upstreamDigest` pins. | 0.16.0 |
| [`apply-suggestion`](#fluid-contract-apply-suggestion) | Merge a suggestion file into a contract, with per-field provenance gating. | 0.8.3 |
| [`migrate-product-type`](#fluid-contract-migrate-product-type) | Fill the missing twin of `metadata.layer` / `metadata.productType`. | 0.8.3 |

## Subcommands

### `fluid contract digest`

Print the canonical digest of a contract. A downstream product that federates with this one pins the value in `consumes[].upstreamDigest`, and `fluid apply` checks the pin before it applies.

```bash
fluid contract digest contract.fluid.yaml
```

```text
sha256:c1e5698c3a6e632e0cd1933209da2c3eac339e55dd098264ae08baf2cb277255
```

Pin it in the consuming contract. `upstreamWorkspace` (the id of a federated workspace declared in `federation/upstreams.yaml`) and `upstreamDigest` exist from `fluidVersion: 0.7.6`, a preview version you opt into, and the schema requires `upstreamDigest` whenever `upstreamWorkspace` is set:

```yaml
fluidVersion: "0.7.6"
consumes:
  - productId: gold.customer.analytics_360_v1
    exposeId: customer_360_master
    upstreamWorkspace: <workspace-id>
    upstreamDigest: sha256:c1e5698c3a6e632e0cd1933209da2c3eac339e55dd098264ae08baf2cb277255
```

| Option | Description |
| --- | --- |
| `<contract>` | Required. Path to the contract YAML or JSON. |
| `--json` | Print `{"digest": ..., "path": ...}` instead of the bare digest. |

```bash
fluid contract digest contract.fluid.yaml --json
```

```text
{"digest": "sha256:c1e5698c3a6e632e0cd1933209da2c3eac339e55dd098264ae08baf2cb277255", "path": "contract.fluid.yaml"}
```

The digest is computed over the parsed contract, not the file text, with the same function the federation check in `fluid apply` uses. Reformatting the file (key order, indentation, quoting, comments, line endings) does not change it. Adding a column does.

On a contract with no `$ref` entries you can reproduce the hex digits after `sha256:` outside the CLI: convert the YAML to JSON, then `jq -cSj '.' | shasum -a 256`. With `yq` installed, that is `yq -o=json '.' contract.fluid.yaml | jq -cSj '.' | shasum -a 256`.

::: warning The digest ignores fragments
`fluid contract digest` parses the file you give it and does not resolve `$ref`. For a fragment-layout contract (see [`fluid split`](./split.md)) it hashes the `$ref` strings, not the fragments. The federation check in `fluid apply` also reads only the upstream's root file. As of 0.18.1, changing a column type from `INTEGER` to `BIGINT` inside `fragments/exposes/customer_360_master.yaml` left the root's digest at `sha256:60ff973a...`, while the bundled contract's digest changed to `sha256:bd8943b1...`.

A downstream pin therefore cannot see schema changes made in an upstream's fragments. A fragment-layout contract and the flat contract with the same content also have different digests. For a product other teams pin, publish a bundled file and take its digest:

```bash
fluid bundle contract.fluid.yaml --out bundled.fluid.yaml
fluid contract digest bundled.fluid.yaml
```

`fluid bundle` writes the resolved contract. Write it inside the contract's directory: `--out ../bundled.fluid.yaml` is refused because the path contains `..`.
:::

Errors:

| Event | Cause |
| --- | --- |
| `digest_contract_not_found` | The path is not a file. |
| `digest_contract_empty` | The file is empty or holds only comments. The command refuses rather than print the digest of `{}`. |
| `digest_contract_not_a_mapping` | The file parses to something other than a mapping. |
| `digest_contract_unsafe` | The file exceeds the safe-YAML limits (size, alias expansion). |
| `digest_contract_unreadable` | The file does not parse. |

All of them exit with code `1`.

### `fluid contract apply-suggestion`

Merge a suggestion file into a target contract. Each field in the file names its provenance (`ai`, `introspection`, `template` or `user`). A field with `ai` provenance that lands on a safety-critical path is rejected, and you can accept only the provenance kinds you trust.

```bash
fluid contract apply-suggestion contract.suggested.json \
  --target contract.fluid.yaml \
  --accept-provenance ai user \
  --out contract.next.fluid.yaml
```

The suggestion file is JSON. YAML is not read.

```json
{
  "contract_id": "gold.customer.analytics_360_v1",
  "fields": [
    {
      "path": "description",
      "value": "Customer 360 for the CRM team.",
      "provenance": "ai",
      "rationale": "Drafted from the column names"
    },
    {
      "path": "metadata.owner.team",
      "value": "crm-analytics",
      "provenance": "user"
    },
    {
      "path": "exposes[0].contract.schema[0].description",
      "value": "Stable customer key",
      "provenance": "introspection"
    }
  ]
}
```

`path` is dotted, with `[i]` for a list index (`builds[0].properties.source.streams[1]`). A missing path is created. `provenance` defaults to `ai`; `rationale` is a one-line note for the reviewer.

| Option | Description |
| --- | --- |
| `<suggestion-file>` | Required. Path to the suggestion JSON. |
| `--target <path>` | Required. The contract to merge into, YAML or JSON. |
| `--accept-provenance <list>` | Space-separated provenance kinds to apply: `ai`, `introspection`, `template`, `user`. Default: all. |
| `--out <path>` | Write here instead of overwriting `--target`. |

Without `--out`, the command overwrites `--target` after copying it to `<target>.bak` (`contract.fluid.yaml.bak`). A YAML target is rewritten with `yaml.safe_dump`, which drops comments; key order is kept. In the run above, the two header comment lines of the contract were gone from `contract.next.fluid.yaml`.

#### Paths an `ai` field cannot touch

An `ai` field on any of these paths fails the whole merge with `ai_guardrail_violation` and exit code `1`, and nothing is written:

- `builds[].properties.source.connection`, including `secretRef`
- `builds[].properties.airbyte.deployment.auth`, including `secretRef`
- `exposes[].contract.schema`
- `sovereignty`
- `builds[].properties.airbyte.image_signature`, `builds[].properties.debezium.image_signature` and `builds[].properties.kafka-connect.image_signature`
- `builds[].properties.cost.budget`

```text
AI-mode guardrail violations:
  sovereignty.jurisdiction: AI provenance is not allowed on safety-critical fields (connection details, secrets, sovereignty, image signatures, cost budgets). Source this from introspection or a human-authored template.
```

The check is on the field's declared provenance. The same path with `introspection`, `template` or `user` provenance is applied. `metadata.classification` and `policy.*` are not on the list, so an `ai` field can change them; review those in the diff.

The guardrail check runs on every field in the file before `--accept-provenance` filters anything, so an `ai` field on a blocked path fails the merge even if you accept only `user`. The closing `Merged N field(s)` line counts every field in the file, including the ones the filter skipped.

No `fluid` command writes suggestion files in 0.18.1: `fluid init --discover` and `fluid forge --refine` do not produce them. The file is yours to write, or a tool's.

### `fluid contract migrate-product-type`

Walk `**/*.fluid.yaml` under a root and fill in the missing twin of `metadata.layer` / `metadata.productType`.

```bash
# Dry run: list what is incomplete, exit 1 if any contract needs changes
fluid contract migrate-product-type --root . --check

# Rewrite in place
fluid contract migrate-product-type --root . --write

# Walk a different directory, skip the prompt
fluid contract migrate-product-type --root ./products --write --yes
```

```text
  ✏️  .../a/x.fluid.yaml: would write layer=Bronze productType=SDP (was layer=Bronze productType=<unset>)
Scanned 1 contract(s) under .../a: 1 would be rewritten, 0 already complete, 0 still missing both twins.
❌ 1 contract(s) need migration; re-run with --write to apply or fix metadata by hand.
```

| Option | Description |
| --- | --- |
| `--root <path>` | Directory to walk. Default: the current directory. Skips `.git`, `__pycache__`, `node_modules`, `.venv` and `venv`. |
| `--check` | Exit `1` if any contract still needs migration or has neither field. |
| `--write` | Rewrite files in place. Without it the command is a dry run. |
| `-y`, `--yes` | Skip the confirmation before `--write` rewrites files. Required without a terminal; ignored without `--write`. |

`--write` re-serialises each changed file with `yaml.safe_dump`: key order is kept, but comments and quoting are dropped. A file with `# keep me` as its first line lost it in the run above. Commit before you run it, and review the diff.

#### Equivalence axiom

| Set on contract | Filled in |
| --- | --- |
| `layer: Bronze` | `productType: SDP` |
| `layer: Silver` | `productType: ADP` |
| `layer: Gold` | `productType: CDP` |
| `productType: SDP` | `layer: Bronze` |
| `productType: ADP` | `layer: Silver` |
| `productType: CDP` | `layer: Gold` |
| `layer: Platinum` | (no productType; Platinum is medallion-only) |

A contract with neither field set is counted as "still missing both twins" and left alone.

::: warning Conflicting twins crash the command
If both fields are set and disagree (`layer: Bronze` with `productType: CDP`), the command should name the contract. As of 0.18.1 it stops with `Unexpected error: metadata.layer='Bronze' and metadata.productType='CDP' are inconsistent`, `CLI unhandled exception` and exit code `2`, and it does not say which file. Fix the contract by hand; [`fluid validate`](./validate.md) reports the conflict per file.
:::

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | The subcommand succeeded. |
| `1` | User error (missing file, bad suggestion, guardrail violation, empty contract), or `migrate-product-type --check` found contracts that need migration. |
| `2` | `migrate-product-type` met a contract whose `layer` and `productType` disagree (an unhandled exception), or an argument error. |

## See also

- [Product Types — SDP, ADP, CDP](/forge_docs/data-products/product-type.html) — the vocabulary the migrator normalizes
- [`fluid split`](./split.md) and [`fluid bundle`](./bundle.md) — convert between a flat contract and a fragment layout; [Contract fragments](../concepts/fragments.md#digests) explains why the digest of a fragment root does not move
- [Federated upstreams](../concepts/federation.md#the-pin) — where `upstreamDigest` is pinned and checked
- [`fluid apply`](./apply.md) — checks `upstreamDigest` pins before it applies
- [`fluid validate`](./validate.md) — reports inconsistent contracts the migrator cannot fix
