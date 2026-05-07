#!/usr/bin/env python3
"""
agent-policy — high-fidelity scripted demo of agentPolicy enforcement.

Shows the actual concept the docs page is teaching: what an agentPolicy
block looks like in YAML, how `fluid validate` confirms its shape, how
`fluid policy-check` reports which models / use-cases are gated, and what
happens at runtime when an agent tries to read data — one allowed, one
blocked. All scripted at frame-perfect fidelity to what the real CLI
produces; no live calls.
"""

import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from cast_builder import Cast, A, ok, working, info, err  # type: ignore


def build() -> Cast:
    cast = Cast(
        width=92, height=26,
        title="agentPolicy — declare, validate, gate (fluid validate → policy-check → audit)",
        pace="readable",
    )

    # 1. Show the agentPolicy block in the contract
    cast.run(
        "cat contract.fluid.yaml | yq '.agentPolicy'",
        f"  {A.color(A.GRAY_DIM, '──────────────────────────────────────────────')}",
        f"  {A.color(A.BLUE_ACCENT, 'allowedModels:')}",
        f"    {A.color(A.AMBER, '- gpt-4')}",
        f"    {A.color(A.AMBER, '- claude-3-opus')}",
        f"    {A.color(A.AMBER, '- gemini-2.5-flash')}",
        f"  {A.color(A.BLUE_ACCENT, 'allowedUseCases:')}",
        f"    {A.color(A.AMBER, '- analysis')}",
        f"    {A.color(A.AMBER, '- summarization')}",
        f"    {A.color(A.AMBER, '- qa')}",
        f"  {A.color(A.BLUE_ACCENT, 'deniedUseCases:')}",
        f"    {A.color(A.RED_ERR, '- training')}",
        f"    {A.color(A.RED_ERR, '- fine-tuning')}",
        f"    {A.color(A.RED_ERR, '- profiling')}",
        f"  {A.color(A.BLUE_ACCENT, 'maxTokensPerRequest:')} 4000",
        f"  {A.color(A.BLUE_ACCENT, 'canStore:')} false              {A.color(A.GRAY_DIM, '# ephemeral reads only')}",
        f"  {A.color(A.BLUE_ACCENT, 'auditRequired:')} true          {A.color(A.GRAY_DIM, '# every read logged')}",
        f"  {A.color(A.GRAY_DIM, '──────────────────────────────────────────────')}",
        output_post=0.18,
    )

    # 2. Validate the contract (with agentPolicy)
    cast.run(
        "fluid validate contract.fluid.yaml --strict",
        ok("Schema 0.7.2 — passed"),
        ok("agentPolicy.allowedModels — 3 enum values recognized"),
        ok("agentPolicy.deniedUseCases — 3 enum values recognized"),
        ok("agentPolicy.maxTokensPerRequest — within int range"),
        ok("agentPolicy.canStore=false — caching disabled"),
        ok("agentPolicy.auditRequired=true — audit trail mandatory"),
        f"  {A.color(A.BRIGHT_GREEN, '✓ Contract validation passed (strict)')}",
        output_post=0.16,
    )

    # 3. Policy-check shows what would be enforced
    cast.run(
        "fluid policy-check contract.fluid.yaml --report agentPolicy",
        f"  {A.color(A.BOLD, '🛡  agentPolicy enforcement summary')}",
        f"  {A.color(A.GRAY_DIM, '──────────────────────────────────────────────')}",
        f"  {A.color(A.BOLD, 'Models')}     {A.color(A.GREEN_OK, '3 allowed')}, {A.color(A.RED_ERR, 'all others denied')}",
        f"  {A.color(A.BOLD, 'Use cases')}  {A.color(A.GREEN_OK, '3 allowed')}, {A.color(A.RED_ERR, '3 explicitly denied')}",
        f"  {A.color(A.BOLD, 'Storage')}    {A.color(A.RED_ERR, 'no caching')} — every read is fresh",
        f"  {A.color(A.BOLD, 'Audit')}      {A.color(A.GREEN_OK, 'every read logged')} (auditRequired=true)",
        f"  {A.color(A.BOLD, 'Limits')}     {A.color(A.AMBER, 'maxTokensPerRequest=4000')}",
        f"  {A.color(A.GRAY_DIM, '──────────────────────────────────────────────')}",
        ok("All 11 schema fields covered by agentPolicy gates"),
        ok(f"PII-tagged columns ({A.color(A.AMBER, 'email')}, {A.color(A.AMBER, 'phone')}, {A.color(A.AMBER, 'ssn')}) auto-masked at read"),
        f"  {A.color(A.BRIGHT_GREEN, '✓ agentPolicy ready to enforce')}",
        output_post=0.18,
    )

    # 4. Simulated agent read attempts — the runtime in action
    cast.lines(
        f"  {A.color(A.BOLD, '🤖 Simulated agent reads')}  {A.color(A.GRAY_DIM, '(fluid agent-audit --replay)')}",
        f"  {A.color(A.GRAY_DIM, '──────────────────────────────────────────────')}",
        post=0.3,
    )

    cast.lines(
        f"  {A.color(A.GREEN_OK, '✓ ALLOW')}  {A.color(A.AMBER, 'gpt-4')} · use-case={A.color(A.AMBER, 'analysis')} · 312 tokens",
        f"            agent={A.color(A.BLUE_ACCENT, 'svc:bi-dashboard')} · audit-id={A.color(A.GRAY_DIM, 'aud_8f2…')}",
        post=0.3,
    )
    cast.lines(
        f"  {A.color(A.RED_ERR, '✗ DENY')}   {A.color(A.AMBER, 'claude-3-opus')} · use-case={A.color(A.RED_ERR, 'training')}",
        f"            reason: {A.color(A.RED_ERR, 'use-case in agentPolicy.deniedUseCases')}",
        f"            agent={A.color(A.BLUE_ACCENT, 'svc:research-pipeline')} · audit-id={A.color(A.GRAY_DIM, 'aud_8f3…')}",
        post=0.3,
    )
    cast.lines(
        f"  {A.color(A.RED_ERR, '✗ DENY')}   {A.color(A.AMBER, 'mixtral-8x7b')} · use-case={A.color(A.AMBER, 'qa')}",
        f"            reason: {A.color(A.RED_ERR, 'model not in agentPolicy.allowedModels')}",
        f"            agent={A.color(A.BLUE_ACCENT, 'svc:experimental-bot')} · audit-id={A.color(A.GRAY_DIM, 'aud_8f4…')}",
        post=0.3,
    )
    cast.lines(
        f"  {A.color(A.GREEN_OK, '✓ ALLOW')}  {A.color(A.AMBER, 'gemini-2.5-flash')} · use-case={A.color(A.AMBER, 'summarization')} · 1102 tokens",
        f"            agent={A.color(A.BLUE_ACCENT, 'svc:weekly-digest')} · audit-id={A.color(A.GRAY_DIM, 'aud_8f5…')}",
        post=0.3,
    )

    cast.section_break(0.5)
    cast.lines(
        f"  {A.color(A.GRAY_DIM, '──────────────────────────────────────────────')}",
        f"  {A.color(A.BOLD, 'Last 24 h:')}  {A.color(A.GREEN_OK, '4,182 allow')}  ·  {A.color(A.RED_ERR, '21 deny')}  ·  {A.color(A.AMBER, '0 unaudited')}",
        post=0.5,
    )

    cast.prompt()
    return cast


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/casts/agent-policy.cast"
    cast = build()
    cast.write(out)
    print(f"agent-policy: {cast.duration:.1f}s → {out}")
