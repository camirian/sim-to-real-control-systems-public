#!/usr/bin/env bash
# Deterministic render of the VRTV-01 SEEDED control variants.
# Uses the identical pinned procedure as render_views.sh.
# Deliberately separate so that rendering seeded controls can never
# rewrite or re-render a clean View A-D artifact.
set -euo pipefail
cd "$(dirname "$0")"

MMDC_PKG="@mermaid-js/mermaid-cli@11.12.0"
THEME="neutral"
BACKGROUND="white"
WIDTH=1600
SCALE=2

for f in seeded/*.mmd; do
  base="${f%.mmd}"
  npx --yes "$MMDC_PKG" \
    --input "$f" \
    --output "${base}.png" \
    --theme "$THEME" \
    --backgroundColor "$BACKGROUND" \
    --width "$WIDTH" \
    --scale "$SCALE"
done

sha256sum seeded/*.mmd seeded/*.png > SEEDED_HASHES.txt
echo "--- seeded rendered. hashes:"
cat SEEDED_HASHES.txt
