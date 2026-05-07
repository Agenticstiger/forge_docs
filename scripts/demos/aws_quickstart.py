#!/usr/bin/env python3
"""AWS / Athena quickstart — S3 + Glue + Athena."""

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from cast_builder import Cast, A, ok, working, info  # type: ignore


def build() -> Cast:
    cast = Cast(
        width=92, height=24,
        title="FLUID Forge — AWS / Athena quickstart",
        pace="readable",
    )

    cast.run(
        'pipx install "data-product-forge[aws]"',
        f"  installed package {A.color(A.BLUE_ACCENT, 'data-product-forge 0.8.0')}, Python 3.13",
        f"  added providers: {A.color(A.BLUE_ACCENT, 'aws')} (S3 + Glue + Athena + IAM)",
        output_post=0.18,
    )

    cast.run(
        "aws configure",
        f"  {A.color(A.DIM, 'AWS Access Key ID [None]:')} {A.color(A.GRAY_DIM, '••••••••')}",
        f"  {A.color(A.DIM, 'AWS Secret Access Key [None]:')} {A.color(A.GRAY_DIM, '••••••••')}",
        f"  {A.color(A.DIM, 'Default region name [None]:')} eu-west-1",
        f"  {A.color(A.DIM, 'Default output format [None]:')} json",
        output_post=0.3,
    )

    cast.prompt()
    cast.typed("yq -i '.exposes[0].binding.platform = \"aws\"' contract.fluid.yaml")
    cast.enter()
    cast.section_break(0.4)

    cast.run(
        "fluid validate contract.fluid.yaml",
        ok("Schema 0.7.2 — passed"),
        ok("binding.platform=aws — supported (provider aws installed)"),
        ok("binding.format=s3_file with bucket + prefix"),
        f"  {A.color(A.BRIGHT_GREEN, '✓ Contract validation passed')}",
        output_post=0.16,
    )

    cast.run(
        "fluid plan contract.fluid.yaml --env prod",
        info(f"Provider: {A.color(A.BLUE_ACCENT, 'aws')} (S3 + Glue + Athena)"),
        f"  {A.color(A.BOLD, 'Plan summary:')}",
        f"    {A.color(A.GREEN_OK, '+')} ensure  s3 bucket  fluid-demo-data-lake (region=eu-west-1)",
        f"    {A.color(A.GREEN_OK, '+')} ensure  glue db    crypto",
        f"    {A.color(A.GREEN_OK, '+')} create  glue table crypto.btc (Parquet)",
        f"    {A.color(A.GREEN_OK, '+')} create  Athena workgroup fluid-demo",
        output_post=0.15,
    )

    cast.run(
        "fluid apply contract.fluid.yaml --env prod --yes",
        working("Ensuring S3 bucket fluid-demo-data-lake..."),
        output_post=0.32,
    )
    cast.lines(ok("S3 bucket exists (encrypted, versioned)"), post=0.16)
    cast.lines(working("Ensuring Glue database crypto..."), post=0.3)
    cast.lines(ok("Glue database exists"), post=0.16)
    cast.lines(working("Creating Glue table crypto.btc..."), post=0.35)
    cast.lines(ok("table created with Parquet partitioning"), post=0.2)
    cast.lines(working("Applying IAM resource policies..."), post=0.3)
    cast.lines(ok("S3 + Glue + Athena resource policies applied"), post=0.3)

    cast.output(f"  {A.color(A.BRIGHT_GREEN, '✓ Pipeline complete in 6.21 s')}", post=0.4)
    cast.output("", post=0.0)
    cast.output(f"  {A.color(A.BOLD, '📦 Data product live:')} gold.crypto.bitcoin_tracker_v1", post=0.18)
    cast.output(f"  {A.color(A.DIM, '📍 s3://fluid-demo-data-lake/crypto/btc/  (Athena queryable)')}", post=0.4)

    cast.section_break(0.6)
    cast.prompt()
    return cast


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/casts/aws-quickstart.cast"
    cast = build()
    cast.write(out)
    print(f"aws-quickstart: {cast.duration:.1f}s → {out}")
