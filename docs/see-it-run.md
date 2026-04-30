# See Fluid Forge in action

Eight short, self-contained reels showing what Fluid Forge actually looks like at the moments most likely to make or break adoption — install, first run, AI flow, multi-cloud portability, and dbt integration.

Every reel is HTML/CSS/JS only — no video, no analytics, no autoplay surprise. Use **←/→** to step scenes, **space** to pause, **r** to restart.

## The funnel — pick where you are

| If you're … | Watch this | Time |
|---|---|---|
| Brand new — wondering if this works at all | [The 60-second walkthrough](#the-60-second-walkthrough) | 60 s |
| About to install — wondering if it's fast | [Quickstart in 90 seconds](#quickstart-in-90-seconds) | 90 s |
| AI-curious — wondering if the agent is real | [Agent loop, live](#agent-loop-live) | 60 s |
| Comparing cloud backends | [One contract, three backends](#one-contract-three-backends) | 50 s |
| Integrating with dbt | [Forged contract → runnable dbt](#forged-contract-runnable-dbt) | 45 s |
| Adding your own backend | [Custom provider in 5 minutes](#custom-provider-in-5-minutes) | 50 s |
| Operator tuning provider models | [Capability-warning banner](#capability-warning-banner) | 20 s |
| Operator tuning the agent loop | [Compaction strategies](#compaction-strategies) | 30 s |

---

## The 60-second walkthrough

`fluid forge data-model from-intent` against four LLM providers — Anthropic Haiku 4.5, OpenAI gpt-4.1-mini, Gemini 2.5-flash, local Ollama gemma4 — building the same retail customer-orders contract on each.

<iframe
  src="/forge_docs/reels/forge-in-action.html"
  width="100%"
  height="540"
  style="border: 1px solid #232a3d; border-radius: 12px; max-width: 1100px;"
  loading="lazy"
  title="Fluid Forge in action — agentic data-product flow">
</iframe>

What to watch for — same intent file, four providers, same valid contract. Per-call token counts and dollar costs. Capability warnings firing on degraded combos. Local Ollama at $0. [Open standalone](/forge_docs/reels/forge-in-action.html)

## Quickstart in 90 seconds

`pip install` → `fluid init --quickstart` → `fluid validate` → `fluid plan` → `fluid apply`. Local DuckDB target, no cloud setup, no API keys.

<iframe
  src="/forge_docs/reels/quickstart-90s.html"
  width="100%"
  height="500"
  style="border: 1px solid #232a3d; border-radius: 12px; max-width: 1100px;"
  loading="lazy"
  title="Quickstart in 90 seconds — Fluid Forge">
</iframe>

Pairs with [Get Started](/forge_docs/getting-started/). [Open standalone](/forge_docs/reels/quickstart-90s.html)

## Agent loop, live

`fluid forge --agent-loop` runs over multiple turns: the agent inspects the workspace, lists templates, reads template intents, scaffolds, then self-validates. Six turns, five tool calls, all transparent.

<iframe
  src="/forge_docs/reels/agent-loop-live.html"
  width="100%"
  height="500"
  style="border: 1px solid #232a3d; border-radius: 12px; max-width: 1100px;"
  loading="lazy"
  title="Agent loop, live — Fluid Forge">
</iframe>

Pairs with [`fluid forge`](/forge_docs/cli/forge.html), [Agentic primitives](/forge_docs/advanced/agentic-primitives.html). [Open standalone](/forge_docs/reels/agent-loop-live.html)

## One contract, three backends

The same `customer_orders.fluid.yaml` against DuckDB, BigQuery, and Snowflake — `--provider` flag is the only thing that changes.

<iframe
  src="/forge_docs/reels/multi-target-portability.html"
  width="100%"
  height="480"
  style="border: 1px solid #232a3d; border-radius: 12px; max-width: 1100px;"
  loading="lazy"
  title="One contract, three backends — Fluid Forge">
</iframe>

Pairs with [Providers](/forge_docs/providers/). [Open standalone](/forge_docs/reels/multi-target-portability.html)

## Forged contract → runnable dbt

`fluid generate transformation` reads the `.model.json` sidecar and emits a dbt project that parses, runs, and passes its own tests — not a skeleton.

<iframe
  src="/forge_docs/reels/generate-transformation-dbt.html"
  width="100%"
  height="500"
  style="border: 1px solid #232a3d; border-radius: 12px; max-width: 1100px;"
  loading="lazy"
  title="Forged contract to runnable dbt — Fluid Forge">
</iframe>

Pairs with [`fluid generate`](/forge_docs/cli/generate.html). [Open standalone](/forge_docs/reels/generate-transformation-dbt.html)

## Custom provider in 5 minutes

Subclass `FluidProvider`, implement four methods, register the entry point. Same shape as the built-in `gcp` / `aws` / `snowflake` plugins.

<iframe
  src="/forge_docs/reels/custom-provider-5min.html"
  width="100%"
  height="480"
  style="border: 1px solid #232a3d; border-radius: 12px; max-width: 1100px;"
  loading="lazy"
  title="Custom provider in 5 minutes — Fluid Forge">
</iframe>

Pairs with [Custom Providers](/forge_docs/providers/custom-providers.html). [Open standalone](/forge_docs/reels/custom-provider-5min.html)

## Capability-warning banner

The same run on a degraded `(provider, model)` combo (`openai/o1-mini`) prints a one-paragraph warning at start; the supported combo (`openai/gpt-4.1-mini`) is silent.

<iframe
  src="/forge_docs/reels/capability-warning-fires.html"
  width="100%"
  height="440"
  style="border: 1px solid #232a3d; border-radius: 12px; max-width: 1100px;"
  loading="lazy"
  title="Capability warning fires — worked example">
</iframe>

Pairs with [Capability Warnings](/forge_docs/advanced/capability-warnings.html). [Open standalone](/forge_docs/reels/capability-warning-fires.html)

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

## Where these come from

Each reel is rendered from a `SCENES = [...]` array in a single self-contained HTML file under [`docs/.vuepress/public/reels/`](https://github.com/Agenticstiger/forge_docs/tree/main/docs/.vuepress/public/reels). No external CDNs, no JS frameworks, no images — just terminal-styled HTML/CSS/JS that auto-advances. Roughly 25–30 KB per reel, lazy-loaded so the page stays fast on first paint.

Token counts, durations, and costs in the LLM-driven reels are real — captured live from production runs across Anthropic, OpenAI, Gemini, and Ollama. Latency numbers in the deterministic reels (quickstart, generate-transformation, multi-target) are representative of v0.8.0 against the customer-360 quickstart template.

If you want to capture your own run as a reel: copy any of the eight files, replace the `SCENES` array with your captured CLI output (the runs print structured token-usage logs you can paste in directly), and reference it from a markdown page with an `<iframe>`.

## See also

- [Get Started](/forge_docs/getting-started/) — install, scaffold, validate, run locally
- [`fluid forge`](/forge_docs/cli/forge.html) — AI-assisted scaffolding entry point
- [AI Forge and data-model journeys](/forge_docs/walkthrough/ai-forge-data-model.html) — the prose walkthrough the hero reel is condensed from
- [Capability Warnings](/forge_docs/advanced/capability-warnings.html) — full coverage matrix
- [Agentic primitives](/forge_docs/advanced/agentic-primitives.html) — the architecture the reels are visualizing
- [Custom Providers](/forge_docs/providers/custom-providers.html) — the FluidProvider API
