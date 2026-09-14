#!/usr/bin/env python3
"""Verify forge_docs is in sync with the installed `fluid` CLI.

Six checks:

1. The CLI version reported by ``fluid --version`` matches the
   ``supportedCliVersion`` recorded in ``docs/.vuepress/cli-version.json``.
2. Every top-level subcommand registered by the CLI's argparse parser has a
   matching ``docs/cli/<command>.md`` page (and vice versa), modulo the
   explicit exceptions in ``scripts/cli-docs-allowlist.yml``. Doc pages are
   enumerated recursively and keyed on their path relative to ``docs/cli/``,
   so pages in subdirectories (``catalogs/``, ``tasks/``) are visible to both
   halves of the check.
3. ``fluid init --quickstart`` emits the fluidVersion pinned as
   ``quickstartScaffoldVersion`` (so the docs can't silently drift from what
   the quickstart actually scaffolds — the quickstart/customer-360 template is
   pinned independently of the latest factory-path schema).
4. cli-version.json's own contract pins exist in the pinned CLI's bundled
   schema set.
5. FLAG ORACLE: every ``fluid ...`` invocation inside a fenced code block in
   ``docs/**/*.md`` uses flags and subcommand names the pinned CLI actually
   registers. Options are diffed against the resolved subparser's
   ``option_strings`` (recursing into nested subparsers via ``choices``), and
   positionals that declare ``choices`` are checked against them.
6. VERSION SWEEP: no page claims a CLI version or a contract ``fluidVersion``
   that contradicts ``cli-version.json`` / the pinned CLI's bundled schemas.

We introspect the argparse parser directly (via
``fluid_build.cli.build_parser``, falling back to
``fluid_build.cli.bootstrap.register_core_commands``) rather than parsing
``fluid --help`` text, because the CLI ships a heavily customized Rich help
formatter that only shows promoted commands.

Exit code is non-zero on any failure so this can be wired straight into CI.


The historical marker
---------------------
The version sweep is about what the docs tell a reader to run *today*. Pages
legitimately discuss older releases ("GA since CLI v0.8.0", "new in CLI
0.8.9"). Two things keep those out of the results: the sweep matches only
*baseline* phrasings (see ``_VERSION_PATTERNS``), and any line that slips
through can be marked historical.

The marker is an HTML comment, so it never renders:

    <!-- cli-version: historical -->

Three scopes:

* On the same line as the version — exempts that line::

      | CLI | 0.9.0 -> 0.10.0 | Released. | <!-- cli-version: historical -->

* On a line of its own — exempts the next non-blank line, and if that line
  opens a fenced code block, the whole block. Use this for fenced snippets,
  where an inline HTML comment would be shown to the reader verbatim::

      <!-- cli-version: historical -->
      ```bash
      pip install data-product-forge==0.8.4
      ```

* ``<!-- cli-version: historical-file -->`` anywhere in a file exempts the
  whole file. Use it for pages that are entirely about a past release.

``RELEASE_NOTES_*.md`` is excluded from the sweep unconditionally; those pages
are a permanent record of what a past release shipped and are never rewritten.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = REPO_ROOT / "docs" / ".vuepress" / "cli-version.json"
DOCS_DIR = REPO_ROOT / "docs"
CLI_DOCS_DIR = DOCS_DIR / "cli"
ALLOWLIST_FILE = REPO_ROOT / "scripts" / "cli-docs-allowlist.yml"

# Directories under docs/ that are build output or vendored, never prose.
_SKIP_DIR_PARTS = {"node_modules", ".vuepress"}

ALLOWLIST_KEYS = (
    "undocumented_ok",
    "docs_only_ok",
    "flag_oracle_ok",
    "version_sweep_ok",
)


def load_supported_version() -> str:
    data = json.loads(VERSION_FILE.read_text(encoding="utf-8"))
    version = data.get("supportedCliVersion")
    if not version:
        sys.exit(f"ERROR: {VERSION_FILE} is missing 'supportedCliVersion'")
    return str(version)


def load_supported_install_spec() -> str:
    data = json.loads(VERSION_FILE.read_text(encoding="utf-8"))
    version = data.get("supportedCliVersion")
    install_spec = data.get("supportedCliInstallSpec")
    if install_spec:
        return str(install_spec)
    if not version:
        sys.exit(f"ERROR: {VERSION_FILE} is missing 'supportedCliVersion'")
    return f"data-product-forge=={version}"


def load_quickstart_scaffold_version() -> str | None:
    """The fluidVersion ``fluid init --quickstart`` is expected to emit.

    Pinned in cli-version.json as ``quickstartScaffoldVersion``. The quickstart
    is an alias for ``--template customer-360``, whose bundled contract is
    pinned independently of the latest schema (factory paths such as
    ``--discover`` / ``forge`` / ``product-new`` emit the newer
    ``supportedFluidContractVersion``). Returns None if not pinned.
    """
    data = json.loads(VERSION_FILE.read_text(encoding="utf-8"))
    value = data.get("quickstartScaffoldVersion")
    return str(value) if value else None


def load_supported_contract_version() -> str | None:
    data = json.loads(VERSION_FILE.read_text(encoding="utf-8"))
    value = data.get("supportedFluidContractVersion")
    return str(value) if value else None


def load_allowlist() -> dict[str, set[str]]:
    """Tiny YAML reader covering only the shape we use here.

    Avoids requiring PyYAML in CI. Supported syntax: top-level
    ``key:`` followed by ``- value`` list items. Comments after ``#``
    are stripped. Anything else triggers a clear error.
    """
    result: dict[str, set[str]] = {key: set() for key in ALLOWLIST_KEYS}
    current: set[str] | None = None

    if not ALLOWLIST_FILE.exists():
        return result

    for raw_lineno, raw_line in enumerate(
        ALLOWLIST_FILE.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if not line.startswith(" ") and line.endswith(":"):
            key = line[:-1].strip()
            if key not in result:
                sys.exit(
                    f"ERROR: {ALLOWLIST_FILE}:{raw_lineno}: unknown allowlist key "
                    f"{key!r}. Known keys: {', '.join(ALLOWLIST_KEYS)}."
                )
            current = result[key]
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

    return result


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


# ---------------------------------------------------------------------------
# Parser introspection
# ---------------------------------------------------------------------------


_PARSER_CACHE: argparse.ArgumentParser | None = None


def build_cli_parser() -> argparse.ArgumentParser:
    """Return the pinned CLI's real root argparse parser.

    ``fluid_build.cli.build_parser`` is the parser the CLI actually dispatches
    on, so it carries the global options (``--provider``, ``--profile``, ...)
    that apply only *before* the subcommand name. Subparsers do not inherit
    them, which is why ``fluid verify --provider local`` is an error even
    though ``fluid --provider local verify`` is not. We fall back to assembling
    a parser from ``register_core_commands`` for CLI releases that do not
    export ``build_parser``.
    """
    global _PARSER_CACHE
    if _PARSER_CACHE is not None:
        return _PARSER_CACHE

    try:
        from fluid_build.cli import build_parser  # type: ignore
    except ImportError:
        pass
    else:
        _PARSER_CACHE = build_parser()
        return _PARSER_CACHE

    try:
        from fluid_build.cli.bootstrap import register_core_commands  # type: ignore
    except ImportError as exc:
        sys.exit(
            "ERROR: could not import fluid_build.cli. Install the pinned CLI "
            f"first (`pip install data-product-forge==<version>`). {exc}"
        )

    parser = argparse.ArgumentParser(prog="fluid")
    sp = parser.add_subparsers(dest="cmd")
    register_core_commands(sp)
    _PARSER_CACHE = parser
    return _PARSER_CACHE


def _subparsers_action(
    parser: argparse.ArgumentParser,
) -> argparse._SubParsersAction | None:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action
    return None


def _option_strings(parser: argparse.ArgumentParser) -> set[str]:
    return {opt for action in parser._actions for opt in action.option_strings}


def _option_nargs(parser: argparse.ArgumentParser) -> dict[str, object]:
    """Map every option string on ``parser`` to that action's nargs."""
    out: dict[str, object] = {}
    for action in parser._actions:
        for opt in action.option_strings:
            out[opt] = action.nargs
    return out


