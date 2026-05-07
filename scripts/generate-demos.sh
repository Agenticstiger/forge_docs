#!/usr/bin/env bash
#
# generate-demos.sh — produce all 8 CLI demo SVGs.
#
# Pipeline per cast:
#   1. Generate or capture a .cast file in /tmp/casts/ (gitignored)
#   2. Pipe through scripts/scrub-cast.py — strips known secret formats
#      AND substitutes literal $SNOWFLAKE_ACCOUNT / $SNOWFLAKE_USER /
#      $GEMINI_API_KEY values for friendly placeholders
#   3. Render to docs/.vuepress/public/demos/<name>.svg via svg-term
#   4. Delete the .cast files (raw + scrubbed) — only the SVG persists
#
# Usage:
#   scripts/generate-demos.sh              # all 8 (will skip live ones if env not set)
#   scripts/generate-demos.sh --safe-only  # 6 hand-scripted only
#   scripts/generate-demos.sh --live-only  # 2 live-API only
#   scripts/generate-demos.sh local-quickstart forge-blank  # specific names
#
# Environment for live-API casts:
#   GEMINI_API_KEY                         # required for forge-gemini
#   SNOWFLAKE_{ACCOUNT,USER,PASSWORD,      # all required for snowflake-real
#               WAREHOUSE,ROLE}

set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
CASTS_TMP="/tmp/casts"
DEMOS_OUT="$REPO/docs/.vuepress/public/demos"
SCRUB="$REPO/scripts/scrub-cast.py"

mkdir -p "$CASTS_TMP" "$DEMOS_OUT"

CYAN=$'\033[36m'
GREEN=$'\033[32m'
YELLOW=$'\033[33m'
RED=$'\033[31m'
DIM=$'\033[2m'
RESET=$'\033[0m'

log() { echo "${CYAN}::${RESET} $*"; }
ok()  { echo "${GREEN}✓${RESET} $*"; }
warn(){ echo "${YELLOW}⚠${RESET} $*"; }
err() { echo "${RED}✗${RESET} $*" >&2; }

# Each cast is (name, generator-kind, generator-arg, width, height)
#   generator-kind: "py-script" or "py-live"
#     py-script  → import-and-write via cast_builder DSL (no creds, deterministic)
#     py-live    → asciinema rec wrapping a real CLI invocation (needs creds)
SAFE_DEMOS=(
  "local-quickstart    py-script  scripts/demos/local_quickstart.py    92 24"
  "gcp-quickstart      py-script  scripts/demos/gcp_quickstart.py      92 24"
  "aws-quickstart      py-script  scripts/demos/aws_quickstart.py      92 24"
  "snowflake-quickstart py-script scripts/demos/snowflake_quickstart.py 92 24"
  "forge-blank         py-script  scripts/demos/forge_blank.py         92 22"
  "policy-flow         py-script  scripts/demos/policy_flow.py         92 22"
  "agent-policy        py-script  scripts/demos/agent_policy.py        92 26"
  "forge-multi-provider py-script scripts/demos/forge_multi_provider.py 92 30"
  "source-aligned-bronze py-script scripts/demos/source_aligned_bronze.py 92 26"
  "guided-forge-ux       py-script scripts/demos/guided_forge_ux.py       92 28"
  "day2-ops              py-script scripts/demos/day2_ops.py              92 28"
  "agent-compaction      py-script scripts/demos/agent_compaction.py      92 26"
)

LIVE_DEMOS=(
  # No live captures by default — both forge-gemini and snowflake-real
  # are hand-scripted at full fidelity. To record an actual live capture,
  # run scripts/demos/forge_gemini_real_capture.py manually with a current
  # Gemini model and pipe through the same scrub + svg-term pipeline.
)

# Both of these are hand-scripted but they ARE meant to evoke a live run.
# The real-capture variants exist as separate scripts; the scripted demos
# ship by default because they're more consistent + readable + watchable.
EXTRA_DEMOS=(
  "forge-gemini        py-script  scripts/demos/forge_gemini.py        92 28"
  "snowflake-real      py-script  scripts/demos/snowflake_real.py      92 24"
)

