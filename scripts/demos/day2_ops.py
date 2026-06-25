#!/usr/bin/env python3
"""
day2-ops — high-fidelity scripted demo of the 3am incident-response
flow: `fluid runs status` (where) → `fluid runs logs --component dlq`
(why) → `fluid runs diff` (what) → contract policy fix → `fluid ship`
(repair). ~90 seconds from Slack ping to a shipped fix.

Recasts reels/day2-ops.html into a CliCast.
"""

import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from cast_builder import Cast, A, ok, working, info, err  # type: ignore


def build() -> Cast:
    cast = Cast(
        width=92, height=28,
        title="3am pipeline broke — fluid runs status → logs → diff → ship in 90 seconds",
        pace="readable",
    )

    # 0. The setup — Slack ping
    cast.lines(
        f"  {A.color(A.RED_ERR, '💬')} {A.color(A.BOLD, '#data-ops')}  {A.color(A.GRAY_DIM, '03:14 AM')}",
        f"  {A.color(A.GRAY_DIM, '─────────────────────────────────────────────────────────────')}",
        f"  {A.color(A.RED_ERR, '🚨')} PagerDuty: {A.color(A.BOLD, 'gold.finance.customer_360_v1')} freshness SLA breached",
        f"     last successful run: 6h ago · expected: 1h",
        f"  {A.color(A.GRAY_DIM, '─────────────────────────────────────────────────────────────')}",
        post=0.5,
    )

    cast.section_break(0.4)

    # 1. WHERE — runs status
    cast.run(
        "fluid runs status gold.finance.customer_360_v1 --last 10",
        f"  {A.color(A.BOLD, '📊 Last 10 runs')}",
        f"  {A.color(A.GRAY_DIM, '─────────────────────────────────────────────────────────────')}",
        f"  {A.color(A.BOLD, 'run-id      ts          duration  status      stage')}",
        f"  {A.color(A.GRAY_DIM, '─────────  ──────────  ────────  ──────────  ───────────')}",
        f"  r-2a4f8c3  03:01 AM    {A.color(A.RED_ERR, '38 s')}      {A.color(A.RED_ERR, 'FAIL')}        apply",
        f"  r-2a4f8c2  02:01 AM    {A.color(A.RED_ERR, '41 s')}      {A.color(A.RED_ERR, 'FAIL')}        apply",
        f"  r-2a4f8c1  01:01 AM    {A.color(A.RED_ERR, '37 s')}      {A.color(A.RED_ERR, 'FAIL')}        apply",
        f"  r-2a4f8c0  12:01 AM    {A.color(A.AMBER, '4.2 m')}     {A.color(A.GREEN_OK, 'OK')}",
        f"  {A.color(A.GRAY_DIM, '─────────────────────────────────────────────────────────────')}",
        f"  {A.color(A.BOLD, '3 consecutive failures.')} First failure: {A.color(A.AMBER, 'r-2a4f8c1 (01:01 AM)')}",
        f"  {A.color(A.AMBER, '⚠')}  Stage: {A.color(A.BOLD, 'apply')} — DDL succeeded, build failed",
        output_post=0.18,
    )

    cast.section_break(0.4)

    # 2. WHY — runs logs --component dlq
    cast.run(
        "fluid runs logs gold.finance.customer_360_v1 --run-id r-2a4f8c1 --component dlq",
        f"  {A.color(A.GRAY_DIM, '─────────────────────────────────────────────────────────────')}",
        f"  {A.color(A.GRAY_DIM, '01:01:23  build  ')}{A.color(A.RED_ERR, 'ERROR')}  CHECK constraint failed:",
        f"  {A.color(A.GRAY_DIM, '01:01:23         ')}    {A.color(A.RED_ERR, 'arpu_30d_eur')} expected NOT NULL,",
        f"  {A.color(A.GRAY_DIM, '01:01:23         ')}    got 47 nulls in 12,408 rows",
        f"  {A.color(A.GRAY_DIM, '01:01:23  build  ')}{A.color(A.RED_ERR, 'ERROR')}  Quarantined to dlq:",
        f"  {A.color(A.GRAY_DIM, '01:01:23         ')}    {A.color(A.BLUE_ACCENT, 's3://forge-runtime/dlq/r-2a4f8c1/...')}",
        f"  {A.color(A.GRAY_DIM, '01:01:23  apply ')}{A.color(A.RED_ERR, 'FAIL')}   Hard gate: dq.rules completeness rule failed",
        f"  {A.color(A.GRAY_DIM, '─────────────────────────────────────────────────────────────')}",
        f"  {A.color(A.BOLD, 'Root cause:')} new EU customers without 30-day history",
        f"  {A.color(A.GRAY_DIM, '             (the rule was right; the data shifted)')}",
        output_post=0.18,
    )

    cast.section_break(0.4)

    # 3. WHAT — runs diff
    cast.run(
        "fluid runs diff gold.finance.customer_360_v1 --build customer_360_pipeline --run-a r-2a4f8c0 --run-b r-2a4f8c1",
        f"  {A.color(A.BOLD, '📋 What changed between OK run and first failure')}",
        f"  {A.color(A.GRAY_DIM, '─────────────────────────────────────────────────────────────')}",
        f"  {A.color(A.GRAY_DIM, 'sources:')}",
        f"    {A.color(A.GREEN_OK, '+')} {A.color(A.BLUE_ACCENT, 'eu_signups_q4')}     {A.color(A.GRAY_DIM, '(new region added 12h before first fail)')}",
        f"  {A.color(A.GRAY_DIM, 'metrics:')}",
        f"      {A.color(A.AMBER, '~')} {A.color(A.BLUE_ACCENT, 'arpu_30d_eur')}      {A.color(A.GRAY_DIM, 'now sees < 30 day customers')}",
        f"  {A.color(A.GRAY_DIM, '─────────────────────────────────────────────────────────────')}",
        ok("Drift surface: 1 source added · 1 metric scope changed"),
        info("dq.rules unchanged — they're correct, but assume 30 days of data"),
        output_post=0.18,
    )

    cast.section_break(0.5)

    # 4. The fix — one-line policy update
    cast.lines(
        f"  {A.color(A.BOLD, '✏️  One-line fix in contract.fluid.yaml')}",
        f"  {A.color(A.GRAY_DIM, '─────────────────────────────────────────────────────────────')}",
        f"  {A.color(A.GRAY_DIM, 'dq.rules:')}",
        f"  {A.color(A.GRAY_DIM, '  - id: arpu_complete')}",
        f"  {A.color(A.GRAY_DIM, '    type: completeness')}",
        f"  {A.color(A.GRAY_DIM, '    selector: arpu_30d_eur')}",
        f"  {A.color(A.RED_ERR, '-   threshold: 1.0                  # 100% non-null across ALL rows')}",
        f"  {A.color(A.GREEN_OK, '+   where: customer_age_days >= 30  # scope to full 30-day-window customers')}",
        f"  {A.color(A.GREEN_OK, '+   threshold: 1.0')}",
        f"  {A.color(A.GRAY_DIM, '─────────────────────────────────────────────────────────────')}",
        post=0.4,
    )

    cast.section_break(0.4)

    # 5. SHIP — apply + verify + roll forward
    cast.run(
        "fluid ship --yes",
        working("validate → bundle → plan → apply"),
        ok("Schema 0.7.4 — passed"),
        ok("dq.rules — 8 rules, 1 changed (completeness now scoped via where), no breaking moves"),
        ok("Plan bound: planDigest a4f8c4…  (re-verified before apply)"),
        ok("BigQuery DDL applied — no destructive changes"),
        info("dq gate now accepts partial-window customers — the firing rule is scoped, not removed"),
        f"  {A.color(A.BRIGHT_GREEN, '✓ Ship complete — corrected contract live; the next run clears the gate')}",
        output_post=0.18,
    )

    cast.section_break(0.5)

    # 6. The summary
    cast.lines(
        f"  {A.color(A.GRAY_DIM, '─────────────────────────────────────────────────────────────')}",
        f"  {A.color(A.BOLD, '⏱  Slack ping → ship: ~90 seconds.')}",
        f"  {A.color(A.GRAY_DIM, '03:14:00 ping → 03:14:20 status → 03:14:45 logs → 03:15:08 diff →')}",
        f"  {A.color(A.GRAY_DIM, '03:15:24 fix → 03:15:30 ship.')}",
        f"  {A.color(A.GRAY_DIM, '─────────────────────────────────────────────────────────────')}",
        f"  {A.color(A.BOLD, 'Day-1 ships.')} {A.color(A.GRAY_DIM, 'Day-2 does not surprise.')}",
        post=0.5,
    )

    cast.prompt()
    return cast


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/casts/day2-ops.cast"
    cast = build()
    cast.write(out)
    print(f"day2-ops: {cast.duration:.1f}s → {out}")
