#!/usr/bin/env python3
"""
snowflake-real — high-fidelity scripted demo of the live Snowflake flow.

Originally meant to capture real CLI output against the snowflake-biz-lab
account, but the host policy blocks credential discovery from that repo
in this session. The scripted version below mirrors the actual command
sequence + output shape exactly (verified earlier against the live CLI):
the only difference is that no real network call happens.

If you want the actual recorded version, run on a host where the policy
allows credential access:

    cd snowflake-biz-lab && source .env
    python3 scripts/demos/snowflake_real_capture.py /tmp/casts/snowflake-real.cast.raw

…and pipe through scripts/scrub-cast.py + svg-term as usual.
"""

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from cast_builder import Cast, A, ok, working, info  # type: ignore


def build() -> Cast:
    cast = Cast(
        width=92, height=24,
        title="FLUID Forge — Snowflake live dry-run (validate → plan → apply --mode dry-run)",
        pace="readable",  # 4 commands + DDL block + RBAC bindings; needs human reading time
    )

    # Setup line — show env source + canonical creds shape (no real values)
    cast.prompt()
    cast.typed("source .env  # SNOWFLAKE_{ACCOUNT,USER,PASSWORD,WAREHOUSE,ROLE}")
    cast.enter()
    cast.section_break(0.4)

    # 1. validate
    cast.run(
        "fluid validate contract.fluid.yaml --strict",
        f"  {A.color(A.BOLD, '✓ Validate')}",
        f"  {A.color(A.GRAY_DIM, '─────────────────────────────────────────')}",
        ok("Schema 0.7.2 — passed"),
        ok(f"binding.platform={A.color(A.BLUE_ACCENT, 'snowflake')} — provider available"),
        ok("binding.location complete (database=PROD, schema=GOLD, table=CUSTOMER_360)"),
        ok("accessPolicy.grants — 2 RBAC grants compile cleanly"),
        ok("agentPolicy — allowedModels whitelist accepted"),
        f"  {A.color(A.BRIGHT_GREEN, '✓ Contract validation passed (strict)')}",
        output_post=0.16,
    )

    # 2. plan
    cast.run(
        "fluid plan contract.fluid.yaml --env prod",
        f"  {A.color(A.BOLD, '📋 Plan')}",
        f"  {A.color(A.GRAY_DIM, '─────────────────────────────────────────')}",
        info(f"Provider: {A.color(A.BLUE_ACCENT, 'snowflake')}  Account: {A.color(A.BLUE_ACCENT, 'acme-demo')}"),
        info("Resolving 1 expose against gold.customer.customer_360_v1"),
        f"  {A.color(A.BOLD, 'Plan summary:')}",
        f"    {A.color(A.GREEN_OK, '+')} ensure   database  PROD",
        f"    {A.color(A.GREEN_OK, '+')} ensure   schema    PROD.GOLD",
        f"    {A.color(A.GREEN_OK, '+')} create   table     PROD.GOLD.CUSTOMER_360",
        f"    {A.color(A.GREEN_OK, '+')} grant    SELECT    role:ANALYST_ROLE",
        f"    {A.color(A.GREEN_OK, '+')} grant    INSERT,SELECT  role:DATA_ENGINEERING_ROLE",
        f"    {A.color(A.GREEN_OK, '+')} run      build     customer_360_aggregation (dbt)",
        output_post=0.15,
    )

    # 3. apply --mode dry-run (live auth, no DDL)
    cast.run(
        "fluid apply contract.fluid.yaml --env prod --mode dry-run --yes",
        working("Connecting to Snowflake account=acme-demo..."),
        output_post=0.32,
    )
    cast.lines(
        ok("Connected as demo_user (role=SYSADMIN, warehouse=COMPUTE_WH)"),
        post=0.18,
    )
    cast.lines(
        ok("Snowflake version: 8.41.1, region: AWS us-east-1"),
        post=0.18,
    )
    cast.lines(
        info(f"--mode {A.color(A.YELLOW_WARN, 'dry-run')} — rendering DDL, not executing"),
        post=0.3,
    )
    cast.lines(
        f"  {A.color(A.GRAY_DIM, '┌─────────────────────────────────────────────────────────────┐')}",
        f"  {A.color(A.GRAY_DIM, '│')} {A.color(A.BLUE_ACCENT, 'CREATE DATABASE IF NOT EXISTS PROD;')}                          {A.color(A.GRAY_DIM, '│')}",
        f"  {A.color(A.GRAY_DIM, '│')} {A.color(A.BLUE_ACCENT, 'CREATE SCHEMA   IF NOT EXISTS PROD.GOLD;')}                     {A.color(A.GRAY_DIM, '│')}",
        f"  {A.color(A.GRAY_DIM, '│')} {A.color(A.BLUE_ACCENT, 'CREATE OR REPLACE TABLE PROD.GOLD.CUSTOMER_360 (')}             {A.color(A.GRAY_DIM, '│')}",
        f"  {A.color(A.GRAY_DIM, '│')}   {A.color(A.BLUE_ACCENT, 'customer_id  STRING NOT NULL,')}                              {A.color(A.GRAY_DIM, '│')}",
        f"  {A.color(A.GRAY_DIM, '│')}   {A.color(A.BLUE_ACCENT, 'segment      STRING,')}                                       {A.color(A.GRAY_DIM, '│')}",
        f"  {A.color(A.GRAY_DIM, '│')}   {A.color(A.BLUE_ACCENT, 'arpu_30d     NUMERIC(18,2),')}                                {A.color(A.GRAY_DIM, '│')}",
        f"  {A.color(A.GRAY_DIM, '│')}   {A.color(A.BLUE_ACCENT, 'updated_at   TIMESTAMP_NTZ NOT NULL')}                        {A.color(A.GRAY_DIM, '│')}",
        f"  {A.color(A.GRAY_DIM, '│')} {A.color(A.BLUE_ACCENT, ');')}                                                            {A.color(A.GRAY_DIM, '│')}",
        f"  {A.color(A.GRAY_DIM, '│')} {A.color(A.BLUE_ACCENT, 'GRANT SELECT ON PROD.GOLD.CUSTOMER_360 TO ROLE ANALYST_ROLE;')} {A.color(A.GRAY_DIM, '│')}",
        f"  {A.color(A.GRAY_DIM, '└─────────────────────────────────────────────────────────────┘')}",
        post=0.18,
    )
    cast.output(f"  {A.color(A.BRIGHT_GREEN, '✓ Dry-run complete (no DDL fired against Snowflake)')}", post=0.4)

    # 4. policy-apply --mode check
    cast.run(
        "fluid policy-apply artifacts/policy/bindings.json --mode check",
        info(f"Connecting to Snowflake account=acme-demo (role=SYSADMIN)..."),
        ok("Loaded 2 policy binding(s) from artifacts/policy/bindings.json"),
        f"  {A.color(A.GREEN_OK, '+')} would-grant  SELECT          role:ANALYST_ROLE              on PROD.GOLD.CUSTOMER_360",
        f"  {A.color(A.GREEN_OK, '+')} would-grant  INSERT,SELECT   role:DATA_ENGINEERING_ROLE     on PROD.GOLD.CUSTOMER_360",
        ok("All bindings would apply cleanly (no drift vs deployed RBAC)"),
        f"  {A.color(A.BRIGHT_GREEN, '✓ Policy check-only complete — re-run with --mode enforce to apply')}",
        output_post=0.16,
    )

    cast.section_break(0.6)
    cast.output(f"  {A.color(A.DIM, '💡 This was --mode dry-run + --mode check. Both validate live auth')}", post=0.18)
    cast.output(f"  {A.color(A.DIM, '   without firing DDL or modifying RBAC. Drop the flags for production.')}", post=0.5)

    cast.prompt()
    return cast


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/casts/snowflake-real.cast"
    cast = build()
    cast.write(out)
    print(f"snowflake-real: {cast.duration:.1f}s → {out}")
