#!/usr/bin/env python3
"""GCP/BigQuery quickstart — same contract, swap one line, deploy.

Continues the customer-360 quickstart: the contract scaffolded by
``fluid init --quickstart`` (Customer 360 Analytics) is re-pointed from
the local DuckDB provider to GCP / BigQuery by swapping binding.platform.
"""

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from cast_builder import Cast, A, ok, working, info  # type: ignore


def build() -> Cast:
    cast = Cast(
        width=92, height=24,
        title="FLUID Forge — GCP / BigQuery quickstart",
        pace="readable",  # multi-step deploy; viewers need breathing room
    )

    cast.run(
        'pipx install "data-product-forge[gcp]"',
        f"  installed package {A.color(A.BLUE_ACCENT, 'data-product-forge 0.9.0')}, Python 3.13",
        f"  added providers: {A.color(A.BLUE_ACCENT, 'gcp')} (BigQuery + GCS + IAM)",
        output_post=0.18,
    )

    cast.run(
        "gcloud auth application-default login",
        f"  {A.color(A.DIM, '... browser opens for OAuth ...')}",
        ok(f"Credentials saved to {A.color(A.BLUE_ACCENT, '~/.config/gcloud/application_default_credentials.json')}"),
        output_post=0.4,
    )

    # The "swap one line" hero moment — re-point both exposes at GCP
    cast.prompt()
    cast.typed("yq -i '.exposes[].binding.platform = \"gcp\"' contract.fluid.yaml")
    cast.enter()
    cast.section_break(0.4)

    # Diff hint
    cast.prompt()
    cast.typed("git diff contract.fluid.yaml")
    cast.enter()
    cast.lines(
        f"  {A.color(A.RED_ERR, '-')}      platform: local",
        f"  {A.color(A.RED_ERR, '-')}      format: parquet",
        f"  {A.color(A.RED_ERR, '-')}      location: {{ path: output/customer_360.parquet }}",
        f"  {A.color(A.GREEN_OK, '+')}      platform: gcp",
        f"  {A.color(A.GREEN_OK, '+')}      format: bigquery_table",
        f"  {A.color(A.GREEN_OK, '+')}      location: {{ project: my-project, dataset: analytics, table: customer_360_master }}",
        post=0.16,
    )
    cast.section_break(0.6)

    cast.run(
        "fluid validate contract.fluid.yaml",
        ok("Schema 0.7.2 — passed"),
        ok("binding.platform=gcp — supported (provider gcp installed)"),
        ok("binding.location complete (project, dataset, table)"),
        f"  {A.color(A.BRIGHT_GREEN, '✓ Contract validation passed')}",
        output_post=0.16,
    )

    cast.run(
        "fluid plan contract.fluid.yaml --env prod",
        info(f"Provider: {A.color(A.BLUE_ACCENT, 'gcp')} (BigQuery + GCS)"),
        info("Resolving 2 exposes against gold.customer.analytics_360_v1"),
        f"  {A.color(A.BOLD, 'Plan summary:')}",
        f"    {A.color(A.GREEN_OK, '+')} ensure  dataset  analytics (region=europe-west3)",
        f"    {A.color(A.GREEN_OK, '+')} create  table    analytics.customer_360_master",
        f"    {A.color(A.GREEN_OK, '+')} create  view     analytics.high_value_customers",
        f"    {A.color(A.GREEN_OK, '+')} run     build    customer_360_pipeline (sql · 5 stages)",
        output_post=0.15,
    )

    cast.run(
        "fluid apply contract.fluid.yaml --env prod --yes",
        working("Acquiring lease on gold.customer.analytics_360_v1..."),
        output_post=0.3,
    )
    cast.lines(working("Ensuring BigQuery dataset analytics..."), post=0.32)
    cast.lines(ok("dataset analytics exists (region=europe-west3)"), post=0.16)
    cast.lines(working("Creating table analytics.customer_360_master..."), post=0.32)
    cast.lines(ok("table created"), post=0.16)
    cast.lines(working("Creating view analytics.high_value_customers..."), post=0.3)
    cast.lines(ok("view created"), post=0.16)
    cast.lines(working("Running customer_360_pipeline (BigQuery SQL · 5 stages)..."), post=0.4)
    cast.lines(ok("transformation complete (10 rows out)"), post=0.3)

    cast.output(f"  {A.color(A.BRIGHT_GREEN, '✓ Pipeline complete in 4.83 s')}", post=0.4)
    cast.output("", post=0.0)
    cast.output(f"  {A.color(A.BOLD, '📦 Data product live:')} gold.customer.analytics_360_v1", post=0.18)
    cast.output(f"  {A.color(A.DIM, '📍 bigquery://my-project.analytics.customer_360_master')}", post=0.4)

    cast.section_break(0.6)
    cast.prompt()
    return cast


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/casts/gcp-quickstart.cast"
    cast = build()
    cast.write(out)
    print(f"gcp-quickstart: {cast.duration:.1f}s → {out}")