def list_cli_subcommands() -> set[str]:
    """Return the set of top-level subcommands registered by the CLI parser.

    Inspects the registered ``_SubParsersAction.choices`` directly. This
    catches every command the CLI installs - including ones the custom Rich
    ``--help`` formatter chooses to hide (deprecated, hidden, profile-gated).
    """
    sp = _subparsers_action(build_cli_parser())
    if sp is None:
        sys.exit("ERROR: the CLI root parser registers no subparsers.")
    commands = {str(name) for name in sp.choices.keys()}
    if not commands:
        sys.exit("ERROR: the CLI root parser produced an empty subcommand set.")
    return commands


def bundled_schema_versions() -> set[str] | None:
    """Contract schema versions the pinned CLI ships, straight from the CLI.

    Returns None when the CLI does not expose the manager (older releases), in
    which case the fluidVersion sweep falls back to cli-version.json's pins.
    """
    try:
        from fluid_build.schema_manager import FluidSchemaManager  # type: ignore
    except ImportError:
        return None
    versions = getattr(FluidSchemaManager, "BUNDLED_VERSIONS", None)
    if not versions:
        return None
    return {str(v) for v in versions}


def latest_bundled_schema_version() -> str | None:
    try:
        from fluid_build.schema_manager import FluidSchemaManager  # type: ignore
    except ImportError:
        return None
    getter = getattr(FluidSchemaManager, "latest_bundled_version", None)
    if getter is None:
        return None
    try:
        return str(getter())
    except Exception:  # pragma: no cover - defensive
        return None