# ----------------------------------------------------------------------
# Live-cast prerequisites
# ----------------------------------------------------------------------
require_env_for_live() {
  local missing=()
  case "$1" in
    forge-gemini)
      [ -z "${GEMINI_API_KEY:-}" ] && missing+=("GEMINI_API_KEY")
      ;;
    snowflake-real)
      for v in SNOWFLAKE_ACCOUNT SNOWFLAKE_USER SNOWFLAKE_PASSWORD SNOWFLAKE_WAREHOUSE SNOWFLAKE_ROLE; do
        [ -z "${!v:-}" ] && missing+=("$v")
      done
      ;;
  esac
  if [ ${#missing[@]} -gt 0 ]; then
    warn "skipping $1 — missing env: ${missing[*]}"
    return 1
  fi
  return 0
}

# ----------------------------------------------------------------------
# Render one cast end-to-end
# ----------------------------------------------------------------------
build_one() {
  local name="$1"
  local kind="$2"
  local generator="$3"
  local width="$4"
  local height="$5"

  local raw="$CASTS_TMP/$name.cast.raw"
  local clean="$CASTS_TMP/$name.cast"
  local svg="$DEMOS_OUT/$name.svg"

  log "${name}: generating cast ($kind)"

  case "$kind" in
    py-script)
      python3 "$REPO/$generator" "$raw" >&2
      ;;
    py-live)
      require_env_for_live "$name" || return 0  # skip, not a hard error
      python3 "$REPO/$generator" "$raw" >&2
      ;;
    *)
      err "unknown generator kind: $kind"
      return 1
      ;;
  esac

  if [ ! -s "$raw" ]; then
    err "$name: cast file is empty"
    return 1
  fi

  # Step 2a: convert v3 → v2 + compress idle gaps (live casts can have
  # 10-20 s LLM-wait pauses that bore the viewer). Cap at 1 s.
  local v2="$CASTS_TMP/$name.cast.v2"
  local max_idle="0"
  if [ "$kind" = "py-live" ]; then max_idle="1.0"; fi
  python3 "$REPO/scripts/cast-v3-to-v2.py" --max-idle "$max_idle" "$raw" "$v2"

  log "${name}: scrubbing secrets"
  python3 "$SCRUB" --in "$v2" --out "$clean" --report 2>&1 | sed 's/^/      /'

  log "${name}: rendering SVG ($width x $height)"
  # No --window flag: <CliCast> wraps the SVG in our own branded chrome
  # (terminal title bar + three Mac dots + click-to-play overlay). Letting
  # svg-term add its own --window chrome would stack two sets of dots.
  svg-term \
    --in "$clean" \
    --out "$svg" \
    --no-cursor \
    --width "$width" \
    --height "$height" \
    >/dev/null 2>&1

  if [ ! -s "$svg" ]; then
    err "$name: SVG render produced empty file"
    return 1
  fi

  # Sanity post-check: scan the FINAL SVG (the only file that lands in git)
  # for known leak patterns. Belt + suspenders.
  if grep -qE 'AIza[0-9A-Za-z_-]{35,}|sk-(ant-|proj-)?[A-Za-z0-9_-]{40,}|eyJ[A-Za-z0-9_=-]+\.[A-Za-z0-9_=-]+' "$svg"; then
    err "$name: LEAK PATTERN matched in final SVG — refusing to keep $svg"
    rm -f "$svg"
    return 1
  fi
  if [ -n "${SNOWFLAKE_ACCOUNT:-}" ] && grep -qF "$SNOWFLAKE_ACCOUNT" "$svg"; then
    err "$name: literal SNOWFLAKE_ACCOUNT value matched in final SVG — refusing to keep $svg"
    rm -f "$svg"
    return 1
  fi

  rm -f "$raw" "$v2" "$clean"
  ok "${name} → $(printf '%s' "$svg" | sed "s|$REPO/||")  ($(stat -f%z "$svg") bytes)"
}

# ----------------------------------------------------------------------
# Main dispatch
# ----------------------------------------------------------------------
mode="all"
case "${1:-}" in
  --safe-only)  mode="safe";  shift ;;
  --live-only)  mode="live";  shift ;;
  --help|-h)
    head -30 "$0" | sed 's|^# \?||'
    exit 0
    ;;
esac

declare -a TARGETS=()
# Use ${arr[@]+"${arr[@]}"} idiom to handle empty arrays under `set -u`.
case "$mode" in
  all)
    TARGETS=("${SAFE_DEMOS[@]}")
    [ ${#EXTRA_DEMOS[@]} -gt 0 ] && TARGETS+=("${EXTRA_DEMOS[@]}")
    [ ${#LIVE_DEMOS[@]}  -gt 0 ] && TARGETS+=("${LIVE_DEMOS[@]}")
    ;;
  safe)
    TARGETS=("${SAFE_DEMOS[@]}")
    [ ${#EXTRA_DEMOS[@]} -gt 0 ] && TARGETS+=("${EXTRA_DEMOS[@]}")
    ;;
  live)
    [ ${#LIVE_DEMOS[@]} -gt 0 ] && TARGETS=("${LIVE_DEMOS[@]}")
    ;;
esac

# Filter by name if positional args given
if [ $# -gt 0 ]; then
  declare -a FILTERED=()
  for arg in "$@"; do
    for row in "${TARGETS[@]}"; do
      read -r n _ _ _ _ <<< "$row"
      if [ "$n" = "$arg" ]; then FILTERED+=("$row"); fi
    done
  done
  TARGETS=("${FILTERED[@]}")
fi

if [ ${#TARGETS[@]} -eq 0 ]; then
  err "no demos selected"; exit 1
fi

echo "${DIM}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo "${DIM}  FLUID Forge — generate ${#TARGETS[@]} demo cast(s)${RESET}"
echo "${DIM}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"

failed=0
for row in "${TARGETS[@]}"; do
  read -r name kind generator width height <<< "$row"
  if ! build_one "$name" "$kind" "$generator" "$width" "$height"; then
    failed=$((failed + 1))
  fi
  echo
done

if [ $failed -gt 0 ]; then
  err "$failed demo(s) failed"
  exit 1
fi

echo "${DIM}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
ok "All ${#TARGETS[@]} demo(s) rendered successfully"
echo "  ${DIM}→ $DEMOS_OUT${RESET}"
