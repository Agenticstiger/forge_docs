#!/usr/bin/env python3
"""
agent-compaction — high-fidelity scripted demo of agent-loop context
compaction: show context bloat over 20 turns ($0.50/run baseline), then
the three strategies (truncate / summarize / hybrid) with real before/
after costs ($0.50 → $0.05). One env var to set, 10× cheaper agent loops.

Recasts reels/compaction-and-warnings.html into a CliCast.
"""

import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from cast_builder import Cast, A, ok, working, info  # type: ignore


def build() -> Cast:
    cast = Cast(
        width=92, height=26,
        title="Agent-loop compaction — $0.50/run → $0.05/run with one env var",
        pace="readable",
    )

    # 1. The baseline — 20-turn agent loop without compaction
    cast.lines(
        f"  {A.color(A.BOLD, '🐢 Baseline — no compaction')}",
        f"  {A.color(A.GRAY_DIM, '─────────────────────────────────────────────────────────────')}",
        f"  20-turn agent loop. Every tool result rides on top of the last.",
        post=0.4,
    )

    cast.lines(
        f"  {A.color(A.BOLD, 'turn   ctx tokens   $/turn   $ cumul')}",
        f"  {A.color(A.GRAY_DIM, '─────  ───────────  ───────  ────────')}",
        f"   1     {A.color(A.AMBER, '5,200')}        $0.001   $0.001",
        f"   5     {A.color(A.AMBER, '23,400')}       $0.006   $0.018",
        f"  10     {A.color(A.AMBER, '67,800')}       $0.017   $0.092",
        f"  15     {A.color(A.AMBER, '142,500')}      $0.036   $0.241",
        f"  20     {A.color(A.RED_ERR, '298,000')}      {A.color(A.RED_ERR, '$0.075')}   {A.color(A.RED_ERR, '$0.503')}",
        f"  {A.color(A.GRAY_DIM, '─────────────────────────────────────────────────────────────')}",
        f"  {A.color(A.RED_ERR, '⚠')} {A.color(A.BOLD, 'Super-linear growth.')} 20-turn loop = {A.color(A.RED_ERR, '$0.50')} per agent run.",
        post=0.5,
    )

    cast.section_break(0.5)

    # 2. Strategy 1 — truncate (free)
    cast.lines(
        f"  {A.color(A.BOLD, '⚡ Strategy 1 / 3 — truncate (free, default)')}",
        f"  {A.color(A.GRAY_DIM, '─────────────────────────────────────────────────────────────')}",
        f"  Drop oldest tool results when context > threshold. Zero LLM cost.",
        f"  Recall: low. Best for: long loops where early turns are throwaway.",
        post=0.4,
    )
    cast.run(
        "FORGE_AGENT_COMPACTION=truncate fluid forge --max-turns 20",
        f"  {A.color(A.GRAY_DIM, '...running 20-turn agent loop...')}",
        ok(f"Compaction triggered at turn 12 (ctx={A.color(A.AMBER, '95,000')} > {A.color(A.GRAY_DIM, '90,000')} threshold)"),
        ok("Dropped 7 oldest tool results"),
        f"  {A.color(A.GRAY_DIM, '─────────────────────────────────────────────────────────────')}",
        f"  Final cost: {A.color(A.BRIGHT_GREEN, '$0.087')} (vs {A.color(A.RED_ERR, '$0.503')} baseline)  ·  {A.color(A.BOLD, '5.8× cheaper')}",
        output_post=0.18,
    )

    cast.section_break(0.4)

    # 3. Strategy 2 — summarize (LLM-backed)
    cast.lines(
        f"  {A.color(A.BOLD, '🧠 Strategy 2 / 3 — summarize (LLM-backed, high recall)')}",
        f"  {A.color(A.GRAY_DIM, '─────────────────────────────────────────────────────────────')}",
        f"  Summarize old turns via cheap model (haiku/mini). Keep facts, drop fluff.",
        f"  Recall: high. Best for: research/analysis loops where every fact matters.",
        post=0.4,
    )
    cast.run(
        "FORGE_AGENT_COMPACTION=summarize fluid forge --max-turns 20",
        f"  {A.color(A.GRAY_DIM, '...running 20-turn agent loop...')}",
        ok(f"Compaction triggered at turn 12"),
        ok(f"Summarized turns 1-7 → {A.color(A.AMBER, '2,400 tokens')} (was {A.color(A.GRAY_DIM, '52,000')})"),
        f"  {A.color(A.GRAY_DIM, 'Summarizer cost: $0.003 (claude-haiku)')}",
        f"  {A.color(A.GRAY_DIM, '─────────────────────────────────────────────────────────────')}",
        f"  Final cost: {A.color(A.BRIGHT_GREEN, '$0.054')} (vs {A.color(A.RED_ERR, '$0.503')} baseline)  ·  {A.color(A.BOLD, '9.3× cheaper')}",
        output_post=0.18,
    )

    cast.section_break(0.4)

    # 4. Strategy 3 — hybrid
    cast.lines(
        f"  {A.color(A.BOLD, '🎯 Strategy 3 / 3 — hybrid (truncate first, summarize as safety net)')}",
        f"  {A.color(A.GRAY_DIM, '─────────────────────────────────────────────────────────────')}",
        f"  Truncate by default; summarize only when truncation drops a tool result",
        f"  flagged as load-bearing. Recall: medium-high. Best for: production loops.",
        post=0.4,
    )
    cast.run(
        "FORGE_AGENT_COMPACTION=hybrid fluid forge --max-turns 20",
        f"  {A.color(A.GRAY_DIM, '...running 20-turn agent loop...')}",
        ok(f"Truncated 5 turns at threshold"),
        ok(f"Summarized 2 load-bearing turns ({A.color(A.AMBER, '$0.001')} summariser cost)"),
        f"  {A.color(A.GRAY_DIM, '─────────────────────────────────────────────────────────────')}",
        f"  Final cost: {A.color(A.BRIGHT_GREEN, '$0.048')} (vs {A.color(A.RED_ERR, '$0.503')} baseline)  ·  {A.color(A.BOLD, '10.5× cheaper')}",
        output_post=0.18,
    )

    cast.section_break(0.5)

    # 5. The summary
    cast.lines(
        f"  {A.color(A.BOLD, '📊 Three strategies side-by-side')}",
        f"  {A.color(A.GRAY_DIM, '─────────────────────────────────────────────────────────────')}",
        f"  Strategy        Cost / 20-turn run     Multiplier     Best for",
        f"  {A.color(A.GRAY_DIM, '──────────────  ──────────────────  ─────────────  ─────────────')}",
        f"  none ({A.color(A.GRAY_DIM, 'baseline')})    {A.color(A.RED_ERR, '$0.503')}              1.0×           {A.color(A.GRAY_DIM, '(do not)')}",
        f"  truncate        {A.color(A.BRIGHT_GREEN, '$0.087')}              5.8×           long throwaway loops",
        f"  summarize       {A.color(A.BRIGHT_GREEN, '$0.054')}              9.3×           research / analysis",
        f"  hybrid          {A.color(A.BRIGHT_GREEN, '$0.048')}             10.5×           production (recommended)",
        f"  {A.color(A.GRAY_DIM, '─────────────────────────────────────────────────────────────')}",
        f"  {A.color(A.BOLD, 'Set one env var:')} FORGE_AGENT_COMPACTION=hybrid",
        f"  {A.color(A.GRAY_DIM, 'No code changes. Works with every --llm-provider.')}",
        post=0.5,
    )

    cast.prompt()
    return cast


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/casts/agent-compaction.cast"
    cast = build()
    cast.write(out)
    print(f"agent-compaction: {cast.duration:.1f}s → {out}")
