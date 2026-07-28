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

  odps         Bitol Open Data Product Standard v1.0.0
               https://github.com/bitol-io/open-data-product-standard
               fluid generate standard --format odps | odps-bitol

  odps-v4.1    LF/ODPI Open Data Product Specification v4.1
               https://github.com/Open-Data-Product-Initiative/v4.1
               fluid generate standard --format odps-v4.1
               deprecated alias(es): opds — prefer --format odps-v4.1

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
    ],
    "deprecatedFormats": []
  },
  {
    "name": "odps",
    "spec": "Bitol Open Data Product Standard v1.0.0",
    "url": "https://github.com/bitol-io/open-data-product-standard",
    "formats": [
      "odps",
      "odps-bitol"
    ],
    "deprecatedFormats": []
  },
  {
    "name": "odps-v4.1",
    "spec": "LF/ODPI Open Data Product Specification v4.1",
    "url": "https://github.com/Open-Data-Product-Initiative/v4.1",
    "formats": [
      "odps-v4.1"
    ],
    "deprecatedFormats": [
      "opds"
    ]
  }
]
```

## Formats at a glance

| Format | Standard | Governed by | Invocation |
| --- | --- | --- | --- |
| `odcs` | Bitol Open Data Contract Standard v3.1.0 | [Bitol.io](https://bitol.io) | `fluid generate standard --format odcs` |
| `odps` | Bitol Open Data Product Standard v1.0.0 (v1.1.0 opt-in) | [Bitol.io](https://bitol.io) | `fluid generate standard --format odps` (alias `odps-bitol`) |
| `odps-v4.1` | LF/ODPI Open Data Product Specification v4.1 | LF / Open Data Product Initiative | `fluid generate standard --format odps-v4.1` (deprecated alias `opds`) |

## Notes

- **Exporters are not providers.** Spec-export formats serialize a contract to an open standard; they do not deploy infrastructure. That is why they have their own command — list deployment targets with [`fluid providers`](./providers.md) instead.
- **The per-format export commands are unchanged and fully supported.** See [`fluid odps`](./odps.md), [`fluid odps-bitol`](./odps-bitol.md), [`fluid odcs`](./odcs.md), [`fluid export-odps`](./export-odps.md), and [`fluid generate standard`](./generate.md#fluid-generate-standard) `--format odps|odcs|odps-v4.1`.
- **Bitol ODPS v1.1.0 is available opt-in since `0.13.1`.** The listing shows the v1.0.0 default; `fluid odps-bitol export --api-version v1.1.0` emits the v1.1.0 shape instead, which adds the RFC 0029 top-level `type` (`sourceAligned` / `aggregate` / `consumerAligned`, mapped from `metadata.productType`). v1.1.0 is pre-release until Bitol cuts it, so v1.0.0 stays the default.
- **Naming realigned in `0.11.0`.** `--format odps` now emits the Bitol standard (explicit alias `odps-bitol`); the LF/ODPI specification moved to `--format odps-v4.1`, with `opds` kept as a deprecated letter-swap alias.
- **Reclassified in `0.10.0`.** `odps` and `odcs` were reclassified from providers to exporters; [`fluid providers`](./providers.md) no longer lists them.