# ---------------------------------------------------------------------------
# Doc page enumeration
# ---------------------------------------------------------------------------


def _iter_doc_files(root: Path) -> list[Path]:
    out = []
    for path in sorted(root.rglob("*.md")):
        if _SKIP_DIR_PARTS & set(path.relative_to(root).parts):
            continue
        out.append(path)
    # The repo-root README is a docs surface with the widest audience of all -
    # it is what GitHub shows first - but it lives outside docs/, so the sweep
    # never saw it. It sat seven releases stale (0.8.11 against a 0.15.0 pin)
    # while every in-tree page was green.
    if root == DOCS_DIR:
        root_readme = REPO_ROOT / "README.md"
        if root_readme.is_file():
            out.append(root_readme)
    return out


def list_doc_pages() -> set[str]:
    """Doc page keys, relative to docs/cli/ and without the .md suffix.

    ``glob("*.md")`` here was non-recursive, which hid every page under
    ``docs/cli/catalogs/`` and ``docs/cli/tasks/`` from both the missing-docs
    and the orphan-docs halves of the check. Keys carry their subdirectory
    (``catalogs/bigquery``) so a nested page never silently satisfies a
    top-level command name.
    """
    if not CLI_DOCS_DIR.is_dir():
        sys.exit(f"ERROR: missing docs directory {CLI_DOCS_DIR}")
    return {
        str(p.relative_to(CLI_DOCS_DIR).with_suffix("")) for p in _iter_doc_files(CLI_DOCS_DIR)
    }


def _allowed_doc_page(key: str, allowlist: set[str]) -> bool:
    """Allowed by an exact key, or by a directory entry such as ``tasks/``."""
    if key in allowlist:
        return True
    return any(entry.endswith("/") and key.startswith(entry) for entry in allowlist)


# ---------------------------------------------------------------------------
# Checks 1, 3, 4: versions of the CLI itself
# ---------------------------------------------------------------------------


def check_version_only() -> int:
    expected = load_supported_version()
    actual = installed_cli_version()
    if expected != actual:
        install_spec = load_supported_install_spec()
        print(
            f"FAIL: supportedCliVersion is {expected!r} but `fluid --version` "
            f"reports {actual!r}.\n"
            f"  Either bump {VERSION_FILE.relative_to(REPO_ROOT)} or "
            f"`pip install {install_spec}`.",
            file=sys.stderr,
        )
        return 1
    print(f"OK: fluid CLI version matches docs ({expected}).")
    return 0


_FLUIDVERSION_RE = re.compile(r"""fluidVersion:\s*["']?(\d+\.\d+\.\d+)""")


