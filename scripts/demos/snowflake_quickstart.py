#!/usr/bin/env python3
"""Snowflake quickstart — dry, scripted (no live calls)."""

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from cast_builder import Cast, A, ok, working, info  # type: ignore


def build() -> Cast:
    cast = Cast(
        width=92, height=24,
        title="FLUID Forge — Snowflake quickstart",
        pace="readable",
    )

    cast.run(
        'pipx install "data-product-forge[snowflake]"',
        f"  installed package {A.color(A.BLUE_ACCENT, 'data-product-forge 0.8.0')}, Python 3.13",
        f"  added providers: {A.color(A.BLUE_ACCENT, 'snowflake')} (Snowflake + Snowpark + dbt)",
        output_post=0.18,
    )

    # Env file (no values shown)
    cast.prompt()
    cast.typed("cat > .env <<'EOF'")
    cast.enter()
    cast.lines(
        "SNOWFLAKE_ACCOUNT=acme-demo",
        "SNOWFLAKE_USER=demo_user",
        f"SNOWFLAKE_PASSWORD={A.color(A.GRAY_DIM, '••••••••')}",
        "SNOWFLAKE_WAREHOUSE=COMPUTE_WH",
        "SNOWFLAKE_ROLE=SYSADMIN",
        "EOF",
        post=0.18,
    )
    cast.section_break(0.4)

    cast.prompt()
    cast.typed("set -a; . .env; set +a")
    cast.enter()
    cast.section_break(0.4)

    cast.prompt()
    cast.typed("yq -i '.exposes[0].binding.platform = \"snowflake\"' contract.fluid.yaml")
    cast.enter()
    cast.section_break(0.4)

    cast.run(
        "fluid validate contract.fluid.yaml --strict",
        ok("Schema 0.7.2 — passed"),
        ok(f"binding.platform={A.color(A.BLUE_ACCENT, 'snowflake')} — supported"),
        ok("binding.location complete (database, schema, table)"),
        ok("accessPolicy.grants — 1 RBAC grant compiles"),
        f"  {A.color(A.BRIGHT_GREEN, '✓ Contract validation passed (strict)')}",
        output_post=0.16,
    )

    cast.run(
        "fluid plan contract.fluid.yaml --env prod",
        info(f"Provider: {A.color(A.BLUE_ACCENT, 'snowflake')} (account=acme-demo)"),
        f"  {A.color(A.BOLD, 'Plan summary:')}",
        f"    {A.color(A.GREEN_OK, '+')} ensure  database   PROD",
        f"    {A.color(A.GREEN_OK, '+')} ensure  schema     PROD.GOLD",
        f"    {A.color(A.GREEN_OK, '+')} create  table      PROD.GOLD.BITCOIN_PRICES",
        f"    {A.color(A.GREEN_OK, '+')} grant   SELECT     ANALYST_ROLE",
        f"  {A.color(A.DIM, '(this is the dry/scripted demo — no live Snowflake calls)')}",
        output_post=0.15,
    )

    cast.run(
        "fluid apply contract.fluid.yaml --env prod --mode dry-run",
        working("Connecting to Snowflake account=acme-demo..."),
        output_post=0.32,
    )
    cast.lines(ok("Connected as demo_user (role=SYSADMIN, warehouse=COMPUTE_WH)"), post=0.18)
    cast.lines(info("--mode dry-run — rendering DDL, not executing"), post=0.3)
    cast.lines(
        f"  {A.color(A.GRAY_DIM, '──────────────────────────────────────────────────────────')}",
        f"  {A.color(A.BLUE_ACCENT, 'CREATE DATABASE IF NOT EXISTS PROD;')}",
        f"  {A.color(A.BLUE_ACCENT, 'CREATE SCHEMA   IF NOT EXISTS PROD.GOLD;')}",
        f"  {A.color(A.BLUE_ACCENT, 'CREATE OR REPLACE TABLE PROD.GOLD.BITCOIN_PRICES ( ... );')}",
        f"  {A.color(A.BLUE_ACCENT, 'GRANT SELECT ON PROD.GOLD.BITCOIN_PRICES TO ROLE ANALYST_ROLE;')}",
        f"  {A.color(A.GRAY_DIM, '──────────────────────────────────────────────────────────')}",
        post=0.18,
    )
    cast.output(f"  {A.color(A.BRIGHT_GREEN, '✓ Dry-run complete (no DDL fired)')}", post=0.4)
    cast.output("", post=0.0)
    cast.output(f"  {A.color(A.DIM, 'Run without --mode dry-run to execute. See snowflake-real cast for the live flow.')}", post=0.4)

    cast.section_break(0.6)
    cast.prompt()
    return cast


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/casts/snowflake-quickstart.cast"
    cast = build()
    cast.write(out)
    print(f"snowflake-quickstart: {cast.duration:.1f}s → {out}")
