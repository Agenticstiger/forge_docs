#!/usr/bin/env python3
"""forge --blank --domain finance — interview shape only, no LLM."""

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from cast_builder import Cast, A, ok, working, info  # type: ignore


def build() -> Cast:
    cast = Cast(width=92, height=22, title="FLUID Forge — fluid forge --blank --domain finance (~22 s)")

    cast.run(
        "fluid forge --blank --domain finance --target-dir my-finance-product",
        f"  {A.color(A.PURPLE_AI, '✨')} {A.color(A.BOLD, 'fluid forge')} — AI-powered data product creation",
        f"  {A.color(A.DIM, '─────────────────────────────────────────────────')}",
        f"  Domain: {A.color(A.BLUE_ACCENT, 'finance')} (regulated analytics, fraud, compliance)",
        f"  Mode:   {A.color(A.BLUE_ACCENT, '--blank')} (no LLM, structured stub only)",
        output_post=0.22,
    )

    cast.lines(
        f"  {A.color(A.PURPLE_AI, '🎯')} Generating finance-domain skeleton...",
        post=0.4,
    )

    cast.lines(
        ok(f"Created {A.color(A.BLUE_ACCENT, 'my-finance-product/contract.fluid.yaml')} with finance defaults"),
        ok(f"Pre-seeded {A.color(A.BLUE_ACCENT, 'sovereignty.regulatoryFramework')} = ['SOX', 'GDPR']"),
        ok(f"Pre-seeded {A.color(A.BLUE_ACCENT, 'agentPolicy.deniedUseCases')} = ['training', 'fine-tuning']"),
        ok(f"Pre-seeded {A.color(A.BLUE_ACCENT, 'metadata.layer')} = 'Gold' (finance defaults to Gold)"),
        post=0.18,
    )

    cast.section_break(0.6)

    cast.lines(
        f"  {A.color(A.BOLD, '📋 Next steps')} — fill in the blanks:",
        f"    1. Add at least one {A.color(A.BLUE_ACCENT, 'expose')} block describing your output",
        f"    2. Define the schema fields (transactions, balance, etc.)",
        f"    3. Set {A.color(A.BLUE_ACCENT, 'binding.platform')} to your target cloud",
        f"    4. Run {A.color(A.GREEN_OK, 'fluid validate contract.fluid.yaml')}",
        post=0.18,
    )
    cast.section_break(0.5)

    cast.lines(
        f"  {A.color(A.DIM, '💡 Want the AI to fill these in automatically?')}",
        f"  {A.color(A.DIM, '   Re-run without --blank: fluid forge --domain finance')}",
        post=0.5,
    )

    cast.section_break(0.6)
    cast.prompt()
    return cast


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/casts/forge-blank.cast"
    cast = build()
    cast.write(out)
    print(f"forge-blank: {cast.duration:.1f}s → {out}")