def check_scaffold_version() -> int:
    """Assert ``fluid init --quickstart`` emits the pinned quickstartScaffoldVersion.

    Runs the real scaffold in a temp dir and reads the emitted ``fluidVersion``,
    so the docs can never silently drift from what the quickstart actually
    writes. Passes (no-op) when the pin is absent.
    """
    expected = load_quickstart_scaffold_version()
    if not expected:
        print("OK: no quickstartScaffoldVersion pinned - skipping scaffold check.")
        return 0
    with tempfile.TemporaryDirectory() as tmp:
        try:
            subprocess.run(
                ["fluid", "init", "proj", "--quickstart", "--yes"],
                check=True,
                capture_output=True,
                text=True,
                cwd=tmp,
            )
        except FileNotFoundError:
            sys.exit("ERROR: `fluid` not found on PATH for the scaffold check.")
        except subprocess.CalledProcessError as exc:
            print(
                f"FAIL: `fluid init --quickstart` exited {exc.returncode}.\n"
                f"stdout: {exc.stdout}\nstderr: {exc.stderr}",
                file=sys.stderr,
            )
            return 1
        contract = Path(tmp) / "proj" / "contract.fluid.yaml"
        if not contract.exists():
            print(
                f"FAIL: `fluid init --quickstart` produced no {contract.name}.",
                file=sys.stderr,
            )
            return 1
        match = _FLUIDVERSION_RE.search(contract.read_text(encoding="utf-8"))
        actual = match.group(1) if match else None
    if actual != expected:
        print(
            f"FAIL: `fluid init --quickstart` emits fluidVersion {actual!r} but "
            f"cli-version.json pins quickstartScaffoldVersion={expected!r}.\n"
            "  The quickstart/customer-360 template version changed - reconcile "
            "the pin and every doc page that states the quickstart's fluidVersion.",
            file=sys.stderr,
        )
        return 1
    print(f"OK: `fluid init --quickstart` emits fluidVersion {expected} (matches pin).")
    return 0


def check_pins_against_cli() -> int:
    """cli-version.json's contract pins must exist in the pinned CLI."""
    bundled = bundled_schema_versions()
    if bundled is None:
        print("OK: CLI exposes no bundled schema set - skipping pin cross-check.")
        return 0

    rc = 0
    latest = latest_bundled_schema_version()
    supported = load_supported_contract_version()
    if supported and latest and supported != latest:
        rc = 1
        print(
            f"FAIL: cli-version.json pins supportedFluidContractVersion={supported!r} "
            f"but the pinned CLI's latest stable bundled schema is {latest!r}.",
            file=sys.stderr,
        )
    quickstart = load_quickstart_scaffold_version()
    if quickstart and quickstart not in bundled:
        rc = 1
        print(
            f"FAIL: cli-version.json pins quickstartScaffoldVersion={quickstart!r}, "
            f"which the pinned CLI does not bundle "
            f"(bundled: {', '.join(sorted(bundled))}).",
            file=sys.stderr,
        )
    if rc == 0:
        print(
            f"OK: contract pins agree with the CLI's bundled schemas "
            f"({', '.join(sorted(bundled))}; latest stable {latest})."
        )
    return rc


# ---------------------------------------------------------------------------
# Check 5: the fence-flag oracle
# ---------------------------------------------------------------------------

_FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})\s*(\S*)")

# Fence languages whose lines are real shell invocations. Deliberately narrow:
# a `fluid ...` inside a ```python or ```json block is a string literal or a
# comment, not something a reader will paste into a terminal.
SHELL_FENCE_LANGS = {
    "",
    "bash",
    "sh",
    "shell",
    "shell-session",
    "console",
    "zsh",
    "groovy",  # Jenkinsfile examples
    "yaml",  # CI workflow examples carrying `run: fluid ...`
    "yml",
    "dockerfile",
    "makefile",
    "make",
}

# Leading noise to peel off before the `fluid` token: shell prompts, CI `run:`
# keys, Jenkins `sh`, Dockerfile `RUN`.
_PREFIX_RE = re.compile(
    r"""^\s*
        (?:[-*]\s+)?                                   # yaml list dash
        (?:(?:run|sh|cmd|command|entrypoint)\s*:\s*)?  # CI step key
        (?:[$%>]\s+)?                                  # shell prompt
        (?:(?:RUN|sh|bash)\s+)?                        # Dockerfile RUN / Jenkins sh
        (?:['"]\s*)?                                   # opening quote of sh '...'
    """,
    re.VERBOSE,
)

_INVOCATION_RE = re.compile(r"^fluid\s+[-\w]")

# Tokens that end the command: a comment, a redirect, or a pipe.
_TERMINATORS = {"|", "||", "&&", ";", ">", ">>", "2>", "2>&1", "<", "#", "\\"}

