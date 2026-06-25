#!/usr/bin/env python3
"""Local DuckDB quickstart — install → init → validate → plan → apply.

Depicts the real ``fluid init --quickstart`` path: it is rewritten
internally to ``--template customer-360`` and scaffolds the Customer 360
Analytics template (contract.fluid.yaml + data/*.csv sample data).
"""

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from cast_builder import Cast, A, ok, working, info  # type: ignore


def build() -> Cast:
    cast = Cast(
        width=92, height=24,
        title="FLUID Forge — local quickstart (~30 s)",
    )

    # 1. Install
    cast.run(
        'pipx install "data-product-forge[local]"',
        f"  installed package {A.color(A.BLUE_ACCENT, 'data-product-forge 0.9.0')}, Python 3.13",
        "  These apps are now globally available",
        f"    - {A.color(A.BOLD, 'fluid')}",
        output_post=0.18,
    )

    # 2. Init — --quickstart scaffolds the customer-360 template
    cast.run(
        "fluid init my-project --quickstart",
        f"  {A.color(A.PURPLE_AI, '📦')} Creating from template: {A.color(A.BOLD, 'customer-360')}",
        ok(f"Generated {A.color(A.BLUE_ACCENT, 'contract.fluid.yaml')} — Customer 360 Analytics"),
        ok(f"Sample data {A.color(A.DIM, '→')} {A.color(A.BLUE_ACCENT, 'data/customers.csv · orders.csv · interactions.csv')}"),
        ok("Created project from customer-360 template"),
        output_post=0.18,
    )

    # 3. cd + validate
    cast.run(
        "cd my-project && fluid validate contract.fluid.yaml",
        ok(f"Schema {A.color(A.AMBER, '0.7.2')} — passed"),
        ok("Required fields complete (fluidVersion, kind, id, name, metadata, exposes)"),
        ok(f"binding.platform={A.color(A.BLUE_ACCENT, 'local')} — supported by installed providers"),
        ok("dq.rules valid (5 rules: uniqueness, valid_values ×2, accuracy ×2)"),
        f"  {A.color(A.BRIGHT_GREEN, '✓ Contract validation passed')}",
        output_post=0.16,
    )

    # 4. Plan
    cast.run(
        "fluid plan contract.fluid.yaml",
        info("Reading contract → resolving 2 exposes, 1 build"),
        info("Provider: local (DuckDB)"),
        f"  {A.color(A.BOLD, 'Plan summary:')}",
        f"    {A.color(A.GREEN_OK, '+')} create  table    customer_360_master",
        f"    {A.color(A.GREEN_OK, '+')} create  view     high_value_customers",
        f"    {A.color(A.GREEN_OK, '+')} run     build    customer_360_pipeline (sql · 5 stages)",
        f"    {A.color(A.GREEN_OK, '+')} write   parquet  output/customer_360.parquet",
        f"    {A.color(A.GREEN_OK, '+')} write   parquet  output/high_value_customers.parquet",
        f"  {A.color(A.DIM, '(no destructive actions; dry-run safe)')}",
        output_post=0.15,
    )

    # 5. Apply
    cast.run(
        "fluid apply contract.fluid.yaml --yes",
        working("Reading sources: customers.csv, orders.csv, interactions.csv..."),
        output_post=0.32,
    )
    cast.lines(
        working(f"Running {A.color(A.BLUE_ACCENT, 'customer_360_pipeline')} — 5-stage SQL build"),
        post=0.36,
    )
    cast.lines(
        working(f"Writing {A.color(A.BLUE_ACCENT, 'output/customer_360.parquet')}"),
        post=0.45,
    )
    cast.output(f"  {A.color(A.BRIGHT_GREEN, '✓ Pipeline complete in 1.42 s')}", post=0.4)
    cast.output("", post=0.0)

    cast.output(f"  {A.color(A.BOLD, '📦 Data product live:')} gold.customer.analytics_360_v1", post=0.18)
    cast.output(f"  {A.color(A.DIM, '📍 output/customer_360.parquet (10 rows · 14 cols)')}", post=0.4)

    cast.section_break(0.6)
    cast.prompt()
    return cast


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/casts/local-quickstart.cast"
    cast = build()
    cast.write(out)
    print(f"local-quickstart: {cast.duration:.1f}s → {out}")
