# See Fluid Forge in action

Three short, self-contained reels that show what a Fluid Forge run actually looks like. Every token count, every duration, every cost number is from a real production call — nothing is mocked.

Use ←/→ to step scenes, **space** to pause, **r** to restart on any reel.

## 1. The 60-second walkthrough

`fluid forge data-model from-intent` against four LLM providers — Anthropic Haiku 4.5, OpenAI gpt-4.1-mini, Gemini 2.5-flash, and local Ollama gemma4 — building the same retail customer-orders contract on each.

<iframe
  src="/forge_docs/reels/forge-in-action.html"
  width="100%"
  height="540"
  style="border: 1px solid #232a3d; border-radius: 12px; max-width: 1100px;"
  loading="lazy"
  title="Fluid Forge in action — agentic data-product flow">
</iframe>

What to watch for:

- **Same intent file, four providers, same valid contract** — the agent layer abstracts away provider quirks
- **Per-call token counts and dollar costs** — captured live, including streaming runs
- **Capability warnings firing on degraded combos** — the run continues, but you know what's degraded
- **Local Ollama at $0** — no API key, fully offline, works for the staged pipeline

[Open the standalone reel →](/forge_docs/reels/forge-in-action.html)

## 2. Compaction strategies (~30s)

When the multi-turn agent loop accumulates enough tool-result history to threaten the model's context window, the compaction layer steps in. This reel walks the three strategies — `truncate`, `summarize`, `hybrid` — so you can pick the right one for your provider.

<iframe
  src="/forge_docs/reels/compaction-and-warnings.html"
  width="100%"
  height="480"
  style="border: 1px solid #232a3d; border-radius: 12px; max-width: 1100px;"
  loading="lazy"
  title="Compaction strategies and capability warnings walkthrough">
</iframe>

Pairs with [Agentic primitives → Token-budget pre-flight & compaction](/forge_docs/advanced/agentic-primitives.html#token-budget-preflight-and-compaction).

[Open the standalone reel →](/forge_docs/reels/compaction-and-warnings.html)

## 3. Capability-warning banner (~20s)

The same run on a degraded (provider, model) combo (`openai/o1-mini`) prints a warning at start; the supported combo (`openai/gpt-4.1-mini`) is silent. Three scenes, no narration needed.

<iframe
  src="/forge_docs/reels/capability-warning-fires.html"
  width="100%"
  height="440"
  style="border: 1px solid #232a3d; border-radius: 12px; max-width: 1100px;"
  loading="lazy"
  title="Capability warning fires — worked example">
</iframe>

Pairs with [Capability Warnings](/forge_docs/advanced/capability-warnings.html).

[Open the standalone reel →](/forge_docs/reels/capability-warning-fires.html)

## Where these come from

Each reel is rendered from a `SCENES = [...]` array in a single self-contained HTML file under [`docs/.vuepress/public/reels/`](https://github.com/Agenticstiger/forge_docs/tree/main/docs/.vuepress/public/reels). No external CDNs, no JS frameworks, no images — just terminal-styled HTML/CSS/JS that auto-advances. Roughly 30 KB per reel, lazy-loaded so the page stays fast on first paint.

If you want to capture your own run as a reel: copy any of the three files, replace the `SCENES` array with your captured CLI output (the runs print structured token-usage logs you can paste in directly), and reference it from a markdown page with an `<iframe>`.

## See also

- [Get Started](/forge_docs/getting-started/) — install, scaffold, validate, run locally before any reel makes sense
- [AI Forge and data-model journeys](/forge_docs/walkthrough/ai-forge-data-model.html) — the prose walkthrough the first reel is condensed from
- [Capability Warnings](/forge_docs/advanced/capability-warnings.html) — full coverage matrix referenced in reel #3
- [Agentic primitives](/forge_docs/advanced/agentic-primitives.html) — the architecture the reels are visualizing