# A token containing any of these is a documentation placeholder, not a literal.
_PLACEHOLDER_CHARS = set("<>{}|$*")

# ALL-CAPS tokens are usage metavariables (`fluid export-odps CONTRACT --out
# PATH`), never literal values. Treating them as placeholders is what keeps
# every synopsis line in docs/cli/*.md out of the results.
_METAVAR_RE = re.compile(r"[A-Z][A-Z0-9_-]+$")


def _iter_shell_lines(path: Path) -> list[tuple[int, str]]:
    """Yield (lineno, logical_line) for every shell-ish fenced code line.

    Backslash line continuations are joined, so a multi-line invocation is
    checked as one command and reported at its first line.
    """
    out: list[tuple[int, str]] = []
    in_fence = False
    fence_char = ""
    fence_len = 0
    include = False

    pending: list[str] = []
    pending_lineno = 0

    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        m = _FENCE_RE.match(raw)
        if m and not in_fence:
            in_fence = True
            fence_char = m.group(1)[0]
            fence_len = len(m.group(1))
            info = m.group(2).strip().lower()
            # ```bash{1,3} / ```console:no-line-numbers -> take the bare word
            lang = re.split(r"[{\s:]", info, maxsplit=1)[0] if info else ""
            include = lang in SHELL_FENCE_LANGS
            pending = []
            continue
        if m and in_fence and m.group(1)[0] == fence_char and len(m.group(1)) >= fence_len:
            in_fence = False
            include = False
            pending = []
            continue
        if not (in_fence and include):
            continue

        stripped = raw.rstrip()
        if stripped.endswith("\\"):
            if not pending:
                pending_lineno = lineno
            pending.append(stripped[:-1].strip())
            continue
        if pending:
            pending.append(stripped.strip())
            out.append((pending_lineno, " ".join(pending)))
            pending = []
            continue
        out.append((lineno, raw))

    return out


def _segments(line: str) -> list[str]:
    """Split a shell line on command separators so `cd x && fluid y` is seen."""
    parts = re.split(r"\s(?:\|\||&&|;|\|)\s", line)
    return [p for p in parts if p.strip()]


def _tokenize(tail: str) -> list[str]:
    tokens: list[str] = []
    for tok in tail.split():
        if tok in _TERMINATORS or tok.startswith("#"):
            break
        # Strip markdown / usage decoration, but keep placeholder markers so
        # the placeholder test below can still see them.
        tok = tok.strip("`'\",")
        tok = re.sub(r"^\[|\]$", "", tok)
        if tok:
            tokens.append(tok)
    return tokens


def _is_placeholder(tok: str) -> bool:
    if tok in {"...", "--"}:
        return True
    if _PLACEHOLDER_CHARS & set(tok):
        return True
    return bool(_METAVAR_RE.fullmatch(tok))


def _resolve_option(flag: str, options: set[str]) -> tuple[str, str | None]:
    """Mirror argparse's option lookup, abbreviation included.

    Returns (status, detail) where status is 'ok', 'unknown' or 'ambiguous'.
    argparse accepts an unambiguous long-option prefix by default, so the
    oracle has to accept one too or it reports invocations that really work.
    """
    if flag in options:
        return "ok", None
    if flag.startswith("--"):
        matches = sorted(o for o in options if o.startswith(flag))
        if len(matches) == 1:
            return "ok", None
        if len(matches) > 1:
            return "ambiguous", ", ".join(matches)
    return "unknown", None


def _consume_option(
    parser: argparse.ArgumentParser,
    tokens: list[str],
    i: int,
    path: list[str],
    problems: list[str],
) -> int:
    """Validate tokens[i] as an option; return the next index to read."""
    raw = tokens[i]
    flag, _, inline_value = raw.partition("=")
    if _is_placeholder(flag):
        return i + 1
    options = _option_strings(parser)
    status, detail = _resolve_option(flag, options)
    if status == "unknown":
        known = ", ".join(sorted(o for o in options if o.startswith("--"))) or "(none)"
        problems.append(f"unknown flag {flag!r} for `{' '.join(path)}` (has: {known})")
        return i + 1
    if status == "ambiguous":
        problems.append(f"ambiguous flag {flag!r} for `{' '.join(path)}` (matches {detail})")
        return i + 1
    if inline_value:
        return i + 1

    nargs_map = _option_nargs(parser)
    if flag in nargs_map:
        nargs = nargs_map[flag]
    else:  # resolved by abbreviation
        nargs = next(
            (n for opt, n in nargs_map.items() if opt.startswith(flag)),
            None,
        )
    if nargs == 0:
        return i + 1
    if isinstance(nargs, int) and nargs > 0:
        return i + 1 + nargs
    if nargs in ("*", "+", "?", argparse.REMAINDER):
        return i + 1
    # nargs None on a plain store action: exactly one value, but only if the
    # next token is not itself a flag.
    if i + 1 < len(tokens) and not tokens[i + 1].startswith("-"):
        return i + 2
    return i + 1


