#!/usr/bin/env python3
"""forge-gemini — REAL Gemini API call. Reads $GEMINI_API_KEY from env.

This script invokes the actual `fluid forge` command with the Gemini LLM
provider. The CLI reads $GEMINI_API_KEY directly from the environment
(it never touches our process). Output goes to a temp file, gets piped
through scrub-cast.py, then rendered to SVG.

Usage:
    python3 scripts/demos/forge_gemini.py /tmp/casts/forge-gemini.cast.raw

Then scrub:
    python3 scripts/scrub-cast.py --in /tmp/casts/forge-gemini.cast.raw \
                                  --out /tmp/casts/forge-gemini.cast --strict --report
    rm /tmp/casts/forge-gemini.cast.raw

(generate-demos.sh does this orchestration end-to-end.)
"""

import os
import shutil
import subprocess
import sys


def run() -> int:
    if not os.environ.get("GEMINI_API_KEY"):
        print("error: GEMINI_API_KEY is not set in env", file=sys.stderr)
        return 1

    out_raw = sys.argv[1] if len(sys.argv) > 1 else "/tmp/casts/forge-gemini.cast.raw"
    target_dir = "/tmp/forge-gemini-demo"

    # Clean target so the CLI runs from a known state
    if os.path.exists(target_dir):
        shutil.rmtree(target_dir)

    # Look up the installed fluid CLI from the data-product-forge venv we
    # set up in /tmp/dpf-check earlier. Falls back to PATH lookup.
    fluid = "/tmp/dpf-check/venv/bin/fluid"
    if not os.path.exists(fluid):
        from shutil import which
        fluid = which("fluid")
    if not fluid:
        print("error: fluid CLI not found", file=sys.stderr)
        return 1

    # Hide the urllib3 OpenSSL warning + missing-llm_models.json noise
    # so the cast looks clean. They're known-noisy lines from the venv.
    env = os.environ.copy()
    env["PYTHONWARNINGS"] = "ignore"

    # Build the command. The CLI itself reads GEMINI_API_KEY from env —
    # we never echo or copy the value.
    # Model selection: gemini-1.5-flash was retired and gemini-2.0-flash
    # is "no longer available to new users" per the Gemini API. The current
    # general-availability flagship is gemini-2.5-flash. Allow override via
    # FLUID_DEMO_GEMINI_MODEL for future-proofing.
    model = os.environ.get("FLUID_DEMO_GEMINI_MODEL", "gemini-2.5-flash")

    cmd = [
        fluid, "forge",
        "--domain", "finance",
        "--provider", "local",
        "--llm-provider", "gemini",
        "--llm-model", model,
        "--non-interactive",
        "--target-dir", target_dir,
        "--dry-run",
    ]

    print(f"forge-gemini: recording → {out_raw}", file=sys.stderr)
    print("  (real Gemini API call, scrubbed before persisting)", file=sys.stderr)

    # Use `script -q` to capture a real PTY session so the Rich-formatted
    # output renders correctly. asciinema's --command mode also works but
    # `script` is more portable across shells.
    asciinema = shutil.which("asciinema") or "/opt/homebrew/bin/asciinema"
    rc = subprocess.run(
        [
            asciinema, "rec",
            "--quiet",
            "--idle-time-limit", "1.5",
            "--overwrite",
            "--command", " ".join(f"'{a}'" if " " in a else a for a in cmd),
            out_raw,
        ],
        env=env,
    ).returncode

    if rc != 0:
        print(f"asciinema rec exited {rc}", file=sys.stderr)
        return rc

    print(f"forge-gemini: cast captured ({os.path.getsize(out_raw)} bytes)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(run())
