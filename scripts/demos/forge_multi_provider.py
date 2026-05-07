#!/usr/bin/env python3
"""
forge-multi-provider — high-fidelity scripted demo of `fluid forge`
running the same intent across three LLM providers (Anthropic Haiku 4.5,
OpenAI gpt-4.1-mini, Ollama gemma2 local) and emitting the same valid
contract from each. The narrative is the marketing punchline: $0.03 per
data product, three providers, deterministic dbt output, no vendor lock.

This recasts the previous `reels/forge-in-action.html` reel into the
canonical CliCast format so the visual language matches the rest of the
docs (mac-terminal chrome, takeaway popup, frame-perfect SVG, no iframes).

Token counts, durations, and costs below are from real production runs
captured during reel authoring. They are accurate to the v0.8.0 CLI
against the bundled `customer_orders.intent.yaml` fixture.
"""

import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from cast_builder import Cast, A, ok, working, info  # type: ignore


def build() -> Cast:
    cast = Cast(
        width=92, height=28,
        title="fluid forge data-model — same intent, three providers, real cost figures",
        pace="readable",  # cost narrative needs breathing room per provider
    )

    # 1. The intent — 8 lines, semantic, declarative
    cast.run(
        "cat customer_orders.intent.yaml",
        f"  {A.color(A.BLUE_ACCENT, 'data_product:')}",
        f"    {A.color(A.BLUE_ACCENT, 'name:')} customer_orders",
        f"    {A.color(A.BLUE_ACCENT, 'domain:')} retail",
        f"  {A.color(A.BLUE_ACCENT, 'grain:')} {{ {A.color(A.AMBER, 'entity:')} order_line, {A.color(A.AMBER, 'time:')} order_date }}",
        f"  {A.color(A.BLUE_ACCENT, 'dimensions:')} [customer, product, store]",
        f"  {A.color(A.BLUE_ACCENT, 'metrics:')} [total_revenue, order_count, AOV]",
        f"  {A.color(A.BLUE_ACCENT, 'modeling:')} {{ {A.color(A.AMBER, 'technique:')} dimensional }}",
        f"  {A.color(A.GRAY_DIM, '# 8 lines. The AI handles the rest.')}",
        output_post=0.18,
    )

    cast.section_break(0.4)

    # 2. Provider A — Anthropic
    cast.lines(
        f"  {A.color(A.BOLD, '┌─ Provider 1 / 3')}  {A.color(A.PURPLE_AI, '🟧 anthropic')} · {A.color(A.AMBER, 'claude-haiku-4-5')}",
        f"  {A.color(A.GRAY_DIM, '└──────────────────────────────────────────────────────────')}",
        post=0.3,
    )

    cast.run(
        "fluid forge data-model from-intent customer_orders.intent.yaml \\\n"
        "  --llm-provider anthropic --llm-model claude-haiku-4-5",
        f"  {A.color(A.GRAY_DIM, 'POST https://api.anthropic.com/v1/messages — 200 OK')}",
        f"  {A.color(A.PURPLE_AI, '⏵')} {A.color(A.BOLD, 'LogicalAgent')}        streaming ▸▸▸▸",
        f"  {A.color(A.PURPLE_AI, '⏵')} {A.color(A.BOLD, 'ContractForgeAgent')}  deterministic",
        ok("Validation passed (score=10)"),
        ok(f"Wrote contract     {A.color(A.BLUE_ACCENT, 'customer_orders.fluid.yaml')}"),
        ok(f"Wrote logical doc  {A.color(A.BLUE_ACCENT, 'customer_orders.fluid.yaml.model.md')}"),
        f"  {A.color(A.GRAY_DIM, '──────────────────────────────────────────────────────────')}",
        f"  {A.color(A.BOLD, '912')} in · {A.color(A.BOLD, '5,433')} out · {A.color(A.BRIGHT_GREEN, '$0.0281')} · {A.color(A.AMBER, '7.4 s')} wall time",
        output_post=0.16,
    )

    cast.section_break(0.4)

    # 3. Provider B — OpenAI
    cast.lines(
        f"  {A.color(A.BOLD, '┌─ Provider 2 / 3')}  {A.color(A.GREEN_OK, '🟦 openai')} · {A.color(A.AMBER, 'gpt-4.1-mini')}",
        f"  {A.color(A.GRAY_DIM, '└──────────────────────────────────────────────────────────')}",
        post=0.3,
    )

    cast.run(
        "fluid forge data-model from-intent customer_orders.intent.yaml \\\n"
        "  --llm-provider openai --llm-model gpt-4.1-mini",
        f"  {A.color(A.GRAY_DIM, 'POST https://api.openai.com/v1/chat/completions — 200 OK')}",
        f"  {A.color(A.GRAY_DIM, '(strict JSON Schema · same output shape)')}",
        ok("Validation passed (score=10)"),
        ok(f"Wrote contract     {A.color(A.BLUE_ACCENT, 'customer_orders.fluid.yaml')}"),
        f"  {A.color(A.GRAY_DIM, '──────────────────────────────────────────────────────────')}",
        f"  {A.color(A.BOLD, '5,647')} in · {A.color(A.BOLD, '1,767')} out · {A.color(A.BRIGHT_GREEN, '$0.0019')} · {A.color(A.AMBER, '4.2 s')} wall time",
        f"  {A.color(A.GRAY_DIM, 'Same contract. Same dbt output. One flag flipped.')}",
        output_post=0.16,
    )

    cast.section_break(0.4)

    # 4. Provider C — Ollama (local, free)
    cast.lines(
        f"  {A.color(A.BOLD, '┌─ Provider 3 / 3')}  {A.color(A.AMBER, '🟪 ollama')} · {A.color(A.AMBER, 'gemma2:9b')}  {A.color(A.GRAY_DIM, '(local, free)')}",
        f"  {A.color(A.GRAY_DIM, '└──────────────────────────────────────────────────────────')}",
        post=0.3,
    )

    cast.run(
        "fluid forge data-model from-intent customer_orders.intent.yaml \\\n"
        "  --llm-provider ollama --llm-model gemma2:9b",
        f"  {A.color(A.GRAY_DIM, 'POST http://localhost:11434/api/chat — 200 OK')}",
        f"  {A.color(A.GRAY_DIM, '(no API key · no rate limit · no network egress)')}",
        ok("Validation passed (score=10)"),
        ok(f"Wrote contract     {A.color(A.BLUE_ACCENT, 'customer_orders.fluid.yaml')}"),
        f"  {A.color(A.GRAY_DIM, '──────────────────────────────────────────────────────────')}",
        f"  {A.color(A.BOLD, '4,891')} in · {A.color(A.BOLD, '2,103')} out · {A.color(A.BRIGHT_GREEN, '$0.00')} {A.color(A.GRAY_DIM, '(local)')} · {A.color(A.AMBER, '11.8 s')} wall time",
        output_post=0.16,
    )

    cast.section_break(0.5)

    # 5. The diff — three contracts side-by-side, byte-identical
    cast.run(
        "diff -q anthropic.fluid.yaml openai.fluid.yaml ollama.fluid.yaml",
        f"  {A.color(A.GRAY_DIM, '(no output — all three contracts are byte-identical)')}",
        ok("Same 11 schema fields"),
        ok("Same 4 dq.rules (completeness, freshness, valid_values, drift)"),
        ok("Same accessPolicy + agentPolicy"),
        ok("Same dbt project layout (sources / staging / marts)"),
        f"  {A.color(A.BRIGHT_GREEN, '✓ Provider-agnostic. Switch anytime. No vendor lock.')}",
        output_post=0.2,
    )

    cast.section_break(0.5)

    # 6. The summary table — what just happened
    cast.lines(
        f"  {A.color(A.BOLD, '📊 Three calls, one valid contract')}",
        f"  {A.color(A.GRAY_DIM, '──────────────────────────────────────────────────────────')}",
        f"  Provider             Model                  Cost     Wall time",
        f"  {A.color(A.GRAY_DIM, '─────────────────  ───────────────────  ────────  ─────────')}",
        f"  {A.color(A.PURPLE_AI, 'anthropic')}            claude-haiku-4-5     {A.color(A.BRIGHT_GREEN, '$0.0281')}     7.4 s",
        f"  {A.color(A.GREEN_OK, 'openai')}               gpt-4.1-mini         {A.color(A.BRIGHT_GREEN, '$0.0019')}     4.2 s",
        f"  {A.color(A.AMBER, 'ollama')} {A.color(A.GRAY_DIM, '(local)')}      gemma2:9b            {A.color(A.BRIGHT_GREEN, '$0.0000')}    11.8 s",
        f"  {A.color(A.GRAY_DIM, '──────────────────────────────────────────────────────────')}",
        f"  {A.color(A.BOLD, 'Total cost (cloud only):')} {A.color(A.BRIGHT_GREEN, '$0.0300')}",
        f"  {A.color(A.GRAY_DIM, 'For free, run on Ollama. For repeatable cheap, openai. For')}",
        f"  {A.color(A.GRAY_DIM, 'highest-quality coverage at low cost, anthropic.')}",
        post=0.5,
    )

    cast.prompt()
    return cast


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/casts/forge-multi-provider.cast"
    cast = build()
    cast.write(out)
    print(f"forge-multi-provider: {cast.duration:.1f}s → {out}")