def _check_positional_choices(
    parser: argparse.ArgumentParser, path: list[str], supplied: list[str]
) -> list[str]:
    """Check documented positional values against declared argparse choices.

    Deliberately narrow: only when every positional on the parser takes exactly
    one value, so index alignment between declaration order and the supplied
    tokens is exact.
    """
    positionals = [
        a
        for a in parser._actions
        if not a.option_strings and not isinstance(a, argparse._SubParsersAction)
    ]
    if not positionals or any(p.nargs is not None for p in positionals):
        return []
    problems = []
    for action, tok in zip(positionals, supplied):
        if action.choices is None or _is_placeholder(tok):
            continue
        choices = [str(c) for c in action.choices]
        if tok not in choices:
            problems.append(
                f"invalid value {tok!r} for `{' '.join(path)}` positional "
                f"{action.dest!r} (choices: {', '.join(choices)})"
            )
    return problems


def _check_invocation(root: argparse.ArgumentParser, tokens: list[str]) -> list[str]:
    """Return human-readable problems with one `fluid ...` token list."""
    problems: list[str] = []
    parser = root
    path: list[str] = ["fluid"]

    i = 0
    # Global flags written before the subcommand are checked against the root.
    while i < len(tokens) and tokens[i].startswith("-") and len(tokens[i]) > 1:
        i = _consume_option(parser, tokens, i, path, problems)

    # Walk down nested subparsers as far as the tokens go.
    while i < len(tokens):
        sp = _subparsers_action(parser)
        if sp is None:
            break
        tok = tokens[i]
        if tok.startswith("-") or _is_placeholder(tok):
            break
        if tok not in sp.choices:
            # Only report a plain word. A path or a filename in this slot is a
            # positional argument for a parser whose subcommand is optional.
            if "/" not in tok and "." not in tok:
                problems.append(
                    f"unknown subcommand {tok!r} for `{' '.join(path)}` "
                    f"(choices: {', '.join(sorted(sp.choices))})"
                )
                # No parser to check the rest of the line against; reporting the
                # remaining flags against the parent would be three findings for
                # one defect.
                return problems
            break
        parser = sp.choices[tok]
        path.append(tok)
        i += 1

    positional_tokens: list[str] = []
    while i < len(tokens):
        tok = tokens[i]
        if tok.startswith("-") and len(tok) > 1:
            i = _consume_option(parser, tokens, i, path, problems)
            continue
        positional_tokens.append(tok)
        i += 1

    problems.extend(_check_positional_choices(parser, path, positional_tokens))
    return problems


def _flag_oracle_exempt(rel: str, command: str, allowlist: set[str]) -> bool:
    """Match ``<path glob>`` or ``<path glob>::<invocation substring>``."""
    for entry in allowlist:
        page, _, invocation = entry.partition("::")
        if not fnmatch.fnmatch(rel, page.strip()):
            continue
        if not invocation.strip():
            return True
        if invocation.strip() in command:
            return True
    return False


