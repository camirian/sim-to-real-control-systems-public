#!/usr/bin/env python3
"""Deterministically enumerate the VRTV-02 bounded authoritative review corpus.

VRTV-01 was not executable: its frozen source set is ~3.62M tokens against a
922,000 input maximum. VRTV-02 narrowly corrects the source-access design by
preregistering a BOUNDED corpus.

This is a fixed allow-list, not retrieval. No RAG, no vector store, no
source-on-demand: retrieval is itself a fallible subsystem and would add an
experimental variable to an experiment about representation.

Extracts from SOURCE_BASELINE_SHA via `git archive`, so the corpus is a pure
function of a commit and these rules. Emits CORPUS_MANIFEST.json.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
import sys
import tarfile
from pathlib import Path

SOURCE_BASELINE = "f03c748ae0b0e6b30de572e9cb7ef49b2c88fe29"
CAMPAIGN = "campaign/results/m4-franka-filtered-vs-unfiltered-v1"

# ---- inclusion rules: (category, predicate, rationale) --------------------
INCLUDE = [
    ("authoritative_docs",
     lambda p: p in {"README.md", "RESULTS.md", "MASTER_PLAN.md",
                     "docs/M4_RUNTIME_VALIDATION.md",
                     "docs/REPRODUCE_CAMPAIGN.md"},
     "Authoritative project/results documentation carrying the campaign "
     "narrative, the reported statistics, the claim boundary, and the "
     "pre-campaign validation history."),
    ("campaign_manifest",
     lambda p: p.startswith("campaign/manifests/") and p.endswith(".json"),
     "Frozen campaign manifest: design, disturbance, filter, sampling, "
     "controller, evidence policy, non-claims and provenance."),
    ("campaign_rollup",
     lambda p: p in {f"{CAMPAIGN}/campaign_results.json",
                     f"{CAMPAIGN}/campaign_summary.json",
                     f"{CAMPAIGN}/preflight.json"},
     "Campaign-level machine-readable rollup: scheduled/valid/invalid/failed "
     "counts, integrity index, per-condition aggregates, preflight record."),
    ("per_run_evidence",
     lambda p: p.startswith(f"{CAMPAIGN}/evidence/") and p.endswith(".json"),
     "Per-run evidence/validation records: checks, thresholds, environment, "
     "overall_passed."),
    ("per_run_raw_evidence",
     lambda p: p.endswith("/raw_evidence.json") and p.startswith(CAMPAIGN),
     "Per-run compact evidence header: controller, filter, rate, reset, "
     "signals_summary, start_state, seed, condition, status, file hashes and "
     "manifest_sha256. Contains no per-sample data."),
    ("per_run_metadata",
     lambda p: p.endswith("/run_meta.json") and p.startswith(CAMPAIGN),
     "Per-run identity: run_id, scenario, seed."),
]

# ---- explicit exclusions --------------------------------------------------
EXCLUDE = [
    ("raw_high_frequency_telemetry",
     lambda p: p.endswith("/telemetry.csv"),
     "40 files, ~2.08M tokens. Raw 200 Hz per-sample signal traces. Remains "
     "authoritative evidence in the repository; excluded from the treatment "
     "model context because it is 57% of a corpus that cannot fit, and no "
     "assertion in the visual packet requires per-sample inspection."),
    ("raw_ground_truth_traces",
     lambda p: p.endswith("/truth.csv"),
     "40 files, ~1.43M tokens. Raw per-sample reference traces. Same "
     "rationale as telemetry.csv."),
]


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def archive_at(repo: Path, sha: str) -> dict[str, bytes]:
    out = subprocess.run(["git", "-C", str(repo), "archive", sha],
                         capture_output=True, check=True).stdout
    files: dict[str, bytes] = {}
    with tarfile.open(fileobj=io.BytesIO(out)) as tf:
        for m in tf.getmembers():
            if m.isfile():
                f = tf.extractfile(m)
                if f:
                    files[m.name] = f.read()
    return files


def classify(path: str):
    for cat, pred, why in INCLUDE:
        if pred(path):
            return "include", cat, why
    for cat, pred, why in EXCLUDE:
        if pred(path):
            return "exclude", cat, why
    return "out_of_scope", None, None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", type=Path, required=True)
    ap.add_argument("--sha", default=SOURCE_BASELINE)
    ap.add_argument("--out", type=Path, default=Path(__file__).parent / "CORPUS_MANIFEST.json")
    ap.add_argument("--emit-dir", type=Path,
                    help="optional: write the corpus files here for staging")
    args = ap.parse_args()

    files = archive_at(args.repo, args.sha)
    included, excluded = [], []
    for path in sorted(files):
        verdict, cat, why = classify(path)
        blob = files[path]
        rec = {"path": path, "bytes": len(blob),
               "sha256": sha256_bytes(blob), "category": cat}
        if verdict == "include":
            included.append(rec)
        elif verdict == "exclude":
            excluded.append(rec)

    manifest = {
        "source_baseline_sha": args.sha,
        "rule_version": 1,
        "retrieval": "none - fixed preregistered allow-list",
        "included_file_count": len(included),
        "included_bytes": sum(r["bytes"] for r in included),
        "excluded_file_count": len(excluded),
        "excluded_bytes": sum(r["bytes"] for r in excluded),
        "inclusion_categories": {c: w for c, _, w in INCLUDE},
        "exclusion_categories": {c: w for c, _, w in EXCLUDE},
        "included": included,
        "excluded": excluded,
    }
    args.out.write_text(json.dumps(manifest, indent=2) + "\n")

    if args.emit_dir:
        args.emit_dir.mkdir(parents=True, exist_ok=True)
        for rec in included:
            dest = args.emit_dir / rec["path"]
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(files[rec["path"]])

    by_cat: dict[str, list[int]] = {}
    for r in included:
        by_cat.setdefault(r["category"], [0, 0])
        by_cat[r["category"]][0] += 1
        by_cat[r["category"]][1] += r["bytes"]
    print(f"source_baseline {args.sha}")
    print(f"{'category':26s} {'files':>5s} {'bytes':>12s}")
    for c, (n, b) in sorted(by_cat.items()):
        print(f"  {c:24s} {n:5d} {b:12,d}")
    print(f"  {'INCLUDED TOTAL':24s} {len(included):5d} "
          f"{sum(r['bytes'] for r in included):12,d}")
    print(f"  {'EXCLUDED':24s} {len(excluded):5d} "
          f"{sum(r['bytes'] for r in excluded):12,d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
