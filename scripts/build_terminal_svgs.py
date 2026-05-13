#!/usr/bin/env python3
"""Build deterministic terminal-snapshot SVGs for the SDK & Plugins docs.

Each "scene" is a list of (delay_seconds, text) tuples. We render an asciinema
v2 cast file and pipe it through `svg-term` to produce a stable, repository-
committed SVG that VuePress serves as a static asset.

The animation timing is intentionally compact (each line ~120ms) so the SVG
plays as a brisk demo when viewed in a browser. The cast can also be rendered
to a single still frame with `svg-term --at <ms>`.

KNOWN ISSUE — DO NOT WIRE BACK INTO DOCS BEFORE FIXING (2026-05-13)
==================================================================
The current scenes use ANSI color codes (B/DIM/G/R/Y/C/RST constants below).
`svg-term` appears to count those escape bytes toward the terminal column
width, so long-but-visible-short lines wrap mid-token in the rendered output
(e.g. `STRIPE_LIVE_KEY` splits as `S` + `TRIPE_LIVE_KEY`, `extensions.steward-
required` splits as `extensions.steward-requ` + `ired:`). The 4 SVGs this
script produced were briefly wired into the docs and then removed in the
0.8.3 branch when the layout was inspected.

To re-enable cleanly, pick one of:
  (a) Bump every scene's `width` to 120+ and re-verify (cheap, may still
      wrap on the longest validator-finding lines).
  (b) Strip the ANSI color codes from line content (keep `RST` only at line
      end), accept monochrome stills. Loses the green check / red cross / dim
      log-line styling but eliminates the wrap math entirely.
  (c) Switch to a different SVG renderer that counts visible width, not
      byte length (e.g. `termsvg`, `agg`+`cargo install`, or hand-rolled
      SVG via a small `<text>`-emitting script).

Once one of those lands and the stills look clean, restore the four
`![…](/sdk-and-plugins/terminals/<name>.svg)` references that this commit
removed from:
  - docs/sdk-and-plugins/quickstart.md (Step 0)
  - docs/sdk-and-plugins/examples/hello-scaffold.md (Run it)
  - docs/sdk-and-plugins/examples/steward-validator.md (End-to-end section)
  - docs/sdk-and-plugins/examples/apply-hook-prod-key-guard.md (End-to-end)
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "docs" / ".vuepress" / "public" / "sdk-and-plugins" / "terminals"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ANSI shorthand for the cast strings.
B = "\x1b[1m"        # bold
DIM = "\x1b[2m"      # dim
G = "\x1b[32m"       # green
R = "\x1b[31m"       # red
Y = "\x1b[33m"       # yellow
C = "\x1b[36m"       # cyan
RST = "\x1b[0m"      # reset
CHK = f"{G}✓{RST}"
XMK = f"{R}✗{RST}"

PROMPT = f"{B}{C}~/my-product{RST} $ "

SCENES: dict[str, dict] = {
    "quickstart-generate": {
        "title": "fluid generate custom-scaffold",
        "width": 80,
        "height": 14,
        "frames": [
            (0.0, PROMPT),
            (0.4, "fluid generate custom-scaffold\n"),
            (0.7, f"{DIM}Resolving libraries…{RST}\n"),
            (1.0, f"{DIM}Loading bundle hello-scaffold@entrypoint{RST}\n"),
            (1.3, f"{DIM}Rendering 1 file{RST}\n"),
            (1.5, f"{CHK} 1 file written, 0 failed\n"),
            (1.6, f"  {B}README.md{RST}\n"),
            (1.8, PROMPT),
            (2.4, "cat README.md\n"),
            (2.7, f"{B}# My First Product{RST}\n\n"),
            (2.9, "Generated from the hello-scaffold plugin.\n"),
            (3.2, PROMPT),
        ],
    },
    "hello-scaffold-pytest": {
        "title": "pytest — 20 inherited conformance tests pass",
        "width": 80,
        "height": 18,
        "frames": [
            (0.0, f"{B}{C}~/my-first-plugin{RST} $ "),
            (0.4, "pytest\n"),
            (0.7, "============================= test session starts =============================\n"),
            (0.85, "platform darwin -- Python 3.12.6, pytest-7.4.4\n"),
            (1.0, "collected 20 items\n\n"),
            (1.15, "tests/test_scaffold.py "),
            (1.20, f"{G}.{RST}"),
            (1.24, f"{G}.{RST}"),
            (1.28, f"{G}.{RST}"),
            (1.32, f"{G}.{RST}"),
            (1.36, f"{G}.{RST}"),
            (1.40, f"{G}.{RST}"),
            (1.44, f"{G}.{RST}"),
            (1.48, f"{G}.{RST}"),
            (1.52, f"{G}.{RST}"),
            (1.56, f"{G}.{RST}"),
            (1.60, f"{G}.{RST}"),
            (1.64, f"{G}.{RST}"),
            (1.68, f"{G}.{RST}"),
            (1.72, f"{G}.{RST}"),
            (1.76, f"{G}.{RST}"),
            (1.80, f"{G}.{RST}"),
            (1.84, f"{G}.{RST}"),
            (1.88, f"{G}.{RST}"),
            (1.92, f"{G}.{RST}"),
            (1.96, f"{G}.{RST}"),
            (2.05, f"  {DIM}[100%]{RST}\n\n"),
            (2.20, f"============================= {G}20 passed{RST} in 0.07s ==============================\n"),
            (2.50, f"{B}{C}~/my-first-plugin{RST} $ "),
        ],
    },
    "steward-validator": {
        "title": "fluid validate — Validator plugin emits a structured finding",
        "width": 88,
        "height": 14,
        "frames": [
            (0.0, f"{B}{C}~/order-events{RST} $ "),
            (0.4, "fluid validate contract.fluid.yaml\n"),
            (0.7, f"{DIM}Loading contract.fluid.yaml{RST}\n"),
            (1.0, f"{DIM}Running 1 schema check + 1 plugin validator{RST}\n"),
            (1.3, f"{XMK} {B}Validation failed{RST}\n"),
            (1.4, f"  {B}Errors:{RST}\n"),
            (1.6, f"    {R}extensions.steward-required: STEWARD_ID_MISSING{RST}:\n"),
            (1.7, "      Contract 'order-events' is missing the required label 'principal.steward.id'.\n"),
            (1.9, f"      {Y}→ Add metadata.labels['principal.steward.id'] with the data steward.{RST}\n"),
            (2.2, f"{B}{C}~/order-events{RST} $ "),
            (2.6, f"# fix the contract, re-run\n"),
            (2.9, f"{B}{C}~/order-events{RST} $ "),
            (3.1, "fluid validate contract.fluid.yaml\n"),
            (3.5, f"{CHK} {B}Contract valid{RST} against fluidVersion 0.7.3\n"),
            (3.7, f"{B}{C}~/order-events{RST} $ "),
        ],
    },
    "apply-hook-guard": {
        "title": "fluid apply — apply hook blocks prod without STRIPE_LIVE_KEY",
        "width": 92,
        "height": 12,
        "frames": [
            (0.0, f"{B}{C}~/order-events{RST} $ "),
            (0.3, "DEPLOY_ENV=prod fluid apply contract.fluid.yaml --env prod\n"),
            (0.6, f"{DIM}Loading contract.fluid.yaml (env=prod){RST}\n"),
            (0.9, f"{DIM}Running 1 apply hook: prod-key-guard{RST}\n"),
            (1.2, f"{R}error: apply hook prod-key-guard: STRIPE_LIVE_KEY required for prod deploy{RST}\n"),
            (1.4, f"{R}error: apply aborted by an apply-time plugin hook.{RST}\n"),
            (1.5, f"       {Y}Pass --force-pattern-drift to override.{RST}\n"),
            (1.9, f"{B}{C}~/order-events{RST} $ "),
            (2.3, f"export STRIPE_LIVE_KEY=$(op read 'op://prod/stripe/live-key')\n"),
            (2.6, f"{B}{C}~/order-events{RST} $ "),
            (2.8, "DEPLOY_ENV=prod fluid apply contract.fluid.yaml --env prod\n"),
            (3.2, f"{CHK} apply hook prod-key-guard passed\n"),
            (3.4, f"{CHK} {B}applied 7 actions, 0 failed{RST}\n"),
            (3.7, f"{B}{C}~/order-events{RST} $ "),
        ],
    },
}


def build_cast(scene: dict) -> str:
    """Render a scene as asciinema v2 JSON-lines text."""
    header = {
        "version": 2,
        "width": scene["width"],
        "height": scene["height"],
        "timestamp": 1715600000,
        "title": scene["title"],
        "env": {"SHELL": "/bin/zsh", "TERM": "xterm-256color"},
    }
    lines = [json.dumps(header)]
    for at, text in scene["frames"]:
        lines.append(json.dumps([round(at, 3), "o", text]))
    return "\n".join(lines) + "\n"


def render(name: str, scene: dict) -> Path:
    cast_path = Path("/tmp") / f"{name}.cast"
    svg_path = OUT_DIR / f"{name}.svg"
    cast_path.write_text(build_cast(scene))

    # Render the FINAL frame (still snapshot) — looks like a screenshot of the
    # finished session. svg-term picks the last frame implicitly when --at
    # exceeds the cast duration; we set --at to a comfortable margin past it.
    cmd = [
        "svg-term",
        "--in", str(cast_path),
        "--out", str(svg_path),
        "--padding", "16",
        "--window",
        "--width", str(scene["width"]),
        "--height", str(scene["height"]),
        "--no-cursor",
    ]
    subprocess.run(cmd, check=True)
    return svg_path


def main() -> int:
    if not shutil.which("svg-term"):
        print("svg-term not on PATH; install with `npm i -g svg-term-cli`", file=sys.stderr)
        return 1
    for name, scene in SCENES.items():
        out = render(name, scene)
        print(f"wrote {out}  ({out.stat().st_size:>5} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
