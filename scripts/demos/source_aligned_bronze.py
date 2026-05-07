#!/usr/bin/env python3
"""
source-aligned-bronze — high-fidelity scripted demo of `fluid init
--discover postgres://...` producing a working source-aligned Bronze
contract in ~60 seconds, then showing the engine swap (`engine:` between
duckdb / dlt / meltano / airbyte / kafka-connect / debezium) without
touching the contract shape.

Recasts the previous reels/source-aligned-bronze.html into a CliCast.
"""

import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from cast_builder import Cast, A, ok, working, info  # type: ignore


def build() -> Cast:
    cast = Cast(
        width=92, height=26,
        title="fluid init --discover — Postgres → Bronze contract in 60 seconds",
        pace="readable",
    )

    # 1. The setup — alternative is 6 months of cluster work
    cast.lines(
        f"  {A.color(A.GRAY_DIM, '# The alternative: six months of Airbyte. Two weeks of Airflow.')}",
        f"  {A.color(A.GRAY_DIM, '# JVM heap tuning. For one Postgres source.')}",
        post=0.4,
    )

    cast.run(
        "fluid init --discover postgres://demo:****@localhost:5432/store",
        f"  {A.color(A.PURPLE_AI, '✨')} {A.color(A.BOLD, 'fluid init')} — source-aligned discovery",
        f"  {A.color(A.GRAY_DIM, '─────────────────────────────────────────────────────────────────')}",
        info(f"Connecting to {A.color(A.BLUE_ACCENT, 'postgres://localhost:5432/store')}..."),
        ok(f"Connected as {A.color(A.BLUE_ACCENT, 'demo')} (read-only)"),
        info("Scanning information_schema..."),
        ok(f"Discovered {A.color(A.AMBER, '28 tables')} across {A.color(A.AMBER, '4 schemas')} ({A.color(A.GRAY_DIM, '47 ms')})"),
        ok(f"Inferred {A.color(A.AMBER, '143 columns')}, {A.color(A.AMBER, '12 PII candidates')}, {A.color(A.AMBER, '8 foreign keys')}"),
        f"  {A.color(A.GRAY_DIM, '─────────────────────────────────────────────────────────────────')}",
        output_post=0.18,
    )

    cast.section_break(0.4)

    # 2. The contract — emitted automatically
    cast.lines(
        f"  {A.color(A.BRIGHT_GREEN, '✓ Generated contract.fluid.yaml')} ({A.color(A.DIM, 'Bronze layer · embedded engine')})",
        post=0.3,
    )
    cast.lines(
        f"  {A.color(A.GRAY_DIM, '┌─────────────────────────────────────────────────────────────────┐')}",
        f"  {A.color(A.GRAY_DIM, '│')} {A.color(A.BLUE_ACCENT, 'fluidVersion:')} {A.color(A.AMBER, chr(34) + '0.7.2' + chr(34))}                                          {A.color(A.GRAY_DIM, '│')}",
        f"  {A.color(A.GRAY_DIM, '│')} {A.color(A.BLUE_ACCENT, 'kind:')} DataProduct                                              {A.color(A.GRAY_DIM, '│')}",
        f"  {A.color(A.GRAY_DIM, '│')} {A.color(A.BLUE_ACCENT, 'id:')} bronze.retail.store_postgres_v1                          {A.color(A.GRAY_DIM, '│')}",
        f"  {A.color(A.GRAY_DIM, '│')} {A.color(A.BLUE_ACCENT, 'metadata.layer:')} Bronze                                       {A.color(A.GRAY_DIM, '│')}",
        f"  {A.color(A.GRAY_DIM, '├─────────────────────────────────────────────────────────────────┤')}",
        f"  {A.color(A.GRAY_DIM, '│')} {A.color(A.BLUE_ACCENT, 'sources:')}                                                       {A.color(A.GRAY_DIM, '│')}",
        f"  {A.color(A.GRAY_DIM, '│')}   - {A.color(A.BLUE_ACCENT, 'kind:')} postgres                                            {A.color(A.GRAY_DIM, '│')}",
        f"  {A.color(A.GRAY_DIM, '│')}     {A.color(A.BLUE_ACCENT, 'connection:')} {A.color(A.AMBER, '$STORE_PG_DSN')}                              {A.color(A.GRAY_DIM, '│')}",
        f"  {A.color(A.GRAY_DIM, '│')}     {A.color(A.BLUE_ACCENT, 'tables:')} [orders, customers, products, ...]            {A.color(A.GRAY_DIM, '│')}",
        f"  {A.color(A.GRAY_DIM, '│')} {A.color(A.BLUE_ACCENT, 'builds:')}                                                        {A.color(A.GRAY_DIM, '│')}",
        f"  {A.color(A.GRAY_DIM, '│')}   - {A.color(A.BLUE_ACCENT, 'engine:')} {A.color(A.AMBER, 'duckdb')}    {A.color(A.GRAY_DIM, '# embedded — no cluster')}     {A.color(A.GRAY_DIM, '│')}",
        f"  {A.color(A.GRAY_DIM, '│')}     {A.color(A.BLUE_ACCENT, 'mode:')} cdc                                                {A.color(A.GRAY_DIM, '│')}",
        f"  {A.color(A.GRAY_DIM, '│')}     {A.color(A.BLUE_ACCENT, 'cursor:')} updated_at                                       {A.color(A.GRAY_DIM, '│')}",
        f"  {A.color(A.GRAY_DIM, '└─────────────────────────────────────────────────────────────────┘')}",
        post=0.3,
    )

    cast.section_break(0.4)

    # 3. Validate + apply locally
    cast.run(
        "fluid validate contract.fluid.yaml && fluid apply --yes",
        ok("Schema 0.7.2 — passed"),
        ok("28 tables resolved against information_schema"),
        ok("All 12 PII columns flagged for downstream masking"),
        working("Pulling postgres → bronze.duckdb..."),
        ok(f"Pulled {A.color(A.AMBER, '847,392 rows')} in {A.color(A.AMBER, '4.8 s')}"),
        f"  {A.color(A.BRIGHT_GREEN, '✓ Bronze contract live in 6.2 seconds total')}",
        output_post=0.18,
    )

    cast.section_break(0.5)

    # 4. The engine swap — same contract, six engines
    cast.lines(
        f"  {A.color(A.BOLD, '🔄 Outgrew embedded mode? Swap one line:')}",
        f"  {A.color(A.GRAY_DIM, '─────────────────────────────────────────────────────────────────')}",
        post=0.3,
    )

    cast.lines(
        f"  {A.color(A.BLUE_ACCENT, 'engine:')} {A.color(A.AMBER, 'duckdb')}          {A.color(A.GRAY_DIM, '# embedded, default — no cluster, no JVM')}",
        f"  {A.color(A.BLUE_ACCENT, 'engine:')} {A.color(A.AMBER, 'dlt')}             {A.color(A.GRAY_DIM, '# python data-load-tool, schema-evolution-aware')}",
        f"  {A.color(A.BLUE_ACCENT, 'engine:')} {A.color(A.AMBER, 'meltano')}         {A.color(A.GRAY_DIM, '# singer ecosystem, 600+ taps')}",
        f"  {A.color(A.BLUE_ACCENT, 'engine:')} {A.color(A.AMBER, 'airbyte')}         {A.color(A.GRAY_DIM, '# enterprise SaaS / OSS, batched')}",
        f"  {A.color(A.BLUE_ACCENT, 'engine:')} {A.color(A.AMBER, 'kafka-connect')}   {A.color(A.GRAY_DIM, '# streaming, JDBC + CDC source connectors')}",
        f"  {A.color(A.BLUE_ACCENT, 'engine:')} {A.color(A.AMBER, 'debezium')}        {A.color(A.GRAY_DIM, '# log-based CDC, sub-second latency')}",
        f"  {A.color(A.GRAY_DIM, '─────────────────────────────────────────────────────────────────')}",
        post=0.3,
    )

    cast.lines(
        f"  {A.color(A.BOLD, 'The contract.fluid.yaml stays identical.')}",
        f"  {A.color(A.GRAY_DIM, 'Same source spec. Same tables. Same PII flags. Same downstream')}",
        f"  {A.color(A.GRAY_DIM, 'Bronze table layout. Only the runtime engine moves.')}",
        post=0.5,
    )

    cast.prompt()
    return cast


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/casts/source-aligned-bronze.cast"
    cast = build()
    cast.write(out)
    print(f"source-aligned-bronze: {cast.duration:.1f}s → {out}")