def check_doc_flags(allowlist: set[str]) -> int:
    root = build_cli_parser()
    findings: list[str] = []
    scanned = 0

    for path in _iter_doc_files(DOCS_DIR):
        rel = str(path.relative_to(REPO_ROOT))
        # Release notes record the surface a past release shipped. The commands
        # in them were real at the time and the pages are never rewritten.
        if path.name.startswith("RELEASE_NOTES_"):
            continue
        for lineno, line in _iter_shell_lines(path):
            for segment in _segments(line):
                stripped = _PREFIX_RE.sub("", segment).strip()
                if not _INVOCATION_RE.match(stripped):
                    continue
                tokens = _tokenize(stripped[len("fluid") :])
                if not tokens:
                    continue
                scanned += 1
                command = "fluid " + " ".join(tokens)
                if _flag_oracle_exempt(rel, command, allowlist):
                    continue
                for problem in _check_invocation(root, tokens):
                    findings.append(f"  {rel}:{lineno}: {problem}\n      {command}")

    if findings:
        print(
            f"FAIL: {len(findings)} documented `fluid` invocation(s) do not match the "
            f"pinned CLI:\n"
            + "\n".join(findings)
            + "\n  Fix the page, or add an entry to "
            f"{ALLOWLIST_FILE.relative_to(REPO_ROOT)} (flag_oracle_ok) if the page "
            "documents a genuinely unreleased capability.",
            file=sys.stderr,
        )
        return 1
    print(f"OK: all {scanned} documented `fluid` invocations match the pinned CLI.")
    return 0


# ---------------------------------------------------------------------------
# Check 6: the version sweep
# ---------------------------------------------------------------------------

HISTORICAL_MARKER = "<!-- cli-version: historical -->"
HISTORICAL_FILE_MARKER = "<!-- cli-version: historical-file -->"

_V = r"[`'\"]?v?(\d+\.\d+\.\d+)"

# Only *baseline* claims - statements about the release a reader should be
# running right now. Historical phrasing ("GA since CLI v0.8.0", "new in CLI
# 0.8.9", "As of CLI 0.10.0, apply hooks ...") is deliberately not matched:
# those sentences are true and rewriting them would be wrong. See the module
# docstring for the marker that covers anything these patterns catch by
# accident.
_VERSION_PATTERNS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "install spec",
        re.compile(r"data-product-forge==(\d+\.\d+\.\d+)"),
        "cli",
    ),
    (
        "docs baseline banner",
        re.compile(r"(?i)docs\s+baseline\W{0,4}\s*CLI\s*" + _V),
        "cli",
    ),
    (
        "baseline claim",
        re.compile(
            r"(?i)\b(?:tracks|tracking|verified\s+against|baseline|pinned\s+to|"
            r"ships\s+at)\b[^.\n]{0,40}?\bCLI\b[^.\n]{0,24}?" + _V
        ),
        "cli",
    ),
    (
        "CLI release bullet",
        # Tolerates words between "CLI release" and the version - the repo-root
        # README writes "Current CLI release documented here: `x.y.z`", which the
        # tighter form missed, letting it sit seven releases stale.
        re.compile(r"(?i)^\s*[-*]\s*(?:current\s+)?CLI\s+release\b[^.\n]{0,32}?" + _V),
        "cli",
    ),
    (
        "fluid --version banner",
        re.compile(r"(?i)FLUID\s+Forge\s+CLI\s+" + _V),
        "cli",
    ),
    (
        "contract fluidVersion",
        re.compile(r"""fluidVersion:\s*["']?(\d+\.\d+\.\d+)"""),
        "contract",
    ),
)


def _historical_lines(lines: list[str]) -> set[int]:
    """0-indexed line numbers exempted by a standalone historical marker."""
    exempt: set[int] = set()
    for idx, line in enumerate(lines):
        if line.strip() != HISTORICAL_MARKER:
            continue
        j = idx + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        if j >= len(lines):
            continue
        exempt.add(j)
        fence = _FENCE_RE.match(lines[j])
        if fence:
            char, length = fence.group(1)[0], len(fence.group(1))
            k = j + 1
            while k < len(lines):
                exempt.add(k)
                close = _FENCE_RE.match(lines[k])
                if close and close.group(1)[0] == char and len(close.group(1)) >= length:
                    break
                k += 1
    return exempt


