#!/usr/bin/env python3
"""Verify forge_docs/docs/providers/ matches the providers known to the CLI.

Calls ``fluid providers`` (which returns JSON natively, with a log preamble we
strip) and cross-references the names against ``docs/providers/<name>.md``
files. Conceptual pages (architecture, custom providers, roadmap) are skipped,
as are non-execution providers that are documented in ``docs/cli/`` instead
(publishers and standards exporters).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PROVIDERS_DIR = REPO_ROOT / "docs" / "providers"

# Conceptual pages — not bound to a specific provider name.
SKIP_DOC_STEMS = {"README", "architecture", "custom-providers", "roadmap"}

# CLI-registered providers that are documented in docs/cli/<command>.md
# rather than docs/providers/<name>.md (because they are publishers or
# standards exporters, not execution providers users target with `--provider`).
SKIP_CLI_PROVIDERS = {
    "datamesh_manager",  # documented in docs/cli/datamesh-manager.md
    "odps",              # documented in docs/cli/odps.md
    "odps_standard",     # documented in docs/cli/odps-bitol.md
    "odcs",              # documented in docs/cli/odcs.md
}

# Map CLI provider names to docs filename stems when they differ.
NAME_ALIASES: dict[str, str] = {
    # Add entries here only when the CLI name and the docs filename
    # genuinely differ.
}


def _extract_json_blob(text: str) -> str | None:
    """Return the first balanced ``{...}`` block in *text*, or ``None``.

    The CLI prefixes its output with a structured-log line; we have to
    skip past it to find the actual payload.
    """
    depth = 0
    start: int | None = None
    for idx, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = idx
            depth += 1
        elif ch == "}" and depth:
            depth -= 1
            if depth == 0 and start is not None:
                return text[start : idx + 1]
    return None


def fluid_providers() -> set[str]:
    try:
        proc = subprocess.run(
            ["fluid", "providers"],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        sys.exit(
            "ERROR: `fluid` not found on PATH. Install the pinned CLI with "
            "`pip install data-product-forge==<supportedCliVersion>` first."
        )

    if proc.returncode != 0:
        sys.exit(
            "ERROR: `fluid providers` failed.\n"
            f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
        )

    blob = _extract_json_blob(proc.stdout)
    if blob is None:
        sys.exit(
            "ERROR: could not find a JSON object in `fluid providers` output. "
            "The CLI output format may have changed.\n"
            f"stdout: {proc.stdout}"
        )
    try:
        data = json.loads(blob)
    except json.JSONDecodeError as exc:
        sys.exit(f"ERROR: failed to parse JSON from `fluid providers`: {exc}\n{blob}")

    if isinstance(data, dict) and isinstance(data.get("providers"), list):
        names = data["providers"]
    elif isinstance(data, list):
        names = data
    else:
        sys.exit(
            "ERROR: unexpected JSON shape from `fluid providers` (expected a list "
            f"or {{'providers': [...]}}): {data!r}"
        )

    return {str(name).strip() for name in names if str(name).strip()}


def doc_provider_stems() -> set[str]:
    if not PROVIDERS_DIR.is_dir():
        sys.exit(f"ERROR: missing docs directory {PROVIDERS_DIR}")
    return {p.stem for p in PROVIDERS_DIR.glob("*.md") if p.stem not in SKIP_DOC_STEMS}


def main() -> int:
    raw_cli = fluid_providers()
    cli_providers = {NAME_ALIASES.get(name, name) for name in raw_cli - SKIP_CLI_PROVIDERS}
    doc_pages = doc_provider_stems()

    missing_docs = cli_providers - doc_pages
    orphan_docs = doc_pages - cli_providers

    rc = 0
    if missing_docs:
        rc = 1
        print(
            "FAIL: providers known to the CLI but missing a docs page:\n"
            + "\n".join(f"  - {name}" for name in sorted(missing_docs))
            + "\n  Either add docs/providers/<name>.md, or list it in "
            "SKIP_CLI_PROVIDERS / NAME_ALIASES in scripts/check_providers.py."
        )
    if orphan_docs:
        rc = 1
        print(
            "FAIL: docs/providers pages with no matching CLI provider:\n"
            + "\n".join(f"  - {name}.md" for name in sorted(orphan_docs))
            + "\n  Either delete the page, rename it, or add it to SKIP_DOC_STEMS / "
            "NAME_ALIASES in scripts/check_providers.py."
        )
    if rc == 0:
        print(
            f"OK: all {len(cli_providers)} execution providers have a matching "
            f"docs/providers/<name>.md page (skipped non-execution providers: "
            f"{sorted(SKIP_CLI_PROVIDERS & raw_cli)})."
        )
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
