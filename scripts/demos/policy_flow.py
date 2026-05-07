#!/usr/bin/env python3
"""policy-check + policy-apply --mode check — local policy compilation."""

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from cast_builder import Cast, A, ok, working, info, err  # type: ignore


def build() -> Cast:
    cast = Cast(
        width=92, height=22,
        title="FLUID Forge — policy-check → policy-apply --mode check",
        pace="readable",
    )

    cast.run(
        "fluid policy-check contract.fluid.yaml --strict",
        f"  {A.color(A.BOLD, '🛡  Policy check')}",
        f"  {A.color(A.GRAY_DIM, '─────────────────────────────────────────')}",
        ok("accessPolicy.grants — 3 grants validated"),
        ok("Principal formats valid (group:, serviceAccount:)"),
        ok("Permissions are real for binding.platform=gcp"),
        ok("agentPolicy — allowedModels enum recognized"),
        ok("sovereignty.jurisdiction=EU — compatible with binding.location.region=europe-west3"),
        f"  {A.color(A.BRIGHT_GREEN, '✓ Policy check passed (strict)')}",
        output_post=0.16,
    )

    cast.run(
        "fluid generate artifacts contract.fluid.yaml --out artifacts/",
        info("Compiling accessPolicy → native cloud IAM..."),
        ok(f"artifacts/policy/{A.color(A.BLUE_ACCENT, 'bindings.json')} (3 IAM bindings)"),
        ok(f"artifacts/policy/{A.color(A.BLUE_ACCENT, 'opa-policies.rego')} (1 OPA rule)"),
        ok(f"artifacts/standards/{A.color(A.BLUE_ACCENT, 'product.odcs.yaml')}"),
        ok(f"artifacts/standards/{A.color(A.BLUE_ACCENT, 'product.opds.json')}"),
        f"  {A.color(A.BRIGHT_GREEN, '✓ 4 artifacts generated')}",
        output_post=0.16,
    )

    cast.run(
        "fluid policy-apply artifacts/policy/bindings.json --mode check",
        info(f"Loaded 3 binding(s) — running in {A.color(A.YELLOW_WARN, '--mode check')} (no live IAM calls)"),
        f"  {A.color(A.GRAY_DIM, '─────────────────────────────────────────')}",
        f"  {A.color(A.GREEN_OK, '+')} would-grant  group:analysts@company.com         → roles/bigquery.dataViewer",
        f"  {A.color(A.GREEN_OK, '+')} would-grant  group:data-engineering@company.com → roles/bigquery.dataOwner",
        f"  {A.color(A.GREEN_OK, '+')} would-grant  serviceAccount:bi@my-project       → roles/bigquery.dataViewer",
        f"  {A.color(A.GRAY_DIM, '─────────────────────────────────────────')}",
        ok("All bindings would apply cleanly"),
        ok("No drift detected vs deployed policy"),
        f"  {A.color(A.BRIGHT_GREEN, '✓ Policy check-only complete — re-run with --mode enforce to apply')}",
        output_post=0.18,
    )

    cast.section_break(0.6)
    cast.prompt()
    return cast


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/casts/policy-flow.cast"
    cast = build()
    cast.write(out)
    print(f"policy-flow: {cast.duration:.1f}s → {out}")
