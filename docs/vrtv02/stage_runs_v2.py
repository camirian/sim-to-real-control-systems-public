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


def advance_stage2(repo: Path, stage: Path, run: str,
                   resp: Path | None) -> int:
    """Create stage-2 for one run, gated on that run's completed stage-1.

    Stage 2 must deterministically receive (a) that run's exact saved stage-1
    output and (b) the identical bounded corpus. Nothing here depends on
    operator memory or an undocumented chat session.
    """
    if resp is None:
        die("--advance-stage2 requires --stage1-response")
    if not resp.exists():
        die(f"stage-1 response not found: {resp}. Stage 1 must complete and be "
            "saved before stage 2 can be built.")
    try:
        payload = json.loads(resp.read_text())
    except Exception as e:
        die(f"stage-1 response is not readable JSON: {e}")

    output = payload.get("output")
    if not output:
        die("stage-1 response has an empty or missing 'output'; refusing to "
            "build stage 2 from nothing")
    text = "".join(c.get("text", "")
                   for item in output for c in (item.get("content") or [])
                   if c.get("type") == "output_text")
    if not text.strip():
        die("stage-1 response contains no assistant-visible output text")

    # Cross-run leakage guard: the saved response must belong to THIS run.
    meta = resp.parent / resp.name.replace("_raw_response.json", "_metadata.json")
    if meta.exists():
        m = json.loads(meta.read_text())
        if m.get("run") and m["run"] != run:
            die(f"stage-1 response belongs to run {m['run']!r}, not {run!r}; "
                "refusing to cross-contaminate conditions")
        if m.get("stage") and m["stage"] != "stage-1":
            die(f"response is from {m['stage']!r}, not stage-1")

    run_root = stage / run
    if not (run_root / "stage-1").is_dir():
        die(f"{run}/stage-1 does not exist; stage 1 was never staged")
    s2 = run_root / "stage-2"
    if s2.exists() and any(s2.iterdir()):
        die("stage-2 already exists and is non-empty; refusing to overwrite")
    s2.mkdir(parents=True, exist_ok=True)

    # identical bounded corpus, rebuilt from the same enumeration
    corpus = s2 / ".build"
    subprocess.run([sys.executable, str(repo / "docs/vrtv02/build_corpus.py"),
                    "--repo", str(repo), "--emit-dir", str(corpus),
                    "--out", str(s2 / ".corpus_manifest.json")],
                   check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["mv", str(corpus), str(s2 / "source")], check=True)
    (s2 / ".corpus_manifest.json").unlink()

    cont = s2 / "STAGE1_CONTINUATION.json"
    cont.write_text(json.dumps({
        "run": run,
        "stage1_response_path": str(resp),
        "stage1_response_sha256": sha256(resp),
        "stage1_output_text_sha256":
            hashlib.sha256(text.encode()).hexdigest(),
        "stage1_output_items": len(output),
        "stage1_output_text_chars": len(text),
        "replay_contract": "run_condition.py replays the stage-1 user message "
                           "and the complete stage-1 output array verbatim, "
                           "then appends the stage-2 prompt",
    }, indent=2) + "\n")
    cont.chmod(0o600)

    n = sum(1 for p in (s2 / "source").rglob("*") if p.is_file())
    print(f"{run} stage-2 staged: {n} corpus files, stage-1 output "
          f"{len(text)} chars, sha256 {sha256(resp)[:16]}...")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", type=Path, required=True)
    ap.add_argument("--stage-root", type=Path, required=True)
    ap.add_argument("--advance-stage2", choices=RUNS,
                    help="create stage-2 for a run whose stage-1 is complete")
    ap.add_argument("--stage1-response", type=Path,
                    help="saved raw stage-1 provider response for --advance-stage2")
    args = ap.parse_args()

    if args.advance_stage2:
        return advance_stage2(args.repo.resolve(), args.stage_root.resolve(),
                              args.advance_stage2, args.stage1_response)

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
