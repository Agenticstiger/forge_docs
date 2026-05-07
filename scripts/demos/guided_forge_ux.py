#!/usr/bin/env python3
"""
guided-forge-ux — high-fidelity scripted demo of `fluid forge`'s
guided-UX moments: 47 ms welcome scan, 5-mode picker, inferences-first
interview (4 questions instead of 27), slash commands at every prompt,
cost-cap progress prefix in real time, pre-write panel.

Recasts reels/guided-forge-ux.html into a CliCast.
"""

import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from cast_builder import Cast, A, ok, working, info  # type: ignore


def build() -> Cast:
    cast = Cast(
        width=92, height=28,
        title="fluid forge — 23 questions skipped, slash commands, pre-write panel",
        pace="readable",
    )

    # 1. Run forge — welcome scan kicks in immediately
    cast.run(
        "fluid forge",
        f"  {A.color(A.PURPLE_AI, '✨')} {A.color(A.BOLD, 'fluid forge')} — guided contract creation",
        f"  {A.color(A.GRAY_DIM, '─────────────────────────────────────────────────────────────')}",
        info(f"Welcome scan: scanning {A.color(A.BLUE_ACCENT, './')} for context..."),
        ok(f"Found {A.color(A.AMBER, '3 CSVs')}, {A.color(A.AMBER, '2 dbt models')}, {A.color(A.AMBER, '1 README')} ({A.color(A.GRAY_DIM, '47 ms')})"),
        ok(f"Inferred domain: {A.color(A.AMBER, 'finance')} (high confidence)"),
        ok(f"Inferred entity: {A.color(A.AMBER, 'customer_orders')} (cross-CSV foreign key match)"),
        ok(f"Inferred PII: {A.color(A.AMBER, '5 columns')} (email, phone, ssn, dob, name)"),
        f"  {A.color(A.GRAY_DIM, '─────────────────────────────────────────────────────────────')}",
        output_post=0.18,
    )

    cast.section_break(0.4)

    # 2. Mode picker — 5 modes
    cast.lines(
        f"  {A.color(A.BOLD, '? How would you like to start?')}",
        f"    {A.color(A.GREEN_OK, '▸')} 1. {A.color(A.BOLD, 'discover')}     start from local context (recommended)",
        f"      2. {A.color(A.DIM, 'intent')}        write 8 lines of YAML; AI fills the rest",
        f"      3. {A.color(A.DIM, 'blank')}         empty scaffold, fill it in by hand",
        f"      4. {A.color(A.DIM, 'from-existing')} migrate from dbt / dlt / Airflow",
        f"      5. {A.color(A.DIM, 'full-ai')}       AI generates everything from a domain prompt",
        f"  {A.color(A.GRAY_DIM, '   (↑/↓ to move, Enter to select, /help for slash commands)')}",
        post=0.5,
    )

    cast.lines(
        f"  {A.color(A.GRAY_DIM, '> ')} {A.color(A.GREEN_OK, '1')}  {A.color(A.GRAY_DIM, '# discover')}",
        post=0.3,
    )

    cast.section_break(0.4)

    # 3. The interview — 4 questions instead of 27
    cast.lines(
        f"  {A.color(A.BOLD, '🎯 4 questions — the rest, I already know')}",
        f"  {A.color(A.GRAY_DIM, '─────────────────────────────────────────────────────────────')}",
        f"  {A.color(A.GRAY_DIM, '(slash commands at every prompt: /skip /back /help /quit /save)')}",
        post=0.4,
    )

    cast.lines(
        f"  {A.color(A.BLUE_ACCENT, '? Q1.')} What should this product be called?  {A.color(A.GRAY_DIM, '[customer_orders_v1]')}",
        f"  {A.color(A.GRAY_DIM, '> ')} {A.color(A.GREEN_OK, '↵')}  {A.color(A.GRAY_DIM, '# accept inferred default')}",
        post=0.3,
    )
    cast.lines(
        f"  {A.color(A.BLUE_ACCENT, '? Q2.')} Target cloud?  {A.color(A.GRAY_DIM, '[gcp / aws / snowflake / local]')}",
        f"  {A.color(A.GRAY_DIM, '> ')} {A.color(A.GREEN_OK, 'gcp')}",
        post=0.3,
    )
    cast.lines(
        f"  {A.color(A.BLUE_ACCENT, '? Q3.')} Domain regulatory framework?  {A.color(A.GRAY_DIM, '[SOX/GDPR inferred from finance]')}",
        f"  {A.color(A.GRAY_DIM, '> ')} {A.color(A.GREEN_OK, '↵')}  {A.color(A.GRAY_DIM, '# accept')}",
        post=0.3,
    )
    cast.lines(
        f"  {A.color(A.BLUE_ACCENT, '? Q4.')} LLM cost cap for this run?  {A.color(A.GRAY_DIM, '[$0.05]')}",
        f"  {A.color(A.GRAY_DIM, '> ')} {A.color(A.GREEN_OK, '↵')}",
        post=0.3,
    )

    cast.section_break(0.4)

    # 4. Cost-cap progress in real time
    cast.lines(
        f"  {A.color(A.AMBER, '$0.000')} / {A.color(A.GRAY_DIM, '$0.050')}  {A.color(A.PURPLE_AI, '⏵')} Loading domain expertise pack: finance",
        post=0.3,
    )
    cast.lines(
        f"  {A.color(A.AMBER, '$0.001')} / {A.color(A.GRAY_DIM, '$0.050')}  {A.color(A.PURPLE_AI, '⏵')} Streaming LogicalAgent...",
        post=0.3,
    )
    cast.lines(
        f"  {A.color(A.AMBER, '$0.012')} / {A.color(A.GRAY_DIM, '$0.050')}  {A.color(A.PURPLE_AI, '⏵')} Streaming ContractForgeAgent...",
        post=0.3,
    )
    cast.lines(
        f"  {A.color(A.AMBER, '$0.021')} / {A.color(A.GRAY_DIM, '$0.050')}  {A.color(A.GREEN_OK, '✓')} agentPolicy emitted",
        post=0.3,
    )
    cast.lines(
        f"  {A.color(A.AMBER, '$0.021')} / {A.color(A.GRAY_DIM, '$0.050')}  {A.color(A.GREEN_OK, '✓')} Schema validation passed",
        post=0.4,
    )

    cast.section_break(0.4)

    # 5. Pre-write panel — review before commit
    cast.lines(
        f"  {A.color(A.BOLD, '📋 Pre-write panel — review before write')}",
        f"  {A.color(A.GRAY_DIM, '─────────────────────────────────────────────────────────────')}",
        f"  {A.color(A.BOLD, 'Will write:')}",
        f"    {A.color(A.GREEN_OK, '+')} contract.fluid.yaml          {A.color(A.GRAY_DIM, '147 lines, 4.2 KB')}",
        f"    {A.color(A.GREEN_OK, '+')} contract.fluid.yaml.model.md {A.color(A.GRAY_DIM, '38 lines, narrative doc')}",
        f"    {A.color(A.GREEN_OK, '+')} runtime/.state/copilot-memory.json  {A.color(A.GRAY_DIM, 'session memory')}",
        f"  {A.color(A.BOLD, 'Will NOT write:')}",
        f"    {A.color(A.GRAY_DIM, '- runtime/.state/cost-history.json     (read-only this run)')}",
        f"    {A.color(A.GRAY_DIM, '- .git/                                 (never touched)')}",
        f"  {A.color(A.GRAY_DIM, '─────────────────────────────────────────────────────────────')}",
        f"  {A.color(A.BOLD, '? Proceed?')}  {A.color(A.GRAY_DIM, '[Y/n/diff]')}",
        f"  {A.color(A.GRAY_DIM, '> ')} {A.color(A.GREEN_OK, '↵')}",
        post=0.4,
    )

    cast.section_break(0.4)

    # 6. The summary — 4 questions vs 27
    cast.lines(
        ok(f"Wrote {A.color(A.BLUE_ACCENT, 'contract.fluid.yaml')}"),
        ok(f"Wrote {A.color(A.BLUE_ACCENT, 'contract.fluid.yaml.model.md')}"),
        ok(f"Persisted memory ({A.color(A.AMBER, '12.4 KB')})"),
        post=0.3,
    )
    cast.lines(
        f"  {A.color(A.GRAY_DIM, '─────────────────────────────────────────────────────────────')}",
        f"  {A.color(A.BOLD, '4 questions answered.')} {A.color(A.GRAY_DIM, '(Most CLIs ask 27.)')}",
        f"  {A.color(A.BOLD, '47 ms scan')} replaced 23 of them. {A.color(A.BOLD, 'Domain inference')} replaced 4.",
        f"  {A.color(A.BOLD, '$0.021 spent')} of {A.color(A.GRAY_DIM, '$0.050 cap')}.",
        post=0.5,
    )

    cast.prompt()
    return cast


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/casts/guided-forge-ux.cast"
    cast = build()
    cast.write(out)
    print(f"guided-forge-ux: {cast.duration:.1f}s → {out}")
