#!/usr/bin/env python3
"""Resolve and pin the exact VRTV-01 treatment model ID.

Queries the provider Models endpoint with the experiment API account and
determines whether an immutable/snapshot-specific ID exists for the selected
family. Writes MODEL_PIN.json.

This script exists so the model ID is *derived from the provider*, never typed
from memory. Guessing a snapshot ID would silently pin a model nobody verified.

Reads OPENAI_API_KEY / ANTHROPIC_API_KEY from the environment. Touches no VRTV
artifact: no source, view, prompt, or finding is read or transmitted.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

# Family prefix we are pinning for the treatment condition.
TREATMENT_FAMILY = "gpt-5.6-sol"
# Explicit fallback if no immutable snapshot is published. Never the bare
# "gpt-5.6" alias, which could silently re-point to a different model.
TREATMENT_FALLBACK = "gpt-5.6-sol"
FORBIDDEN_ALIASES = {"gpt-5.6", "gpt-5", "gpt-5.6-latest"}

# A snapshot ID carries a date or build suffix, e.g. -2026-08-01 or -20260801.
SNAPSHOT_RE = re.compile(r"-(?:\d{4}-\d{2}-\d{2}|\d{8})$")


def fetch(url: str, headers: dict[str, str]) -> dict:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def openai_models(key: str) -> list[str]:
    data = fetch("https://api.openai.com/v1/models",
                 {"Authorization": f"Bearer {key}"})
    return sorted(m["id"] for m in data.get("data", []))


def anthropic_models(key: str) -> list[str]:
    data = fetch("https://api.anthropic.com/v1/models",
                 {"x-api-key": key, "anthropic-version": "2023-06-01"})
    return sorted(m["id"] for m in data.get("data", []))


def resolve_treatment(ids: list[str]) -> tuple[str, str, list[str]]:
    """Return (pinned_id, basis, candidates)."""
    candidates = [i for i in ids if i.startswith(TREATMENT_FAMILY)]
    snapshots = sorted(i for i in candidates if SNAPSHOT_RE.search(i))
    if snapshots:
        return snapshots[-1], "immutable-snapshot", candidates
    if TREATMENT_FALLBACK in ids:
        return TREATMENT_FALLBACK, "explicit-id-no-snapshot-published", candidates
    return "", "UNRESOLVED", candidates


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path,
                    default=Path(__file__).parent / "MODEL_PIN.json")
    ap.add_argument("--v3-model", default="claude-opus-4-8")
    args = ap.parse_args()

    ok = os.environ.get("OPENAI_API_KEY")
    ak = os.environ.get("ANTHROPIC_API_KEY")
    if not ok:
        print("BLOCKED: OPENAI_API_KEY not set. Cannot query the Models "
              "endpoint, and the treatment model ID must not be guessed.",
              file=sys.stderr)
        return 2

    try:
        oai = openai_models(ok)
    except urllib.error.HTTPError as e:
        print(f"BLOCKED: OpenAI Models query failed: {e.code} {e.reason}",
              file=sys.stderr)
        return 2

    pinned, basis, candidates = resolve_treatment(oai)
    if not pinned:
        print(f"BLOCKED: no model matching '{TREATMENT_FAMILY}' is visible to "
              f"this API account. Do not substitute an alias.", file=sys.stderr)
        print(f"Visible candidates: {candidates or '(none)'}", file=sys.stderr)
        return 2
    if pinned in FORBIDDEN_ALIASES:
        print(f"BLOCKED: resolved to forbidden generic alias '{pinned}'.",
              file=sys.stderr)
        return 2

    record = {
        "treatment": {
            "provider": "OpenAI",
            "family": TREATMENT_FAMILY,
            "pinned_model_id": pinned,
            "pin_basis": basis,
            "candidates_visible": candidates,
            "forbidden_aliases_rejected": sorted(FORBIDDEN_ALIASES),
        },
        "v3": {"provider": "Anthropic", "pinned_model_id": args.v3_model},
    }

    if ak:
        try:
            anth = anthropic_models(ak)
            record["v3"]["visible"] = args.v3_model in anth
            record["v3"]["candidates_visible"] = [
                i for i in anth if i.startswith("claude-opus-4")]
        except urllib.error.HTTPError as e:
            record["v3"]["query_error"] = f"{e.code} {e.reason}"
    else:
        record["v3"]["visible"] = None
        record["v3"]["note"] = "ANTHROPIC_API_KEY not set; not verified"

    args.out.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
