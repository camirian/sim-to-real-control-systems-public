#!/usr/bin/env bash
# Deterministic render of the VRTV-01 visual packet.
# Pinned so V1's stimulus is reproducible and auditable.
set -euo pipefail
cd "$(dirname "$0")"

MMDC_PKG="@mermaid-js/mermaid-cli@11.12.0"
THEME="neutral"
BACKGROUND="white"
WIDTH=1600
SCALE=2

mkdir -p views
for f in views/*.mmd; do
  base="${f%.mmd}"
  npx --yes "$MMDC_PKG" \
    --input "$f" \
    --output "${base}.png" \
    --theme "$THEME" \
    --backgroundColor "$BACKGROUND" \
    --width "$WIDTH" \
    --scale "$SCALE"
done

sha256sum views/*.mmd views/*.png > VIEW_HASHES.txt
echo "--- rendered. hashes:"
cat VIEW_HASHES.txt
