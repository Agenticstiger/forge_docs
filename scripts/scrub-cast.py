#!/usr/bin/env python3
"""
scrub-cast.py — universal secret redactor for asciinema casts (and anything else).

Reads stdin (or a file via --in), writes scrubbed text to stdout (or --out).
Designed to be the *first* thing anything credential-adjacent flows through
before it ever touches disk in a tracked location.

Patterns redacted (in this order — earlier wins):

  1. Provider-specific high-confidence formats:
       Google API keys      AIza[0-9A-Za-z_-]{35}
       OpenAI keys          sk-[A-Za-z0-9]{40,}
       OpenAI project keys  sk-proj-[A-Za-z0-9_-]{40,}
       Anthropic keys       sk-ant-[A-Za-z0-9_-]{40,}
       JWTs                 eyJ[A-Za-z0-9_=-]+\\.[A-Za-z0-9_=-]+\\.?[A-Za-z0-9_.+/=-]*
       AWS access keys      (AKIA|ASIA)[A-Z0-9]{16}
       AWS secret keys      base64-ish 40-char strings tagged AWS_SECRET_ACCESS_KEY=
       GitHub PATs          (gh[ps]_|github_pat_)[A-Za-z0-9_]{20,}
       Slack tokens         xox[abrespup]-[A-Za-z0-9-]{10,}

  2. Generic shell-format secrets — anything that looks like
       (API_KEY|TOKEN|SECRET|PASSWORD|PASSWD|PASSPHRASE|CREDENTIALS)\\s*=\\s*<16+ chars>
     gets the value swapped to ***REDACTED***. Scoped to ENV-style
     ALL_CAPS_KEYS + the YAML/JSON sibling forms.

  3. Project-specific literal substitution — reads $SNOWFLAKE_ACCOUNT,
     $SNOWFLAKE_USER, $GEMINI_API_KEY from the *current* env (not the cast)
     and replaces literal occurrences with friendly placeholders so the
     demo reads naturally:
       $SNOWFLAKE_ACCOUNT  →  acme-demo
       $SNOWFLAKE_USER     →  demo_user
       $GEMINI_API_KEY     →  <GEMINI_API_KEY>
     Skipped if the env var is empty (won't substitute the empty string).

The scrubber NEVER echoes the env values it reads — it only uses them as
search needles to substitute *out* of the input stream.

Usage:
  cat raw.cast | scripts/scrub-cast.py > clean.cast
  scripts/scrub-cast.py --in raw.cast --out clean.cast
  scripts/scrub-cast.py --in raw.cast --out clean.cast --strict   # exit 1 if any pattern matched
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from typing import List, Tuple

# ---------------------------------------------------------------------
# High-confidence provider patterns — order matters, longer/more-specific first
# ---------------------------------------------------------------------
PROVIDER_PATTERNS: List[Tuple[re.Pattern[str], str, str]] = [
    # Google AI Studio / Cloud API key — AIza + 35 OR MORE alphanum chars (greedy
    # so a 39-char key doesn't leave a 4-char tail visible in the output).
    (re.compile(r"AIza[0-9A-Za-z_\-]{35,}"), "<GEMINI_API_KEY>", "Google API key"),

    # OpenAI keys — order matters: sk-ant- and sk-proj- are checked first because
    # they share the sk- prefix.
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]{40,}"), "<ANTHROPIC_API_KEY>", "Anthropic key"),
    (re.compile(r"sk-proj-[A-Za-z0-9_\-]{40,}"), "<OPENAI_PROJECT_KEY>", "OpenAI project key"),
    (re.compile(r"sk-[A-Za-z0-9]{40,}"), "<OPENAI_API_KEY>", "OpenAI key"),

    # JWT — eyJ.eyJ.signature
    (re.compile(r"eyJ[A-Za-z0-9_=\-]+\.[A-Za-z0-9_=\-]+\.?[A-Za-z0-9_.+/=\-]*"), "<JWT>", "JWT"),

    # AWS access keys + secret keys (when shown as a literal pair)
    (re.compile(r"(AKIA|ASIA)[A-Z0-9]{16}"), "<AWS_ACCESS_KEY_ID>", "AWS key id"),

    # GitHub personal access tokens
    (re.compile(r"(?:gh[ps]_|github_pat_)[A-Za-z0-9_]{20,}"), "<GITHUB_PAT>", "GitHub PAT"),

    # Slack tokens
    (re.compile(r"xox[abrespup]-[A-Za-z0-9\-]{10,}"), "<SLACK_TOKEN>", "Slack token"),

    # Snowflake account locator JWT-ish — usually appear in error-state logs as
    # 8-char-host.region.cloud strings. Conservative: only redact when explicitly
    # tagged via SNOWFLAKE_ACCOUNT below, NOT here (host names are too generic
    # to risk false positives on AWS S3 bucket names etc.).

    # Generic high-entropy hex/base64 keys — long alphanumeric strings inside
    # explicit credential contexts. We skip free-form matching to avoid false
    # positives on UUIDs, file hashes, etc. — those go through the GENERIC_ENV
    # pattern below.
]

# ---------------------------------------------------------------------
# Generic ENV-style: KEY=VALUE where KEY looks credential-ish + value is ≥16 chars
# ---------------------------------------------------------------------
# Match credential-shaped variable names anywhere — the (?<![A-Z]) negative
# lookbehind catches prefixes like AWS_SECRET_ACCESS_KEY (preceded by `_`,
# fine) but skips coined words like SUBSECRET (preceded by `B`, skip).
GENERIC_ENV = re.compile(
    r"(?<![A-Z])(API_KEY|API_TOKEN|TOKEN|ACCESS_TOKEN|REFRESH_TOKEN|"
    r"SECRET_ACCESS_KEY|SECRET_KEY|SECRET|"
    r"PASSWORD|PASSWD|PASSPHRASE|"
    r"CREDENTIALS|CREDENTIAL|PRIVATE_KEY|CLIENT_SECRET|"
    r"AUTH_TOKEN|AUTH_KEY|BEARER_TOKEN)"
    r"(\s*[=:]\s*)"
    r'(["\']?)([A-Za-z0-9+/=_\-\.]{16,})\3'
)


def scrub(text: str, strict: bool = False) -> Tuple[str, int]:
    """Apply all redaction passes. Returns (scrubbed_text, n_substitutions)."""
    total = 0

    # Pass 1 — high-confidence provider formats
    for pattern, replacement, _label in PROVIDER_PATTERNS:
        text, n = pattern.subn(replacement, text)
        total += n

    # Pass 2 — generic ENV form (preserves quote style if value was quoted)
    def _repl_env(m: re.Match[str]) -> str:
        quote = m.group(3) or ""
        return f"{m.group(1)}{m.group(2)}{quote}***REDACTED***{quote}"

    text, n = GENERIC_ENV.subn(_repl_env, text)
    total += n

    # Pass 3 — project-specific literal substitution from current env
    # NEVER printed; only used as search needles
    sub_table: List[Tuple[str, str]] = []
    for env_var, placeholder in [
        ("SNOWFLAKE_ACCOUNT", "acme-demo"),
        ("SNOWFLAKE_USER", "demo_user"),
        ("GEMINI_API_KEY", "<GEMINI_API_KEY>"),
    ]:
        v = os.environ.get(env_var, "")
        if v and len(v) >= 4:  # avoid replacing tiny common strings
            sub_table.append((v, placeholder))

    for needle, placeholder in sub_table:
        # Use literal string substitution (not regex) so account IDs with
        # dashes/dots don't blow up the regex parser.
        n = text.count(needle)
        if n:
            text = text.replace(needle, placeholder)
            total += n

    return text, total


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--in", dest="infile", default="-", help="Input file (default stdin)")
    p.add_argument("--out", dest="outfile", default="-", help="Output file (default stdout)")
    p.add_argument("--strict", action="store_true",
                   help="Exit 1 if no substitutions happened (use for sanity-checking that something matched)")
    p.add_argument("--report", action="store_true",
                   help="Print substitution count to stderr")
    args = p.parse_args()

    if args.infile == "-":
        text = sys.stdin.read()
    else:
        with open(args.infile, "r", encoding="utf-8") as f:
            text = f.read()

    scrubbed, n = scrub(text, strict=args.strict)

    if args.outfile == "-":
        sys.stdout.write(scrubbed)
    else:
        with open(args.outfile, "w", encoding="utf-8") as f:
            f.write(scrubbed)

    if args.report:
        sys.stderr.write(f"scrub-cast: {n} substitution(s)\n")

    if args.strict and n == 0:
        sys.stderr.write("scrub-cast: --strict was set but no patterns matched\n")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
