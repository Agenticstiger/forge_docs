#!/usr/bin/env python3
"""Verify forge_docs is in sync with the installed `fluid` CLI.

Two checks:

1. The CLI version reported by ``fluid --version`` matches the
   ``supportedCliVersion`` recorded in ``docs/.vuepress/cli-version.json``.
2. Every top-level subcommand registered by the CLI's argparse parser has a
   matching ``docs/cli/<command>.md`` page (and vice versa), modulo the
   explicit exceptions in ``scripts/cli-docs-allowlist.yml``.

We introspect the argparse parser directly (via
``fluid_build.cli.bootstrap.register_core_commands``) rather than parsing
``fluid --help`` text, because the CLI ships a heavily customized Rich help
formatter that only shows promoted commands.

Exit code is non-zero on any failure so this can be wired straight into CI.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = REPO_ROOT / "docs" / ".vuepress" / "cli-version.json"
CLI_DOCS_DIR = REPO_ROOT / "docs" / "cli"
ALLOWLIST_FILE = REPO_ROOT / "scripts" / "cli-docs-allowlist.yml"


def load_supported_version() -> str:
    data = json.loads(VERSION_FILE.read_text(encoding="utf-8"))
    version = data.get("supportedCliVersion")
    if not version:
        sys.exit(f"ERROR: {VERSION_FILE} is missing 'supportedCliVersion'")
    return str(version)


def load_allowlist() -> tuple[set[str], set[str]]:
    """Tiny YAML reader covering only the shape we use here.

    Avoids requiring PyYAML in CI. Supported syntax: top-level
    ``key:`` followed by ``- value`` list items. Comments after ``#``
    are stripped. Anything else triggers a clear error.
    """
    undocumented_ok: set[str] = set()
    docs_only_ok: set[str] = set()
    current: set[str] | None = None

    if not ALLOWLIST_FILE.exists():
        return undocumented_ok, docs_only_ok

    for raw_lineno, raw_line in enumerate(
        ALLOWLIST_FILE.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if not line.startswith(" ") and line.endswith(":"):
            key = line[:-1].strip()
            if key == "undocumented_ok":
                current = undocumented_ok
            elif key == "docs_only_ok":
                current = docs_only_ok
            else:
                current = None
            continue
        stripped = line.lstrip()
        if stripped.startswith("- ") and current is not None:
            current.add(stripped[2:].strip())
            continue
        sys.exit(
            f"ERROR: {ALLOWLIST_FILE}:{raw_lineno}: unsupported syntax "
            f"({raw_line!r}). Allowlist supports only 'key:' headers and "
            "'- value' list items."
        )

    return undocumented_ok, docs_only_ok


def run_fluid(*args: str) -> str:
    try:
        result = subprocess.run(
            ["fluid", *args],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        sys.exit(
            "ERROR: `fluid` not found on PATH. Install the pinned CLI with "
            "`pip install data-product-forge==<supportedCliVersion>` first."
        )
    except subprocess.CalledProcessError as exc:
        sys.exit(
            f"ERROR: `fluid {' '.join(args)}` failed (exit {exc.returncode}).\n"
            f"stdout: {exc.stdout}\nstderr: {exc.stderr}"
        )
    return result.stdout


_VERSION_RE = re.compile(r"(\d+\.\d+\.\d+(?:[\w.+-]*)?)")


def installed_cli_version() -> str:
    raw = run_fluid("--version").strip()
    match = _VERSION_RE.search(raw)
    if not match:
        sys.exit(f"ERROR: could not parse a version from `fluid --version` output: {raw!r}")
    return match.group(1)


def list_cli_subcommands() -> set[str]:
    """Return the set of top-level subcommands registered by the CLI parser.

    Imports ``fluid_build.cli.bootstrap.register_core_commands`` and inspects
    the registered ``_SubParsersAction.choices`` directly. This catches every
    command the CLI installs - including ones the custom Rich ``--help``
    formatter chooses to hide (deprecated, hidden, profile-gated, etc.).
    """
    try:
        from fluid_build.cli.bootstrap import register_core_commands  # type: ignore
    except ImportError as exc:
        sys.exit(
            "ERROR: could not import fluid_build.cli.bootstrap. Install the "
            f"pinned CLI first (`pip install data-product-forge==<version>`). {exc}"
        )

    parser = argparse.ArgumentParser(prog="fluid")
    sp = parser.add_subparsers(dest="cmd")
    register_core_commands(sp)

    commands = {str(name) for name in sp.choices.keys()}
    if not commands:
        sys.exit("ERROR: register_core_commands produced an empty subcommand set.")
    return commands


def list_doc_pages() -> set[str]:
    if not CLI_DOCS_DIR.is_dir():
        sys.exit(f"ERROR: missing docs directory {CLI_DOCS_DIR}")
    return {p.stem for p in CLI_DOCS_DIR.glob("*.md")}


def check_version_only() -> int:
    expected = load_supported_version()
    actual = installed_cli_version()
    if expected != actual:
        print(
            f"FAIL: supportedCliVersion is {expected!r} but `fluid --version` "
            f"reports {actual!r}.\n"
            f"  Either bump {VERSION_FILE.relative_to(REPO_ROOT)} or "
            f"`pip install data-product-forge=={expected}`.",
            file=sys.stderr,
        )
        return 1
    print(f"OK: fluid CLI version matches docs ({expected}).")
    return 0


def check_full() -> int:
    rc = check_version_only()

    undocumented_ok, docs_only_ok = load_allowlist()
    cli_commands = list_cli_subcommands()
    doc_pages = list_doc_pages()

    missing_docs = (cli_commands - doc_pages) - undocumented_ok
    orphan_docs = (doc_pages - cli_commands) - docs_only_ok

    if missing_docs:
        rc = 1
        print(
            "FAIL: the following CLI commands have no docs/cli/<name>.md page:\n"
            + "\n".join(f"  - {name}" for name in sorted(missing_docs))
            + "\n  Either add a doc page or list the command in "
            f"{ALLOWLIST_FILE.relative_to(REPO_ROOT)} (undocumented_ok)."
        )
    if orphan_docs:
        rc = 1
        print(
            "FAIL: the following doc pages have no matching CLI command:\n"
            + "\n".join(f"  - {name}.md" for name in sorted(orphan_docs))
            + "\n  Either delete the page or list the stem in "
            f"{ALLOWLIST_FILE.relative_to(REPO_ROOT)} (docs_only_ok)."
        )

    if rc == 0:
        print(
            f"OK: all {len(cli_commands)} CLI subcommands are documented "
            f"(docs/cli/ has {len(doc_pages)} pages)."
        )
    return rc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--version-only",
        action="store_true",
        help="Only check the installed CLI version against the pinned value.",
    )
    args = parser.parse_args(argv)

    if args.version_only:
        return check_version_only()
    return check_full()


if __name__ == "__main__":
    raise SystemExit(main())
