# See Fluid Forge in action

Five short, self-contained reels covering the moments most likely to make or break adoption — the agentic stack, source-aligned ingestion, the guided forge UX, day-2 operations, and agent-loop tuning.

Every reel is HTML/CSS/JS only, no video, no analytics, no autoplay surprise. Use **←/→** to step scenes, **space** to pause, **r** to restart.

## The funnel — pick where you are

| If you're … | Watch this | Time |
|---|---|---|
| Brand new — wondering if Forge actually works | [Fluid Forge in action](#fluid-forge-in-action) | 60 s |
| Curious about source-aligned ingestion | [Source-aligned Bronze in 60 s](#source-aligned-bronze-in-60-seconds) | 60 s |
| Comparing the new `fluid forge` UX | [Guided forge UX](#guided-forge-ux) | 50 s |
| Operator: what comes after first apply | [Day-2 ops](#day-2-ops) | 60 s |
| Operator: agent-loop tuning | [Compaction strategies](#compaction-strategies) | 30 s |

---

## Fluid Forge in action

`fluid forge data-model from-intent` against four LLM providers — Anthropic Haiku 4.5, OpenAI gpt-4.1-mini, Gemini 2.5-flash, local Ollama gemma4 — building the same retail customer-orders contract on each.

<iframe
  src="/forge_docs/reels/forge-in-action.html"
  width="100%"
  height="540"
  style="border: 1px solid #232a3d; border-radius: 12px; max-width: 1100px;"
  loading="lazy"
  title="Fluid Forge in action — agentic data-product flow">
</iframe>

Same intent file, four providers, same valid contract. Per-call token counts and dollar costs from real production runs. Local Ollama at $0. [Open standalone](/forge_docs/reels/forge-in-action.html)

## Source-aligned Bronze in 60 seconds

`fluid init --discover postgres://…` → `fluid validate` → `fluid apply`. DuckDB does the ingestion in-process — no Airflow, no Airbyte cluster, no infra setup. Demonstrates schema 0.7.3, the `acquisition` build pattern, and `metadata.productType: SDP`.

<iframe
  src="/forge_docs/reels/source-aligned-bronze.html"
  width="100%"
  height="500"
  style="border: 1px solid #232a3d; border-radius: 12px; max-width: 1100px;"
  loading="lazy"
  title="Source-aligned Bronze in 60 seconds — Fluid Forge">
</iframe>

Pairs with [Source-Aligned Acquisition](/forge_docs/advanced/source-aligned-acquisition.html), [Postgres → DuckDB walkthrough](/forge_docs/walkthrough/source-aligned-postgres-duckdb.html), and the `[fluid init --discover](/forge_docs/cli/init.html#discover)` reference. [Open standalone](/forge_docs/reels/source-aligned-bronze.html)

## Guided forge UX

The new `fluid forge` flow. Welcome scan in 50 ms → 5-mode picker → inferences-first interview with slash commands → streaming contract preview → pre-write panel with cost + run-id. Never writes a file before showing you what it's about to write.

<iframe
  src="/forge_docs/reels/guided-forge-ux.html"
  width="100%"
  height="500"
  style="border: 1px solid #232a3d; border-radius: 12px; max-width: 1100px;"
  loading="lazy"
  title="Guided fluid forge UX — Fluid Forge">
</iframe>

Pairs with [Guided `fluid forge` UX](/forge_docs/advanced/guided-forge-ux.html) and the [`fluid forge`](/forge_docs/cli/forge.html) reference. [Open standalone](/forge_docs/reels/guided-forge-ux.html)

## Day-2 ops

Inspect run records, scope logs by component, diff schema between runs, sweep retention, manage pipeline secrets, and aggregate cost. The new ops surface lives under its own umbrellas (`runs`, `retention`, `secrets`, `stats`) so it doesn't collide with `auth` / `doctor` / `ai setup`.

<iframe
  src="/forge_docs/reels/day2-ops.html"
  width="100%"
  height="500"
  style="border: 1px solid #232a3d; border-radius: 12px; max-width: 1100px;"
  loading="lazy"
  title="Day-2 ops — Fluid Forge">
</iframe>

Pairs with [`fluid runs`](/forge_docs/cli/runs.html), [`fluid retention`](/forge_docs/cli/retention.html), [`fluid secrets`](/forge_docs/cli/secrets.html), and [`fluid stats`](/forge_docs/cli/stats.html). [Open standalone](/forge_docs/reels/day2-ops.html)

## Compaction strategies

When the multi-turn agent loop accumulates enough tool-result history to threaten the model's context window, the compaction layer steps in. This walks the three strategies — `truncate`, `summarize`, `hybrid`.

<iframe
  src="/forge_docs/reels/compaction-and-warnings.html"
  width="100%"
  height="480"
  style="border: 1px solid #232a3d; border-radius: 12px; max-width: 1100px;"
  loading="lazy"
  title="Compaction strategies and capability warnings walkthrough">
</iframe>

Pairs with [Agentic primitives → Token-budget pre-flight & compaction](/forge_docs/advanced/agentic-primitives.html#token-budget-preflight-and-compaction). [Open standalone](/forge_docs/reels/compaction-and-warnings.html)

---

## How these reels are sourced

Each reel renders from a `SCENES = [...]` array in a single self-contained HTML file under [`docs/.vuepress/public/reels/`](https://github.com/Agenticstiger/forge_docs/tree/main/docs/.vuepress/public/reels). No external CDNs, no JS frameworks, no images — just terminal-styled HTML/CSS/JS that auto-advances. Roughly 25–30 KB per reel, lazy-loaded so the page stays fast on first paint.

Token counts, durations, and costs in the LLM-driven reels (Fluid Forge in action, Compaction, Capability) are real captures from production runs. Latency numbers in the deterministic reels (Source-aligned Bronze, Guided forge UX, Day-2 ops) are representative of the schema 0.7.3 stack against the included `examples/source-aligned-postgres-duckdb` fixture.

If you want to capture your own run as a reel: copy any of the six files, replace the `SCENES` array with your captured CLI output, and reference it from a markdown page with an `<iframe>`.

## See also

- [Get Started](/forge_docs/getting-started/) — install, scaffold, validate, run locally
- [Source-Aligned Acquisition](/forge_docs/advanced/source-aligned-acquisition.html) — the framework powering the Bronze reel
- [Product Types — SDP, ADP, CDP](/forge_docs/data-products/product-type.html) — the vocabulary used throughout
- [Guided `fluid forge` UX](/forge_docs/advanced/guided-forge-ux.html) — the architecture behind the forge reel
- [Capability Warnings](/forge_docs/advanced/capability-warnings.html) — the per-model coverage matrix
