#!/usr/bin/env python3
"""GCP/BigQuery quickstart — same contract, swap one line, deploy."""

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from cast_builder import Cast, A, ok, working, info, header  # type: ignore


def build() -> Cast:
    cast = Cast(
        width=92, height=24,
        title="FLUID Forge — GCP / BigQuery quickstart",
        pace="readable",  # 7 commands, multi-step IAM; viewers need breathing room
    )

    cast.run(
        'pipx install "data-product-forge[gcp]"',
        f"  installed package {A.color(A.BLUE_ACCENT, 'data-product-forge 0.8.0')}, Python 3.13",
        f"  added providers: {A.color(A.BLUE_ACCENT, 'gcp')} (BigQuery + GCS + IAM)",
        output_post=0.18,
    )

    cast.run(
        "gcloud auth application-default login",
        f"  {A.color(A.DIM, '... browser opens for OAuth ...')}",
        ok(f"Credentials saved to {A.color(A.BLUE_ACCENT, '~/.config/gcloud/application_default_credentials.json')}"),
        output_post=0.4,
    )

    # The "swap one line" hero moment
    cast.prompt()
    cast.typed("yq -i '.exposes[0].binding.platform = \"gcp\"' contract.fluid.yaml")
    cast.enter()
    cast.section_break(0.4)

    # Diff hint
    cast.prompt()
    cast.typed("git diff contract.fluid.yaml")
    cast.enter()
    cast.lines(
        f"  {A.color(A.RED_ERR, '-')}      platform: local",
        f"  {A.color(A.RED_ERR, '-')}      format: parquet",
        f"  {A.color(A.RED_ERR, '-')}      location: {{ path: ./runtime/out/btc.parquet }}",
        f"  {A.color(A.GREEN_OK, '+')}      platform: gcp",
        f"  {A.color(A.GREEN_OK, '+')}      format: bigquery_table",
        f"  {A.color(A.GREEN_OK, '+')}      location: {{ project: my-project, dataset: crypto, table: btc }}",
        post=0.16,
    )
    cast.section_break(0.6)

    cast.run(
        "fluid validate contract.fluid.yaml",
        ok("Schema 0.7.2 — passed"),
        ok("binding.platform=gcp — supported (provider gcp installed)"),
        ok(f"binding.location complete (project, dataset, table)"),
        f"  {A.color(A.BRIGHT_GREEN, '✓ Contract validation passed')}",
        output_post=0.16,
    )

    cast.run(
        "fluid plan contract.fluid.yaml --env prod",
        info(f"Provider: {A.color(A.BLUE_ACCENT, 'gcp')} (BigQuery + GCS)"),
        info("Resolving 1 expose against gold.crypto.bitcoin_tracker_v1"),
        f"  {A.color(A.BOLD, 'Plan summary:')}",
        f"    {A.color(A.GREEN_OK, '+')} ensure  dataset    crypto (region=europe-west3)",
        f"    {A.color(A.GREEN_OK, '+')} create  table      crypto.btc",
        f"    {A.color(A.GREEN_OK, '+')} grant   role/dataViewer  group:analysts@company.com",
        f"    {A.color(A.GREEN_OK, '+')} run     build      bitcoin_price_ingestion (sql)",
        output_post=0.15,
    )

    cast.run(
        "fluid apply contract.fluid.yaml --env prod --yes",
        working("Acquiring lease on gold.crypto.bitcoin_tracker_v1..."),
        output_post=0.3,
    )
    cast.lines(working("Ensuring BigQuery dataset crypto..."), post=0.32)
    cast.lines(ok("dataset crypto exists (region=europe-west3)"), post=0.16)
    cast.lines(working("Creating table crypto.btc..."), post=0.32)
    cast.lines(ok("table crypto.btc created"), post=0.16)
    cast.lines(working("Running bitcoin_price_ingestion (BigQuery SQL)..."), post=0.4)
    cast.lines(ok("transformation complete (24 rows in)"), post=0.2)
    cast.lines(working("Applying IAM bindings (1 grant)..."), post=0.3)
    cast.lines(ok("BigQuery roles/dataViewer granted to group:analysts@company.com"), post=0.3)

    cast.output(f"  {A.color(A.BRIGHT_GREEN, '✓ Pipeline complete in 4.83 s')}", post=0.4)
    cast.output("", post=0.0)
    cast.output(f"  {A.color(A.BOLD, '📦 Data product live:')} gold.crypto.bitcoin_tracker_v1", post=0.18)
    cast.output(f"  {A.color(A.DIM, '📍 bigquery://my-project.crypto.btc (24 rows)')}", post=0.4)

    cast.section_break(0.6)
    cast.prompt()
    return cast


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/casts/gcp-quickstart.cast"
    cast = build()
    cast.write(out)
    print(f"gcp-quickstart: {cast.duration:.1f}s → {out}")
