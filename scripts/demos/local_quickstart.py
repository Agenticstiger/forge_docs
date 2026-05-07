#!/usr/bin/env python3
"""Local DuckDB quickstart — install → init → validate → plan → apply."""

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from cast_builder import Cast, A, ok, working, info, header, success  # type: ignore


def build() -> Cast:
    cast = Cast(
        width=92, height=24,
        title="FLUID Forge — local quickstart (~30 s)",
    )

    # 1. Install
    cast.run(
        'pipx install "data-product-forge[local]"',
        f"  installed package {A.color(A.BLUE_ACCENT, 'data-product-forge 0.8.0')}, Python 3.13",
        "  These apps are now globally available",
        f"    - {A.color(A.BOLD, 'fluid')}",
        output_post=0.18,
    )

    # 2. Init
    cast.run(
        "fluid init btc-tracker --quickstart",
        f"  {A.color(A.PURPLE_AI, '✨')} Creating new FLUID project: {A.color(A.BOLD, 'btc-tracker')}",
        ok(f"Generated {A.color(A.BLUE_ACCENT, 'contract.fluid.yaml')} (Bitcoin tracker template)"),
        ok(f"Generated sample data {A.color(A.DIM, '→')} {A.color(A.BLUE_ACCENT, 'data/btc.csv')}"),
        ok("Initialized DuckDB workspace"),
        output_post=0.18,
    )

    # 3. cd + validate
    cast.run(
        "cd btc-tracker && fluid validate contract.fluid.yaml",
        ok(f"Schema {A.color(A.AMBER, '0.7.2')} — passed"),
        ok("Required fields complete (fluidVersion, kind, id, name, metadata, exposes)"),
        ok(f"binding.platform={A.color(A.BLUE_ACCENT, 'local')} — supported by installed providers"),
        ok("dq.rules valid (3 rules: completeness, freshness, valid_values)"),
        f"  {A.color(A.BRIGHT_GREEN, '✓ Contract validation passed')}",
        output_post=0.16,
    )

    # 4. Plan
    cast.run(
        "fluid plan contract.fluid.yaml",
        info("Reading contract → resolving 1 expose, 1 build"),
        info("Provider: local (DuckDB)"),
        f"  {A.color(A.BOLD, 'Plan summary:')}",
        f"    {A.color(A.GREEN_OK, '+')} create  table  bitcoin_prices",
        f"    {A.color(A.GREEN_OK, '+')} run     build  bitcoin_price_ingestion (sql)",
        f"    {A.color(A.GREEN_OK, '+')} write   parquet runtime/out/bitcoin_prices.parquet",
        f"  {A.color(A.DIM, '(no destructive actions; dry-run safe)')}",
        output_post=0.15,
    )

    # 5. Apply
    cast.run(
        "fluid apply contract.fluid.yaml --yes",
        working("Reading sources..."),
        output_post=0.32,
    )
    cast.lines(
        working(f"Running transformation: {A.color(A.BLUE_ACCENT, 'bitcoin_price_ingestion')}"),
        post=0.36,
    )
    cast.lines(
        working(f"Writing {A.color(A.BLUE_ACCENT, 'runtime/out/bitcoin_prices.parquet')}"),
        post=0.45,
    )
    cast.output(f"  {A.color(A.BRIGHT_GREEN, '✓ Pipeline complete in 1.42 s')}", post=0.4)
    cast.output("", post=0.0)

    cast.output(f"  {A.color(A.BOLD, '📦 Data product live:')} gold.crypto.bitcoin_tracker_v1", post=0.18)
    cast.output(f"  {A.color(A.DIM, '📍 runtime/out/bitcoin_prices.parquet (24 rows · 3 cols)')}", post=0.4)

    cast.section_break(0.6)
    cast.prompt()
    return cast


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/casts/local-quickstart.cast"
    cast = build()
    cast.write(out)
    print(f"local-quickstart: {cast.duration:.1f}s → {out}")
