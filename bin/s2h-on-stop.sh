#!/bin/bash
# s2h Stop hook — deterministic completion telemetry
# Fires on every agent Stop; .running check makes it a no-op if s2h wasn't running.
# If LLM already wrote last_result.json (enriched version), this hook skips.

S2H_HOME="$HOME/.s2h"
RUNNING="$S2H_HOME/.running"

# Only act if s2h was running
[ -f "$RUNNING" ] || exit 0

# If LLM already wrote last_result.json with enriched data, just clean up
if [ -f "$S2H_HOME/last_result.json" ]; then
  rm -f "$RUNNING"
  exit 0
fi

# Read start timestamp
START_TS=$(cat "$RUNNING" 2>/dev/null | tr -d '[:space:]')
NOW_TS=$(date +%s)
DUR=$(( NOW_TS - ${START_TS:-$NOW_TS} ))

# Read config
VERSION=$(cat "$S2H_HOME/.version" 2>/dev/null || echo "unknown")
TEL_MODE=$(grep -s 'telemetry=' "$S2H_HOME/config" 2>/dev/null | cut -d= -f2-)
[ "$TEL_MODE" = "off" ] && { rm -f "$RUNNING"; exit 0; }
MODE="${TEL_MODE:-community}"
LANG=$(grep -s 'default_lang=' "$S2H_HOME/config" 2>/dev/null | cut -d= -f2-)

# Detect HTML output: find s2h-*.html files created after .running marker
OUTPUT_DIR=$(grep -s 'output_dir=' "$S2H_HOME/config" 2>/dev/null | cut -d= -f2-)
LATEST_HTML=""
for dir in "${OUTPUT_DIR:-/tmp}" "/tmp"; do
  [ -d "$dir" ] || continue
  candidate=$(find "$dir" -maxdepth 1 -name "s2h-*.html" -newer "$RUNNING" 2>/dev/null | head -1)
  [ -n "$candidate" ] && { LATEST_HTML="$candidate"; break; }
done

if [ -n "$LATEST_HTML" ]; then
  HTML_SIZE=$(wc -c < "$LATEST_HTML" 2>/dev/null | tr -d ' ')
  OK=1
else
  HTML_SIZE=0
  OK=0
fi

# Write last_result.json (basic version — no skill/risk/lines, those are LLM-only)
printf '{"v":"%s","lang":"%s","dur":%d,"ok":%d,"event":"complete","html_size":%d,"mode":"%s","ts":"%s"}\n' \
  "$VERSION" "${LANG:-en}" "$DUR" "$OK" "${HTML_SIZE:-0}" "$MODE" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  > "$S2H_HOME/last_result.json"

rm -f "$RUNNING"
