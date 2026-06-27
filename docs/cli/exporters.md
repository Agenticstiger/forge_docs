# `fluid exporters`

List the spec-export formats — the open standards a FLUID contract can be serialized to.

::: tip Where this fits
`fluid exporters` ships in `0.10.0`. Exporters serialize a contract to a SPEC — they are not cloud providers (see [`fluid providers`](./providers.md) for deployment targets).
:::

## Syntax

```bash
fluid exporters [--json]
```

There are no subcommands — bare invocation lists the formats.

## Key options

| Option | Description |
| --- | --- |
| `--json` | Emit machine-readable JSON. |

## Examples

```bash
fluid exporters
fluid exporters --json
```

## Output (human)

```text
📤 FLUID spec exporters (contract → standard):

  odcs         Bitol Open Data Contract Standard v3.1.0
               https://github.com/bitol-io/open-data-contract-standard
               fluid generate standard --format odcs

  odps         LF/ODPI Open Data Product Specification v4.1
               https://github.com/Open-Data-Product-Initiative/v4.1
               fluid generate standard --format odps | opds

  odps-bitol   Bitol Open Data Product Standard v1.0.0
               https://github.com/bitol-io/open-data-product-standard
               fluid generate standard --format odps-bitol | odps-standard

Exporters serialize a contract to a SPEC — they are not cloud providers (see
`fluid providers` for deployment targets).
```

## Output (JSON)

```json
[
  {
    "name": "odcs",
    "spec": "Bitol Open Data Contract Standard v3.1.0",
    "url": "https://github.com/bitol-io/open-data-contract-standard",
    "formats": [
      "odcs"
    ]
  },
  {
    "name": "odps",
    "spec": "LF/ODPI Open Data Product Specification v4.1",
    "url": "https://github.com/Open-Data-Product-Initiative/v4.1",
    "formats": [
      "odps",
      "opds"
    ]
  },
  {
    "name": "odps-bitol",
    "spec": "Bitol Open Data Product Standard v1.0.0",
    "url": "https://github.com/bitol-io/open-data-product-standard",
    "formats": [
      "odps-bitol",
      "odps-standard"
    ]
  }
]
```

## Formats at a glance

| Format | Standard | Governed by | Invocation |
| --- | --- | --- | --- |
| `odcs` | Bitol Open Data Contract Standard v3.1.0 | [Bitol.io](https://bitol.io) | `fluid generate standard --format odcs` |
| `odps` | LF/ODPI Open Data Product Specification v4.1 | LF / Open Data Product Initiative | `fluid generate standard --format odps` (alias `opds`) |
| `odps-bitol` | Bitol Open Data Product Standard v1.0.0 | [Bitol.io](https://bitol.io) | `fluid generate standard --format odps-bitol` (alias `odps-standard`) |

## Notes

- **Exporters are not providers.** Spec-export formats serialize a contract to an open standard; they do not deploy infrastructure. That is why they have their own command — list deployment targets with [`fluid providers`](./providers.md) instead.
- **The per-format export commands are unchanged and fully supported.** See [`fluid odps`](./odps.md), [`fluid odps-bitol`](./odps-bitol.md), [`fluid odcs`](./odcs.md), [`fluid export-odps`](./export-odps.md), and [`fluid generate standard`](./generate.md#fluid-generate-standard) `--format odps|odcs|odps-bitol`.
- **Reclassified in `0.10.0`.** `odps` and `odcs` were reclassified from providers to exporters; [`fluid providers`](./providers.md) no longer lists them.
