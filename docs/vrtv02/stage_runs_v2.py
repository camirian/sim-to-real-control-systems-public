#!/usr/bin/env python3
"""Stage isolated VRTV-02 reviewer inputs outside the repository.

Same fail-closed contract as the VRTV-01 stager, with one change: where a
condition receives source, it receives the BOUNDED corpus from
build_corpus.py rather than the whole committed evidence directory.

Never launches a reviewer.
"""
from __future__ import annotations

import argparse, hashlib, json, subprocess, sys
from pathlib import Path

RUNS = ("V0-CLEAN", "V1-CLEAN", "V1-SEEDED", "V2-CLEAN", "V2-SEEDED")
SOURCE_BASELINE = "f03c748ae0b0e6b30de572e9cb7ef49b2c88fe29"
NEEDS_SOURCE_STAGE1 = {"V0-CLEAN", "V2-CLEAN", "V2-SEEDED"}
NEEDS_IMAGES = {"V1-CLEAN", "V1-SEEDED", "V2-CLEAN", "V2-SEEDED"}
CLEAN = ["view_a_system_topology.png", "view_b_evidence_provenance.png",
         "view_c_controls_and_history.png", "view_d_claim_boundary.png"]
SEEDED_SUB = {"view_a_system_topology.png": "view_a_system_topology_seeded.png",
              "view_b_evidence_provenance.png": "view_b_evidence_provenance_seeded.png"}
LEGEND = ("These four images are non-authoritative projections of a completed "
          "simulation campaign. They were hand-authored from prose documentation, "
          "not mechanically derived. They may omit information and they may "
          "contain errors. They are not the system and they are not evidence.\n")


def die(m): print(f"FAIL-CLOSED: {m}", file=sys.stderr); raise SystemExit(2)
def sha256(p: Path) -> str: return hashlib.sha256(p.read_bytes()).hexdigest()


def load_hashes(repo: Path, name: str) -> dict[str, str]:
    out = {}
    for line in (repo / "docs/vrtv01" / name).read_text().splitlines():
        h, rel = line.split()
        out[Path(rel).name] = h
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", type=Path, required=True)
    ap.add_argument("--stage-root", type=Path, required=True)
    args = ap.parse_args()

    repo = args.repo.resolve()
    if not (repo / ".git").exists():
        die("--repo is not a git repository")
    stage = args.stage_root.resolve()
    if stage == repo or repo in stage.parents or stage.is_relative_to(repo):
        die("stage root must be outside the repository")
    for parent in [stage, *stage.parents]:
        if (parent / ".git").exists():
            die(f"repository visible from staging root at {parent}")
    if stage.exists() and any(stage.iterdir()):
        die("staging requires an empty stage root")
    stage.mkdir(parents=True, exist_ok=True); stage.chmod(0o700)

    # 1. build the bounded corpus once -- one enumeration for every condition
    corpus = stage / ".corpus-build"
    subprocess.run([sys.executable, str(repo / "docs/vrtv02/build_corpus.py"),
                    "--repo", str(repo), "--emit-dir", str(corpus),
                    "--out", str(stage / "CORPUS_MANIFEST.json")],
                   check=True, stdout=subprocess.DEVNULL)

    clean_h = load_hashes(repo, "VIEW_HASHES.txt")
    seed_h = load_hashes(repo, "SEEDED_HASHES.txt")

    for run in RUNS:
        s1 = stage / run / "stage-1"; s1.mkdir(parents=True)
        if run in NEEDS_SOURCE_STAGE1:
            dst = s1 / "source"
            subprocess.run(["cp", "-r", str(corpus), str(dst)], check=True)
        if run in NEEDS_IMAGES:
            imgs = s1 / "images"; imgs.mkdir()
            seeded = run.endswith("SEEDED")
            for name in CLEAN:
                if seeded and name in SEEDED_SUB:
                    src = repo / "docs/vrtv01/seeded" / SEEDED_SUB[name]
                    want = seed_h[SEEDED_SUB[name]]
                else:
                    src = repo / "docs/vrtv01/views" / name
                    want = clean_h[name]
                if sha256(src) != want:
                    die(f"hash mismatch for {src.name}; refusing to stage")
                (imgs / src.name).write_bytes(src.read_bytes())
            (s1 / "LEGEND.txt").write_text(LEGEND)

    subprocess.run(["rm", "-rf", str(corpus)], check=True)

    manifest = []
    for p in sorted(stage.rglob("*")):
        if p.is_file() and p.name != "STAGING_MANIFEST.json":
            if p.is_symlink(): die(f"symlink staged: {p}")
            manifest.append({"path": str(p.relative_to(stage)), "sha256": sha256(p)})
    out = stage / "STAGING_MANIFEST.json"
    out.write_text(json.dumps({"experiment": "VRTV-02",
                               "source_baseline": SOURCE_BASELINE,
                               "corpus": "bounded (docs/vrtv02/build_corpus.py)",
                               "files": manifest}, indent=2) + "\n")
    out.chmod(0o600)
    print(f"VRTV-02 staged under {stage}: {len(manifest)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
