#!/usr/bin/env python3
"""
cast-builder.py — produce world-class asciinema casts with realistic timing.

Asciinema's default `asciinema rec` captures real-time keystrokes, which can
look jittery or rushed. For demo casts we want deliberate, readable pacing:
human-feeling typing, a beat after Enter, output lines that don't all blast
at once, and a final hold so the viewer can read the result.

This module exposes a tiny DSL:

    from cast_builder import Cast, AnsiPalette as A

    cast = Cast(width=92, height=22, title="FLUID Forge — local quickstart")
    cast.prompt()
    cast.typed('pip install "data-product-forge[local]"')
    cast.enter()
    cast.output("  Successfully installed data-product-forge-0.8.0\\n", post=0.4)
    cast.section_break()
    ...
    cast.write("/tmp/casts/local-quickstart.cast")

Timing constants are tuned to feel readable on a 16:9 video crop:

    char_typing_ms     35-55  (with jitter)
    enter_pause_ms     280-380
    line_delay_ms      90-160
    section_break_ms   600-900
    final_hold_ms      1500

Color helpers wrap ANSI escapes in a typed-output-friendly way so demo
authors don't have to remember escape codes.
"""

from __future__ import annotations

import json
import random
import sys
from dataclasses import dataclass, field
from typing import List, Optional


class AnsiPalette:
    """Minimal ANSI helpers for demo output styling."""

    RESET = "\x1b[0m"
    BOLD = "\x1b[1m"
    DIM = "\x1b[2m"

    # Branded colors
    GREEN_OK = "\x1b[32m"        # ✓ success
    BRIGHT_GREEN = "\x1b[1;32m"  # bold success line
    RED_ERR = "\x1b[31m"         # ✗ failure
    YELLOW_WARN = "\x1b[33m"     # ⏳ in-flight, ⚠ warning
    BLUE_ACCENT = "\x1b[36m"     # cyan — code paths, identifiers
    PURPLE_AI = "\x1b[35m"       # AI/LLM/agent lines
    AMBER = "\x1b[33;1m"         # bright yellow — version stamps
    GRAY_DIM = "\x1b[2;37m"      # subtle prose

    @classmethod
    def color(cls, code: str, text: str) -> str:
        return f"{code}{text}{cls.RESET}"


