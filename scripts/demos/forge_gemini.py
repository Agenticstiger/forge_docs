#!/usr/bin/env python3
"""
forge-gemini — high-fidelity scripted demo of the AI copilot flow.

The real-API capture (preserved at forge_gemini_real_capture.py) showed
that the CLI's actual output during `fluid forge --llm-provider gemini`
is mostly a spinner cycling — most of the AI flow happens inside the
streaming response and isn't surfaced as readable lines.

This scripted version shows what the workflow IS, end-to-end, so a
viewer can see the agent reasoning, memory loading, domain-pack hints,
streaming contract generation, validation gates, and the agentPolicy
emerging — frame-perfect for documentation.

Run this for a documentation demo. Run forge_gemini_real_capture.py
to capture a real Gemini call.
"""

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from cast_builder import Cast, A, ok, working, info  # type: ignore


def build() -> Cast:
    cast = Cast(
        width=92, height=28,
        title="fluid forge --domain finance --llm-provider gemini --llm-model gemini-2.5-flash",
        # Slightly tighter typing for the long command (it'd otherwise feel slow)
        char_min=0.020, char_max=0.040,
        pace="readable",  # dense narrative — agent / memory / contract emit
    )

    # 1. Type the command
    cast.run(
        'fluid forge --domain finance --provider snowflake \\\n'
        '  --llm-provider gemini --llm-model gemini-2.5-flash \\\n'
        '  --target-dir ./customer-360-product',
        section=False,
    )

    # 2. Banner
    cast.lines(
        f"  {A.color(A.PURPLE_AI, '✨')} {A.color(A.BOLD, 'fluid forge')} — AI-powered data product creation",
        f"  {A.color(A.GRAY_DIM, '──────────────────────────────────────────────────────────────────')}",
        post=0.3,
    )

    # 3. Memory + domain expertise
    cast.lines(
        f"  {A.color(A.BLUE_ACCENT, 'ℹ')} Loading project memory from {A.color(A.BLUE_ACCENT, 'runtime/.state/copilot-memory.json')}",
        post=0.3,
    )
    cast.lines(
        ok("Project memory loaded — 3 prior generations, customer-360 vocabulary cached"),
        post=0.18,
    )
    cast.lines(
        f"  {A.color(A.BLUE_ACCENT, 'ℹ')} Loading domain expertise pack: {A.color(A.AMBER, 'finance')}",
        post=0.3,
    )
    cast.lines(
        ok("Loaded SOX + GDPR regulatory framework defaults"),
        ok("Loaded denied use cases: ['training', 'fine-tuning', 'profiling']"),
        ok("Loaded 18 finance-domain field hints (PII shape, currency types, retention)"),
        post=0.18,
    )

    cast.section_break(0.5)

    # 4. Discovery
    cast.lines(
        f"  {A.color(A.BLUE_ACCENT, 'ℹ')} Discovering local context...",
        post=0.3,
    )
    cast.lines(
        ok(f"Scanned {A.color(A.BLUE_ACCENT, './data')} — found 2 CSVs (customers, transactions)"),
        ok(f"Scanned {A.color(A.BLUE_ACCENT, './sql')} — found 3 dbt models (customer_metrics, ltv_30d, churn_score)"),
        ok(f"Inferred 17 fields, 4 PII candidates (email, phone, ssn, dob)"),
        post=0.18,
    )

    cast.section_break(0.5)

    # 5. Calling Gemini
    cast.lines(
        f"  {A.color(A.PURPLE_AI, '🧠')} Calling {A.color(A.BOLD, 'gemini-2.5-flash')} with finance-domain prompt...",
        post=0.45,
    )
    # Show streaming spinner briefly (3-4 frames of the asciinema-style spinner)
    cast.lines(f"  {A.color(A.YELLOW_WARN, '⠋')} Streaming...", post=0.18)
    cast.lines(f"  {A.color(A.YELLOW_WARN, '⠙')} Streaming...", post=0.16)
    cast.lines(f"  {A.color(A.YELLOW_WARN, '⠹')} Streaming...", post=0.14)
    cast.lines(f"  {A.color(A.YELLOW_WARN, '⠸')} Streaming... (1834 tokens)", post=0.5)
    cast.section_break(0.4)

    # 6. The contract emerges, block by block
    cast.lines(
        f"  {A.color(A.BRIGHT_GREEN, '✓ Generated contract.fluid.yaml')} ({A.color(A.DIM, '147 lines, 4.2 KB')})",
        post=0.3,
    )

    cast.lines(
        f"  {A.color(A.GRAY_DIM, '┌─────────────────────────────────────────────────────────────────┐')}",
        f"  {A.color(A.GRAY_DIM, '│')} {A.color(A.BLUE_ACCENT, 'fluidVersion:')} {A.color(A.AMBER, chr(34) + '0.7.2' + chr(34))}                                          {A.color(A.GRAY_DIM, '│')}",
        f"  {A.color(A.GRAY_DIM, '│')} {A.color(A.BLUE_ACCENT, 'kind:')} DataProduct                                              {A.color(A.GRAY_DIM, '│')}",
        f"  {A.color(A.GRAY_DIM, '│')} {A.color(A.BLUE_ACCENT, 'id:')} gold.finance.customer_360_v1                              {A.color(A.GRAY_DIM, '│')}",
        f"  {A.color(A.GRAY_DIM, '│')} {A.color(A.BLUE_ACCENT, 'name:')} Customer 360 — Finance                                  {A.color(A.GRAY_DIM, '│')}",
        f"  {A.color(A.GRAY_DIM, '│')} {A.color(A.BLUE_ACCENT, 'domain:')} finance                                                {A.color(A.GRAY_DIM, '│')}",
        f"  {A.color(A.GRAY_DIM, '├─────────────────────────────────────────────────────────────────┤')}",
        f"  {A.color(A.GRAY_DIM, '│')} {A.color(A.PURPLE_AI, '🤖')} AI generated 11 schema fields with PII tagging              {A.color(A.GRAY_DIM, '│')}",
        f"  {A.color(A.GRAY_DIM, '│')} {A.color(A.PURPLE_AI, '🤖')} AI generated 4 dq.rules (completeness, freshness, drift)    {A.color(A.GRAY_DIM, '│')}",
        f"  {A.color(A.GRAY_DIM, '│')} {A.color(A.PURPLE_AI, '🤖')} AI generated 3 accessPolicy.grants (RBAC roles)             {A.color(A.GRAY_DIM, '│')}",
        f"  {A.color(A.GRAY_DIM, '│')} {A.color(A.PURPLE_AI, '🤖')} AI generated agentPolicy with finance-domain defaults       {A.color(A.GRAY_DIM, '│')}",
        f"  {A.color(A.GRAY_DIM, '│')} {A.color(A.PURPLE_AI, '🤖')} AI generated sovereignty (jurisdiction=EU, GDPR enforced)   {A.color(A.GRAY_DIM, '│')}",
        f"  {A.color(A.GRAY_DIM, '└─────────────────────────────────────────────────────────────────┘')}",
        post=0.18,
    )

    cast.section_break(0.4)

    # 7. agentPolicy preview (the hero block for this demo)
    cast.lines(
        f"  {A.color(A.BOLD, '📋 agentPolicy block')} ({A.color(A.DIM, 'gates which AI models can read this product')})",
        post=0.3,
    )
    cast.lines(
        f"  {A.color(A.BLUE_ACCENT, 'agentPolicy:')}",
        f"    {A.color(A.BLUE_ACCENT, 'allowedModels:')} [{A.color(A.AMBER, 'gpt-4')}, {A.color(A.AMBER, 'claude-3-opus')}, {A.color(A.AMBER, 'gemini-2.5-flash')}]",
        f"    {A.color(A.BLUE_ACCENT, 'allowedUseCases:')} [{A.color(A.AMBER, 'analysis')}, {A.color(A.AMBER, 'reporting')}, {A.color(A.AMBER, 'qa')}]",
        f"    {A.color(A.BLUE_ACCENT, 'deniedUseCases:')} [{A.color(A.RED_ERR, 'training')}, {A.color(A.RED_ERR, 'fine-tuning')}, {A.color(A.RED_ERR, 'profiling')}]",
        f"    {A.color(A.BLUE_ACCENT, 'maxTokensPerRequest:')} 4000",
        f"    {A.color(A.BLUE_ACCENT, 'canStore:')} false           {A.color(A.GRAY_DIM, '# ephemeral reads only')}",
        f"    {A.color(A.BLUE_ACCENT, 'auditRequired:')} true       {A.color(A.GRAY_DIM, '# every read logged to platform audit trail')}",
        post=0.16,
    )

    cast.section_break(0.5)

    # 8. Validation gate
    cast.lines(
        f"  {A.color(A.BOLD, '🔍 Auto-validation')}",
        post=0.3,
    )
    cast.lines(working("Running fluid validate against fluid-schema-0.7.2.json..."), post=0.4)
    cast.lines(ok("Schema 0.7.2 — passed (all required fields present)"), post=0.16)
    cast.lines(ok("agentPolicy fields valid (allowedModels enum recognized)"), post=0.16)
    cast.lines(ok("sovereignty.jurisdiction=EU compatible with binding.location.region=eu-central-1"), post=0.16)
    cast.lines(ok("dq.rules all reference real schema fields"), post=0.16)
    cast.lines(f"  {A.color(A.BRIGHT_GREEN, '✓ Contract validation passed')}", post=0.3)

    cast.section_break(0.5)

    # 9. Memory persisted
    cast.lines(
        ok(f"Persisted generation to {A.color(A.BLUE_ACCENT, 'runtime/.state/copilot-memory.json')}"),
        ok(f"Wrote contract → {A.color(A.BLUE_ACCENT, './customer-360-product/contract.fluid.yaml')}"),
        post=0.3,
    )

    cast.section_break(0.5)

    # 10. Next steps
    cast.lines(
        f"  {A.color(A.BRIGHT_GREEN, '✅ Next steps')}",
        f"  {A.color(A.GRAY_DIM, '─────────────────────────────────')}",
        f"    {A.color(A.GREEN_OK, '$')} cd customer-360-product",
        f"    {A.color(A.GREEN_OK, '$')} fluid plan contract.fluid.yaml --html",
        f"    {A.color(A.GREEN_OK, '$')} fluid apply contract.fluid.yaml --mode dry-run --yes",
        f"    {A.color(A.GREEN_OK, '$')} fluid policy-apply --mode check",
        post=0.18,
    )

    cast.section_break(0.6)

    cast.lines(
        f"  {A.color(A.DIM, '💡 1834 tokens · $0.0021 estimated cost · 11.4 s end-to-end')}",
        post=0.5,
    )

    cast.prompt()
    return cast


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/casts/forge-gemini.cast"
    cast = build()
    cast.write(out)
    print(f"forge-gemini: {cast.duration:.1f}s → {out}")
