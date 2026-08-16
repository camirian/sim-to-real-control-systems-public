#!/usr/bin/env python3
"""Deterministic visual-to-source coverage check for VRTV-02.

FAIRNESS GATE. If a CLEAN visual stimulus asserts something a reviewer cannot
verify from the bounded review corpus, then V1/V2 reviewers are being shown
claims they are structurally unable to check, while V0 is not. That is a design
defect, not an experimental result.

Enumerates every material factual assertion encoded in clean Views A-D and
requires each to be supported by at least one artifact in the corpus. Exits
non-zero if any assertion is unsupported.

This checks CORPUS COVERAGE, not correctness of the diagrams. Whether the source
agrees with the diagram is the reviewers' job -- this only proves they CAN look.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# (id, view, assertion, [regex patterns; ANY match = supported])
ASSERTIONS = [
    ("A1", "A", "Simulator is Isaac Sim with a Franka articulation",
     [r"Isaac\s*Sim", r"franka"]),
    ("A2", "A", "Seeded disturbance is 25 Hz plus AWGN",
     [r"AWGN", r"\b25(\.0+)?\s*Hz", r'"?tone_hz"?\s*[:=]\s*25']),
    ("A3", "A", "Disturbance is injected before the condition split, so both arms share it",
     [r"inject", r"disturb"]),
    ("A4", "A", "Filter is a 4th-order Butterworth IIR",
     [r"Butterworth", r'"?order"?\s*[:=]\s*4']),
    ("A5", "A", "Filter cutoff is 5 Hz",
     [r"cutoff", r'"?cutoff_hz"?\s*[:=]\s*5']),
    ("A6", "A", "The in-loop filter path is causal",
     [r"causal"]),
    ("A7", "A", "Unfiltered arm is identity/passthrough at 0 dB",
     [r"passthrough", r"identity"]),
    ("A8", "A", "Controller is WaypointTracker with an exogenous time reference",
     [r"WaypointTracker", r"exogenous"]),
    ("A9", "A", "Loop is closed: controller commands return to the simulator",
     [r"joint[_ ]command", r"closed[- ]loop", r"command"]),
    ("A10", "A", "Raw telemetry targets 200 Hz",
     [r"\b200(\.0+)?\s*Hz", r'"?target_hz"?\s*[:=]\s*200', r'"?rate"?']),
    ("A11", "A", "Runs produce a gauntlet/evidence packet",
     [r"gauntlet", r"evidence"]),

    ("B1", "B", "Frozen campaign manifest defines 20 paired seeds",
     [r"\b20\b.{0,40}seed", r"seed.{0,40}\b20\b", r'"?seeds"?']),
    ("B2", "B", "A campaign harness executes the runs",
     [r"harness", r"campaign"]),
    ("B3", "B", "40 scheduled runs = 20 filtered + 20 unfiltered",
     [r"\b40\b", r'"?scheduled"?']),
    ("B4", "B", "Per-run raw telemetry is produced",
     [r"telemetry"]),
    ("B5", "B", "Per-run evidence packets carry checks",
     [r'"?checks"?', r"evidence"]),
    ("B6", "B", "Manifest/hash verification occurs",
     [r"manifest_sha256", r"sha256", r"integrity"]),
    ("B7", "B", "Aggregation is performed by scripts/build_results.py",
     [r"build_results\.py"]),
    ("B8", "B", "RESULTS.md is the aggregated result artifact",
     [r"RESULTS\.md"]),
    ("B9", "B", "Public claims are bounded",
     [r"non[_ ]claims", r"does not (establish|claim)", r"claim"]),
    ("B10", "B", "Committed evidence is reproducible CPU-only without Isaac",
     [r"CPU[- ]only", r"without Isaac", r"reproduc"]),

    ("C1", "C", "A pre-campaign validation phase existed",
     [r"pre-campaign", r"runtime validation", r"preflight"]),
    ("C2", "C", "A 30.02 Hz sampling-rate defect was found",
     [r"30\.02"]),
    ("C3", "C", "25 Hz would alias near 5 Hz at that rate",
     [r"alias"]),
    ("C4", "C", "A stageMetersPerUnit defect passed static contract but emitted zero",
     [r"stageMetersPerUnit"]),
    ("C5", "C", "A pilot endogenous-reference defect was found",
     [r"endogenous"]),
    ("C6", "C", "Defects were fixed before the manifest freeze",
     [r"freeze|frozen", r"manifest"]),
    ("C7", "C", "Campaign returned 40 valid / 0 failed / 0 missing",
     [r'"?valid"?\s*[:=]\s*40', r"40/40", r'"?failed"?\s*[:=]\s*0']),

    ("D1", "D", "Filtered feedback had lower tracking RMS in the tested scenario",
     [r"tracking_rms_error", r"tracking RMS"]),
    ("D2", "D", "The causal filter attenuated the injected 25 Hz disturbance",
     [r"filter_attenuation_db", r"attenuat"]),
    ("D3", "D", "Committed evidence is reproducible/inspectable without Isaac",
     [r"CPU[- ]only", r"without Isaac", r"reproduc"]),
    ("D4", "D", "NON-CLAIM: no physical hardware performance",
     [r"hardware"]),
    ("D5", "D", "NON-CLAIM: no sim-to-real transfer",
     [r"sim-to-real|sim2real"]),
    ("D6", "D", "NON-CLAIM: no robot safety or certification",
     [r"safety", r"certification"]),
    ("D7", "D", "NON-CLAIM: no Isaac Sim 6.0.1 GA equivalence",
     [r"GA\b", r"6\.0\.1"]),
    ("D8", "D", "NON-CLAIM: no generalization to other robots/scenarios",
     [r"generaliz"]),
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path,
                    default=Path(__file__).parent / "COVERAGE_REPORT.json")
    args = ap.parse_args()

    files = {}
    for p in sorted(args.corpus_dir.rglob("*")):
        if p.is_file():
            files[str(p.relative_to(args.corpus_dir))] = p.read_text(
                encoding="utf-8", errors="replace")

    results, unsupported = [], []
    for aid, view, text, pats in ASSERTIONS:
        hits = []
        for rel, content in files.items():
            for pat in pats:
                m = re.search(pat, content, re.IGNORECASE)
                if m:
                    hits.append({"artifact": rel, "pattern": pat,
                                 "excerpt": content[max(0, m.start()-60):m.end()+60]
                                            .replace("\n", " ")[:150]})
                    break
        rec = {"id": aid, "view": view, "assertion": text,
               "supported": bool(hits), "supporting_artifact_count": len(hits),
               "evidence": hits[:3]}
        results.append(rec)
        if not hits:
            unsupported.append(rec)

    report = {"corpus_dir": str(args.corpus_dir),
              "assertions_total": len(ASSERTIONS),
              "assertions_supported": len(ASSERTIONS) - len(unsupported),
              "assertions_unsupported": len(unsupported),
              "unsupported": unsupported, "results": results}
    args.out.write_text(json.dumps(report, indent=2) + "\n")

    print(f"{'id':5s} {'view':5s} {'files':>6s}  assertion")
    for r in results:
        mark = "OK " if r["supported"] else "MISS"
        print(f"{mark} {r['id']:4s} {r['view']:4s} "
              f"{r['supporting_artifact_count']:6d}  {r['assertion'][:66]}")
    print(f"\nsupported {report['assertions_supported']}/{report['assertions_total']}")
    if unsupported:
        print("\nDESIGN DEFECT - unsupported visual assertions:")
        for r in unsupported:
            print(f"  {r['id']} ({r['view']}): {r['assertion']}")
        return 1
    print("PASS: every material visual assertion is verifiable from the bounded corpus.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