def check_doc_versions(allowlist: set[str]) -> int:
    expected_cli = load_supported_version()
    bundled = bundled_schema_versions()
    if bundled is None:
        bundled = {
            v
            for v in (load_supported_contract_version(), load_quickstart_scaffold_version())
            if v
        }

    findings: list[str] = []
    for path in _iter_doc_files(DOCS_DIR):
        rel = str(path.relative_to(REPO_ROOT))
        if path.name.startswith("RELEASE_NOTES_"):
            continue
        if any(fnmatch.fnmatch(rel, entry) for entry in allowlist):
            continue
        text = path.read_text(encoding="utf-8")
        if HISTORICAL_FILE_MARKER in text:
            continue
        lines = text.splitlines()
        exempt = _historical_lines(lines)

        for idx, line in enumerate(lines):
            if idx in exempt or HISTORICAL_MARKER in line:
                continue
            # Two patterns can match the same claim ("**Docs Baseline:** CLI
            # `0.9.0`" is both a banner and a baseline claim). Report it once.
            seen: set[tuple[str, str]] = set()
            for label, pattern, kind in _VERSION_PATTERNS:
                for match in pattern.finditer(line):
                    found = match.group(1)
                    if (kind, found) in seen:
                        continue
                    seen.add((kind, found))
                    if kind == "cli":
                        if found == expected_cli:
                            continue
                        findings.append(
                            f"  {rel}:{idx + 1}: {label} says CLI {found}, pin is "
                            f"{expected_cli}\n      {line.strip()[:140]}"
                        )
                    else:
                        if found in bundled:
                            continue
                        findings.append(
                            f"  {rel}:{idx + 1}: {label} {found} is not bundled by the "
                            f"pinned CLI ({', '.join(sorted(bundled))})"
                            f"\n      {line.strip()[:140]}"
                        )

    if findings:
        print(
            f"FAIL: {len(findings)} version claim(s) contradict "
            f"{VERSION_FILE.relative_to(REPO_ROOT)}:\n"
            + "\n".join(findings)
            + f"\n  Update the page, or mark the line historical with "
            f"`{HISTORICAL_MARKER}` (scripts/check_cli_docs.py documents the "
            "three marker scopes).",
            file=sys.stderr,
        )
        return 1
    print(f"OK: every version claim in docs/ agrees with the pin (CLI {expected_cli}).")
    return 0


# ---------------------------------------------------------------------------
# Drivers
# ---------------------------------------------------------------------------


def check_docs_coverage(allowlist: dict[str, set[str]]) -> int:
    rc = 0
    cli_commands = list_cli_subcommands()
    doc_pages = list_doc_pages()

    missing_docs = {
        name
        for name in cli_commands - doc_pages
        if not _allowed_doc_page(name, allowlist["undocumented_ok"])
    }
    orphan_docs = {
        key
        for key in doc_pages - cli_commands
        if not _allowed_doc_page(key, allowlist["docs_only_ok"])
    }

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
            + "\n".join(f"  - {key}.md" for key in sorted(orphan_docs))
            + "\n  Either delete the page or list the path in "
            f"{ALLOWLIST_FILE.relative_to(REPO_ROOT)} (docs_only_ok)."
        )
    if rc == 0:
        print(
            f"OK: all {len(cli_commands)} CLI subcommands are documented "
            f"(docs/cli/ has {len(doc_pages)} pages, subdirectories included)."
        )
    return rc


def check_full() -> int:
    allowlist = load_allowlist()
    rc = check_version_only()
    if check_docs_coverage(allowlist) != 0:
        rc = 1
    if check_scaffold_version() != 0:
        rc = 1
    if check_pins_against_cli() != 0:
        rc = 1
    if check_doc_flags(allowlist["flag_oracle_ok"]) != 0:
        rc = 1
    if check_doc_versions(allowlist["version_sweep_ok"]) != 0:
        rc = 1
    return rc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check forge_docs against the pinned fluid CLI."
    )
    parser.add_argument(
        "--version-only",
        action="store_true",
        help="Only check the installed CLI version against the pinned value.",
    )
    parser.add_argument(
        "--scaffold-only",
        action="store_true",
        help="Only check that `fluid init --quickstart` emits the pinned fluidVersion.",
    )
    parser.add_argument(
        "--flags-only",
        action="store_true",
        help="Only run the fence-flag oracle over docs/**/*.md.",
    )
    parser.add_argument(
        "--versions-only",
        action="store_true",
        help="Only run the version sweep over docs/**/*.md.",
    )
    args = parser.parse_args(argv)

    if args.version_only:
        return check_version_only()
    if args.scaffold_only:
        return check_scaffold_version()
    if args.flags_only:
        return check_doc_flags(load_allowlist()["flag_oracle_ok"])
    if args.versions_only:
        return check_doc_versions(load_allowlist()["version_sweep_ok"])
    return check_full()


if __name__ == "__main__":
    raise SystemExit(main())
