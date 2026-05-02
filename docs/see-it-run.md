# See Fluid Forge in action

Five short reels. Each one starts with the pain. Each one closes with a number you remember.

Use **←/→** to step scenes, **space** to pause, **r** to restart.

## Pick your problem

| Your pain | Watch this | Time | Punchline |
|---|---|---|---|
| Writing 200 lines of Python per data source | [$0.03 per data product](#_0-03-per-data-product) | 60 s | Three providers. Same contract. Free on Ollama. |
| Six months to set up Airbyte for one Postgres | [Six months → sixty seconds](#six-months-sixty-seconds) | 60 s | Six engines. One contract. Zero clusters. |
| Most CLIs ask 27 questions before they help | [23 questions, skipped](#_23-questions-skipped) | 50 s | 47 ms scan. 4 of 5 questions auto-resolved. |
| 3am Slack ping: pipeline broke, who knows why | [Skip the panic](#skip-the-panic) | 60 s | 3am incident → ship in 90 seconds. |
| Your agent loop quietly spent $0.50 on tool history | [$0.50 → $0.05](#_0-50-0-05) | 30 s | One env var. 10× cheaper agent loops. |

---

## $0.03 per data product

Most data teams write 200 lines of Python per source. Or 8 lines of YAML and let the AI build the contract — same intent, three providers (Anthropic Haiku 4.5, OpenAI gpt-4.1-mini, local Ollama gemma4), real production cost figures on screen. Switch providers any time. The contract stays portable.

<iframe
  src="/forge_docs/reels/forge-in-action.html"
  width="100%"
  height="540"
  style="border: 1px solid #232a3d; border-radius: 12px; max-width: 1100px;"
  loading="lazy"
  title="Skip the glue code — Fluid Forge in action">
</iframe>

[Open standalone](/forge_docs/reels/forge-in-action.html). Pairs with [Forge Data Model](/forge_docs/forge-data-model.html) and [LLM Providers](/forge_docs/advanced/llm-providers.html).

## Six months → sixty seconds

Six months of Airbyte. Two weeks of Airflow DAGs. JVM heap tuning. For one Postgres source. Or `fluid init --discover postgres://…` and a 60-second flight to a working Bronze contract — switch `engine:` between `duckdb`, `dlt`, `meltano`, `airbyte`, `kafka-connect`, `debezium` when you outgrow embedded mode.

<iframe
  src="/forge_docs/reels/source-aligned-bronze.html"
  width="100%"
  height="500"
  style="border: 1px solid #232a3d; border-radius: 12px; max-width: 1100px;"
  loading="lazy"
  title="Skip the cluster — source-aligned Bronze in 60 seconds">
</iframe>

[Open standalone](/forge_docs/reels/source-aligned-bronze.html). Pairs with [Source-Aligned Acquisition](/forge_docs/advanced/source-aligned-acquisition.html), [Postgres → DuckDB walkthrough](/forge_docs/walkthrough/source-aligned-postgres-duckdb.html), and [`fluid init --discover`](/forge_docs/cli/init.html#discover).

## 23 questions, skipped

Most CLIs ask 27 questions before they help you. Forge asks four — the rest, it already knows. 47 ms welcome scan, 5-mode picker, inferences-first interview, slash commands at every prompt, cost-cap progress prefix in real time, and a pre-write panel so nothing surprises you.

<iframe
  src="/forge_docs/reels/guided-forge-ux.html"
  width="100%"
  height="500"
  style="border: 1px solid #232a3d; border-radius: 12px; max-width: 1100px;"
  loading="lazy"
  title="Skip the questions — Fluid Forge guided UX">
</iframe>

[Open standalone](/forge_docs/reels/guided-forge-ux.html). Pairs with [Guided `fluid forge` UX](/forge_docs/advanced/guided-forge-ux.html) and the [`fluid forge`](/forge_docs/cli/forge.html) reference.

## Skip the panic

It's 3am. Pipeline broke. You have 90 seconds. `fluid runs status` (where), `fluid runs logs --component dlq` (why), `fluid runs diff` (what), one-line policy fix, `fluid ship`. Day-1 ships. Day-2 doesn't surprise.

<iframe
  src="/forge_docs/reels/day2-ops.html"
  width="100%"
  height="500"
  style="border: 1px solid #232a3d; border-radius: 12px; max-width: 1100px;"
  loading="lazy"
  title="Skip the panic — Fluid Forge day-2 ops">
</iframe>

[Open standalone](/forge_docs/reels/day2-ops.html). Pairs with [`fluid runs`](/forge_docs/cli/runs.html), [`fluid retention`](/forge_docs/cli/retention.html), [`fluid secrets`](/forge_docs/cli/secrets.html), [`fluid stats`](/forge_docs/cli/stats.html), and [Typed CLI Errors](/forge_docs/advanced/typed-cli-errors.html).

## $0.50 → $0.05

Long agent loops accumulate tool results — every turn rides on top of the last one. Without compaction, your bill grows super-linearly. Three strategies — `truncate` (free, default), `summarize` (LLM-backed, high recall), `hybrid` (cheap path first, summariser as safety net) — pick yours, set one env var, watch the bill drop 10×.

<iframe
  src="/forge_docs/reels/compaction-and-warnings.html"
  width="100%"
  height="480"
  style="border: 1px solid #232a3d; border-radius: 12px; max-width: 1100px;"
  loading="lazy"
  title="Skip the runaway bill — Fluid Forge compaction strategies">
</iframe>

[Open standalone](/forge_docs/reels/compaction-and-warnings.html). Pairs with [Agentic primitives → Token-budget pre-flight & compaction](/forge_docs/advanced/agentic-primitives.html#token-budget-preflight-and-compaction).

---

## How these reels are sourced

Each reel renders from a `SCENES = [...]` array in a single self-contained HTML file under [`docs/.vuepress/public/reels/`](https://github.com/Agenticstiger/forge_docs/tree/main/docs/.vuepress/public/reels). No external CDNs, no JS frameworks, no images — just terminal-styled HTML/CSS/JS that auto-advances. Roughly 27 KB per reel, lazy-loaded so the page stays fast on first paint.

Token counts, durations, and costs in the LLM-driven reels (Skip the glue code, Skip the runaway bill) are real captures from production runs. Latency numbers in the deterministic reels (Skip the cluster, Skip the questions, Skip the panic) are representative of the v0.7.3 stack against the included `examples/source-aligned-postgres-duckdb` fixture.

If you want to capture your own run as a reel: copy any of the five files, replace the `SCENES` array, and reference it from a markdown page with an `<iframe>`.

## See also

- [Get Started](/forge_docs/getting-started/) — install, scaffold, validate, run locally
- [Source-Aligned Acquisition](/forge_docs/advanced/source-aligned-acquisition.html) — the framework powering the Bronze reel
- [Product Types — SDP, ADP, CDP](/forge_docs/data-products/product-type.html) — the vocabulary used throughout
- [Guided `fluid forge` UX](/forge_docs/advanced/guided-forge-ux.html) — the architecture behind the guided UX reel
- [Capability Warnings](/forge_docs/advanced/capability-warnings.html) — the per-model coverage matrix
