#!/usr/bin/env python3
"""
cast-v3-to-v2.py — convert asciinema v3 cast files to v2 format.

asciinema 3.x defaults to recording in v3 format, but `svg-term-cli`
(and many other downstream tools) still only understand v1 and v2.

The two formats differ in the header only:
  v2:  {"version": 2, "width": W, "height": H, ...}
  v3:  {"version": 3, "term": {"cols": W, "rows": H}, "command": ...,
        "idle_time_limit": ..., "env": ...}

Event lines (`[t, "o"|"i"|"x"|"r", data]`) are identical between v2 and
v3, so we just rewrite the header and pass events through verbatim.
"""

from __future__ import annotations

import json
import sys


def convert(text: str, max_idle: float = 0.0) -> str:
    """Convert v3 → v2 with optional idle-gap compression.

    Critical difference: v3 events use RELATIVE timestamps (delta from
    previous event), v2 uses ABSOLUTE timestamps (cumulative from start).
    Tools like svg-term-cli only understand v2's absolute-time model — if
    you hand them a v3 cast with relative deltas, every event lands at
    t≈0 and the rendered animation has effectively zero duration.

    `max_idle` caps any single inter-event gap. Useful for shrinking
    long LLM-streaming pauses (10–20 s wait → 1 s cap) so the resulting
    cast is watchable. Set to 0 to keep original timing.

    Also strips "x" (exit-code) events, which svg-term renders as literal
    "0" / "1" output if left in.
    """
    out_lines: list[str] = []
    is_v3 = False
    cumulative_t = 0.0

    first = True
    for line in text.splitlines():
        if not line.strip():
            continue

        if first:
            first = False
            try:
                hdr = json.loads(line)
            except json.JSONDecodeError:
                out_lines.append(line)
                continue

            if hdr.get("version") == 3:
                is_v3 = True
                term = hdr.get("term") or {}
                v2 = {
                    "version": 2,
                    "width": term.get("cols", 80),
                    "height": term.get("rows", 24),
                    "timestamp": hdr.get("timestamp", 0),
                    "env": hdr.get("env") or {"SHELL": "/bin/zsh", "TERM": "xterm-256color"},
                }
                if "title" in hdr:
                    v2["title"] = hdr["title"]
                if "idle_time_limit" in hdr:
                    v2["idle_time_limit"] = hdr["idle_time_limit"]
                out_lines.append(json.dumps(v2))
            else:
                # Already v1 / v2 — pass through
                out_lines.append(line)
            continue

        # Event line
        try:
            evt = json.loads(line)
        except json.JSONDecodeError:
            out_lines.append(line)
            continue

        if not (isinstance(evt, list) and len(evt) >= 2):
            out_lines.append(line)
            continue

        kind = evt[1] if len(evt) >= 2 else None

        # Drop exit-code events — svg-term renders them as literal "0"/"1"
        if kind == "x":
            continue

        if is_v3:
            # Convert relative dt → absolute timestamp, with optional cap
            try:
                dt = float(evt[0])
            except (TypeError, ValueError):
                out_lines.append(line)
                continue
            if max_idle > 0 and dt > max_idle:
                dt = max_idle
            cumulative_t += dt
            evt[0] = round(cumulative_t, 4)
            out_lines.append(json.dumps(evt))
        else:
            # v2 cast — also apply idle-compression if requested by
            # rebuilding absolute timestamps (which the v2 cast already has).
            if max_idle > 0:
                try:
                    abs_t = float(evt[0])
                except (TypeError, ValueError):
                    out_lines.append(line)
                    continue
                # Treat first event as anchor at its given t; subsequent
                # gaps get capped.
                if cumulative_t == 0.0:
                    cumulative_t = abs_t
                else:
                    gap = max(0.0, abs_t - cumulative_t)
                    if gap > max_idle:
                        gap = max_idle
                    cumulative_t = cumulative_t + gap
                evt[0] = round(cumulative_t, 4)
                out_lines.append(json.dumps(evt))
            else:
                out_lines.append(line)

    return "\n".join(out_lines) + "\n"


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description="Convert asciinema v3 → v2 with optional idle compression.")
    p.add_argument("infile", nargs="?", default="-")
    p.add_argument("outfile", nargs="?", default="-")
    p.add_argument("--max-idle", type=float, default=0.0,
                   help="Cap any inter-event gap to this many seconds (0 = keep original). Useful for trimming long LLM-wait pauses.")
    args = p.parse_args()

    if args.infile in ("-", ""):
        text = sys.stdin.read()
    else:
        with open(args.infile, "r", encoding="utf-8") as f:
            text = f.read()

    out = convert(text, max_idle=args.max_idle)

    if args.outfile in ("-", ""):
        sys.stdout.write(out)
    else:
        with open(args.outfile, "w", encoding="utf-8") as f:
            f.write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