@dataclass
class Cast:
    width: int = 92
    height: int = 22
    title: str = ""
    shell: str = "/bin/zsh"
    term: str = "xterm-256color"
    prompt_str: str = "$ "

    # Timing knobs (seconds)
    char_min: float = 0.030
    char_max: float = 0.055
    enter_pause_min: float = 0.28
    enter_pause_max: float = 0.42
    line_delay_min: float = 0.09
    line_delay_max: float = 0.16
    section_break_min: float = 0.6
    section_break_max: float = 0.9
    final_hold: float = 1.5
    rng_seed: Optional[int] = 42  # deterministic by default so casts are reproducible

    # Pacing preset. "default" suits short snappy casts; "readable" stretches
    # everything so a human watching a long multi-command demo (8+ commands,
    # 30+ seconds) can actually read each line before the next one lands.
    # Concrete tuning: ~1.6× line delays, ~1.4× section breaks, ~1.3× enter
    # pauses, ~1.2× per-char typing — applied in __post_init__ so the named
    # field defaults stay the source of truth.
    pace: str = "default"

    _events: List[List] = field(default_factory=list)
    _t: float = 0.0

    def __post_init__(self) -> None:
        self._rng = random.Random(self.rng_seed)
        # Initial pause before anything happens (viewers need a beat to focus)
        self._t = 0.4

        if self.pace == "readable":
            self.char_min          *= 1.20
            self.char_max          *= 1.20
            self.enter_pause_min   *= 1.30
            self.enter_pause_max   *= 1.30
            self.line_delay_min    *= 1.60
            self.line_delay_max    *= 1.60
            self.section_break_min *= 1.40
            self.section_break_max *= 1.40
            self.final_hold        *= 1.35

    # Smallest gap between consecutive events so no two ever share a timestamp
    # (svg-term's `steps()` animation glitches on collisions and renders
    # frames out of order — the visible symptom is "scrambled" command text).
    _epsilon: float = 0.0008

    # ---- low-level ---------------------------------------------------
    def _emit(self, text: str, dt: float = 0.0) -> None:
        # Drop pure-pause markers (empty text + zero dt). They were a
        # no-op in the old timing model but each one created a duplicate
        # timestamp event under the new strict-monotonic rule.
        if not text and dt == 0.0:
            return

        # CRLF normalization (CRITICAL for svg-term rendering):
        # Bare \n is a LINE FEED — advance one row but keep current column.
        # Terminals need \r\n (CRLF) to wrap back to column 0. Without this,
        # successive output lines "staircase" off the right edge. We rewrite
        # any bare \n to \r\n at the _emit level so callers can write either.
        # First collapse any pre-existing \r\n back to \n, then re-expand —
        # avoids \r\r\n if a caller already used CRLF.
        if "\n" in text:
            text = text.replace("\r\n", "\n").replace("\n", "\r\n")

        if dt:
            self._t += dt

        # Guarantee strictly increasing timestamps. Compare ROUNDED values
        # so the check isn't fooled by floating-point precision differences
        # between the current unrounded `_t` and the rounded `last`.
        rounded_t = round(self._t, 4)
        if self._events:
            last = self._events[-1][0]
            if rounded_t <= last:
                rounded_t = round(last + self._epsilon, 4)

        # Snap _t to the rounded value so subsequent dt math operates on
        # the same time the cast file actually records.
        self._t = rounded_t
        self._events.append([rounded_t, "o", text])

    def _jitter(self, lo: float, hi: float) -> float:
        return self._rng.uniform(lo, hi)

    # ---- prompt & typing --------------------------------------------
    def prompt(self) -> "Cast":
        """Emit a fresh shell prompt."""
        self._emit(self.prompt_str, dt=0.05)
        return self

    def typed(self, text: str, post: float = 0.0) -> "Cast":
        """Type text character-by-character with realistic jitter.

        Multi-line typed text uses \\\\\\n in the source (shell line-continuation
        + CRLF in the cast). We split on \\n so each character emits at its
        own jittered timestamp, but the \\n itself goes through _emit which
        rewrites it to CRLF.
        """
        for ch in text:
            self._emit(ch, dt=self._jitter(self.char_min, self.char_max))
        if post:
            self._emit("", dt=post)
        return self

    def enter(self, pause: Optional[float] = None) -> "Cast":
        """Emit Enter (CRLF) followed by the post-enter pause."""
        self._emit("\r\n", dt=0.0)
        self._emit("", dt=pause if pause is not None else self._jitter(
            self.enter_pause_min, self.enter_pause_max))
        return self

    # ---- output ------------------------------------------------------
    def output(self, text: str, post: Optional[float] = None) -> "Cast":
        """Emit a chunk of program output.

        Ensures the chunk ends with a newline so subsequent output starts
        on a fresh line. The _emit method rewrites bare \\n to \\r\\n so
        callers don't have to think about carriage-returns.
        """
        if not text.endswith("\n"):
            text = text + "\n"
        self._emit(text, dt=0.0)
        # Inter-output delay — small so multi-line output feels natural
        self._emit("", dt=post if post is not None else self._jitter(
            self.line_delay_min, self.line_delay_max))
        return self

    def lines(self, *parts: str, post: Optional[float] = None) -> "Cast":
        """Emit multiple output lines with a small delay between each."""
        for i, p in enumerate(parts):
            self.output(p, post=post if (i == len(parts) - 1) else None)
        return self

    def section_break(self, dt: Optional[float] = None) -> "Cast":
        """A longer pause between commands so the viewer's eye rests."""
        self._emit("", dt=dt if dt is not None else self._jitter(
            self.section_break_min, self.section_break_max))
        return self

    # ---- compound helpers --------------------------------------------
    def run(self, command: str, *output_lines: str,
            section: bool = True, output_post: Optional[float] = None) -> "Cast":
        """Type a command, hit Enter, emit output lines, then section break.

        The most common pattern in a demo. Equivalent to:
            cast.prompt(); cast.typed(cmd); cast.enter()
            cast.lines(*lines); cast.section_break()
        """
        self.prompt()
        self.typed(command)
        self.enter()
        if output_lines:
            self.lines(*output_lines, post=output_post)
        if section:
            self.section_break()
        return self

    # ---- finalize ----------------------------------------------------
    def write(self, path: str) -> None:
        """Hold the final frame, then write the cast to disk."""
        # Hold the final state so the viewer can read it
        self._emit("", dt=self.final_hold)

        header = {
            "version": 2,
            "width": self.width,
            "height": self.height,
            "timestamp": 1714867200,
            "env": {"SHELL": self.shell, "TERM": self.term},
        }
        if self.title:
            header["title"] = self.title

        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps(header) + "\n")
            for ev in self._events:
                f.write(json.dumps(ev) + "\n")

    @property
    def duration(self) -> float:
        return self._t + self.final_hold


