# `fluid contract`

Manipulate FLUID contracts — apply AI-suggested edits with provenance gating, and migrate older contracts to the schema 0.7.3 productType vocabulary.

::: tip Where this fits
`fluid contract` ships with the source-aligned acquisition stack on the `feat/source-aligned-acquisition` branch. The pinned 0.8.0 docs baseline doesn't include it yet; this page documents the surface ahead of release.
:::

## Syntax

```bash
fluid contract <subcommand> [options]
```

## Subcommands

### `fluid contract apply-suggestion`

Merge an AI suggestion file into a target contract, with per-field provenance gating. Hard-rejects AI-provenance values on safety-critical paths (anything under `metadata.classification`, `policy.*`, `sovereignty.*`).

```bash
fluid contract apply-suggestion suggestion.yaml --target contract.fluid.yaml
fluid contract apply-suggestion suggestion.yaml \
  --target contract.fluid.yaml \
  --accept-provenance ai,template \
  --out contract.next.fluid.yaml
```

| Option | Description |
|---|---|
| `<suggestion-file>` | Required. Path to a per-field provenance-annotated suggestion file. |
| `--target <path>` | Required. The contract to merge into. |
| `--accept-provenance <list>` | Comma-separated provenance tags to accept: `ai`, `introspection`, `template`, `user`. Default: all except `ai` on safety-critical paths. |
| `--out <path>` | Output path. Default: overwrite `--target` (with a one-line backup). |
| `--dry-run` | Print the merged contract without writing. |

#### How suggestions are structured

A suggestion file mirrors a contract but each value is wrapped in a provenance object:

```yaml
metadata:
  layer:
    value: Bronze
    provenance: introspection   # came from --discover schema scan
  productType:
    value: SDP
    provenance: introspection
  description:
    value: "Customer orders, full-refresh from Postgres."
    provenance: ai              # LLM-authored — gate on --accept-provenance
```

Forge (in particular `fluid init --discover` and `fluid forge --refine`) emits these suggestion shapes so a human reviewer can selectively accept changes.

### `fluid contract migrate-product-type`

Walk `**/*.fluid.yaml` under a root and fill in the missing twin of `metadata.layer` / `metadata.productType` per the canonical mapping. Preserves comments, key order, and quoting style.

```bash
# Dry-run — list what's incomplete, exit non-zero if any contracts need changes
fluid contract migrate-product-type --root . --check

# Rewrite in place
fluid contract migrate-product-type --root . --write

# Walk a different directory, skip prompts
fluid contract migrate-product-type --root ./products --write --yes
```

| Option | Description |
|---|---|
| `--root <path>` | Directory to walk. Default: current directory. |
| `--check` | Dry-run mode. Exit non-zero if any contracts are still incomplete. |
| `--write` | Rewrite files in place (default behavior is dry-run-only output). |
| `--yes` | Skip the interactive confirmation. |
| `--json` | Emit a structured summary. |

#### Equivalence axiom

The migrator applies this canonical mapping (same one the runtime validator uses):

| Set on contract | Filled in |
|---|---|
| `layer: Bronze` | `productType: SDP` |
| `layer: Silver` | `productType: ADP` |
| `layer: Gold` | `productType: CDP` |
| `productType: SDP` | `layer: Bronze` |
| `productType: ADP` | `layer: Silver` |
| `productType: CDP` | `layer: Gold` |
| `layer: Platinum` | (no productType — Platinum is medallion-only) |

If both fields are already set and disagree, the migrator emits an error and exits non-zero — that's a contract bug to fix by hand, not a normalization the migrator will silently overwrite.

#### Output (JSON)

```json
{
  "scanned": 47,
  "alreadyComplete": 32,
  "filled": 14,
  "inconsistent": 1,
  "errors": [
    { "path": "products/orders.fluid.yaml", "issue": "layer=Bronze but productType=ADP — pick one and re-run" }
  ]
}
```

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Subcommand succeeded |
| `1` | User error (missing args, invalid file, inconsistent contract) |
| `2` | Some contracts had warnings (in `--check` mode, this is the "still incomplete" signal CI watches for) |

## See also

- [Product Types — SDP, ADP, CDP](/forge_docs/data-products/product-type.html) — the vocabulary the migrator normalizes
- [`fluid forge --refine`](/forge_docs/cli/forge.html) — produces suggestion files via AI-aided refinement
- [`fluid validate`](/forge_docs/cli/validate.html) — what catches inconsistent contracts the migrator refused to fix
