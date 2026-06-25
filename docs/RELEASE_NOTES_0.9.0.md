# Fluid Forge Docs Baseline: CLI `0.9.0`

**Release Date:** June 25, 2026
**Status:** Current stable docs baseline (supersedes [`0.8.11`](./RELEASE_NOTES_0.8.11.md))

## Headline

`0.9.0` lands the **streaming Kafka → Iceberg sink**. Fluid Forge can now derive and manage the connector configuration that lands streaming / CDC data into Apache Iceberg — from the same `contract.fluid.yaml`. `0.9.0` also **promotes contract schema `0.7.5` to the GA default** (it was a preview in the `0.8.x` line). Existing `0.7.4` contracts validate unchanged, and the streaming sink itself is a `0.7.5` feature you enable per contract via `iceberg_sink_enabled`. (`fluid init --quickstart` still scaffolds the pinned customer-360 template at `0.7.2`.)

::: tip Who should upgrade
Anyone building streaming / CDC products into Iceberg — and anyone who wants the latest security hardening. New contracts now default to schema `0.7.5`; the Iceberg streaming sink is a `0.7.5` feature you enable per contract (`iceberg_sink_enabled`). Existing batch contracts are unaffected. `pip install --upgrade data-product-forge`.
:::

## What changed in `v0.9.0`

### Added — streaming Kafka → Iceberg

- **Opt-in `fluid-schema-0.7.5`** with the `icebergConfig.streamingSink` block (`commitIntervalMs`, `dynamicEnabled`, `routeField`, `upsertMode`, `autoCreate`, `evolveSchema`, `controlTopic`), plus `iceberg_sink_enabled`, `iceberg_catalog_overrides`, `sink_topics`, and the `iceberg_table` → `iceberg` `binding.platform` alias. **`fluid-schema-0.7.5` is now the GA default** (promoted from preview); the streaming-sink fields (`iceberg_sink_enabled`, etc.) are opt-in per contract. (#266)
- **Kafka-Connect Iceberg sink derivation** — Forge derives the sink connector config from the contract (auto-create, schema evolution, control topic, record routing), and detects task-level connector failures with canonical `<table>__late_events` late-arrival naming. (#264, #268)
- **Debezium-Server Iceberg sink** — derive the embedded Debezium-Server → Iceberg configuration for CDC sources. (#284)
- **Confluent Tableflow plugin** — a managed Kafka → Iceberg IaC plugin. (#285)
- **Plan-time checks for the Iceberg streaming sink** — `fluid validate` / `fluid plan` catch streaming-sink misconfigurations before any apply. (#267)
- **REST + GCP / Azure Iceberg catalog profiles** in the resolver. (#280)

### Changed

- **`fluid mcp` split into a package** — internal refactor; the `fluid mcp serve` (producer / authoring) and `fluid mcp output-port serve` (consumer / data-access gate) surface is unchanged. (#282)
- Renamed `config.py` → `config_defaults.py` with clarifying docstrings. (#225)

### Fixed

- **Cross-platform text I/O** — `encoding="utf-8"` on all text file I/O, and forced UTF-8 stdout/stderr so the CLI no longer crashes on Windows `cp1252` consoles. (#269, #263)
- **Deterministic `planDigest`** across identical plan runs (so plan-binding doesn't spuriously mismatch). (#260)
- `fluid bundle --out -` restores logging state after the stderr redirect. (#261)

### Security

- **Redact `sasl.jaas.config`** in both redaction layers — streaming credentials never reach logs. (#270)
- **Redact run-record facets before disk write** — closes a Kafka-Connect task-trace credential leak in `.fluid` run records. (#272)

## Companion packages

| Package | Version | Notes |
|---|---|---|
| `data-product-forge` | **0.9.0** | The CLI (this docs set) |
| `data-product-forge-sdk` | `0.9.1` | Unchanged this release |
| `data-product-forge-custom-scaffold` | `0.1.1` | Unchanged this release |