# -----------------------------------------------------------------------
# Convenience helpers — branded styled lines with sensible defaults
# -----------------------------------------------------------------------
A = AnsiPalette


def ok(label: str) -> str:
    return f"  {A.color(A.GREEN_OK, '✓')} {label}"


def working(label: str) -> str:
    return f"  {A.color(A.YELLOW_WARN, '⏳')} {label}"


def info(label: str) -> str:
    return f"  {A.color(A.BLUE_ACCENT, 'ℹ')} {label}"


def err(label: str) -> str:
    return f"  {A.color(A.RED_ERR, '✗')} {label}"


def header(text: str) -> str:
    bar = "━" * 60
    return f"\n  {A.color(A.BLUE_ACCENT, bar)}\n  {A.color(A.BOLD, text)}\n  {A.color(A.BLUE_ACCENT, bar)}"


def insight(*lines: str, width: int = 86) -> List[str]:
    """A boxed takeaway block — the one thing the viewer must walk away with.

    Renders as a green-bordered card with a 💡 marker. Pass one or more
    short lines (≤80 visible chars each, ANSI escapes don't count). Returns
    a list of strings; spread into cast.lines(*) to emit.
    """
    inner = width - 2  # account for │ on each side
    top    = f"  {A.color(A.BRIGHT_GREEN, '╭' + '─' * inner + '╮')}"
    blank  = f"  {A.color(A.BRIGHT_GREEN, '│')}{' ' * inner}{A.color(A.BRIGHT_GREEN, '│')}"
    bottom = f"  {A.color(A.BRIGHT_GREEN, '╰' + '─' * inner + '╯')}"

    out = [top, blank]
    # Title row centred
    title = "💡 INSIGHT"
    pad_l = (inner - len(title)) // 2
    pad_r = inner - len(title) - pad_l
    out.append(f"  {A.color(A.BRIGHT_GREEN, '│')}{' ' * pad_l}{A.color(A.BOLD, title)}{' ' * pad_r}{A.color(A.BRIGHT_GREEN, '│')}")
    out.append(blank)

    for line in lines:
        # Strip ANSI escapes to compute visible width
        import re
        visible = re.sub(r'\x1b\[[0-9;]*m', '', line)
        pad = inner - len(visible) - 2  # 2 spaces of left padding
        if pad < 0:
            pad = 0
        out.append(f"  {A.color(A.BRIGHT_GREEN, '│')}  {line}{' ' * pad}{A.color(A.BRIGHT_GREEN, '│')}")

    out.append(blank)
    out.append(bottom)
    return out


def success(text: str) -> str:
    return f"\n  {A.color(A.BRIGHT_GREEN, text)}\n"


# -----------------------------------------------------------------------
# CLI entry — for one-off use; demo scripts usually import Cast directly
# -----------------------------------------------------------------------
if __name__ == "__main__":
    print("cast-builder.py is a library. Demo scripts import Cast from it.", file=sys.stderr)
    sys.exit(2)
