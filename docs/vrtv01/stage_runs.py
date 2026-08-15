#!/usr/bin/env python3
"""Build isolated VRTV-01 input directories.

This script stages inputs only. It never launches a reviewer and never copies
the preregistration, execution packages, Mermaid sources, answer key, or other
operator material into a reviewer directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tarfile
from pathlib import Path


SOURCE_BASELINE = "f03c748ae0b0e6b30de572e9cb7ef49b2c88fe29"
RUNS = ("V0-CLEAN", "V1-CLEAN", "V1-SEEDED", "V2-CLEAN", "V2-SEEDED")
CLEAN_VIEWS = (
    "view_a_system_topology.png",
    "view_b_evidence_provenance.png",
    "view_c_controls_and_history.png",
    "view_d_claim_boundary.png",
)
SEEDED_VIEWS = (
    "view_a_system_topology_seeded.png",
    "view_b_evidence_provenance_seeded.png",
    "view_c_controls_and_history.png",
    "view_d_claim_boundary.png",
)
SOURCE_FILES = (
    "README.md",
    "RESULTS.md",
    "MASTER_PLAN.md",
    "docs/M4_RUNTIME_VALIDATION.md",
    "docs/REPRODUCE_CAMPAIGN.md",
    "campaign/manifests/m4-franka-filtered-vs-unfiltered-v1.json",
)
SOURCE_DIRS = ("campaign/results/m4-franka-filtered-vs-unfiltered-v1/",)


def die(message: str) -> "NoReturn":
    raise SystemExit(f"stage_runs.py: ERROR: {message}")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def reject_symlink_tree(root: Path) -> None:
    for path in root.rglob("*"):
        if path.is_symlink():
            die(f"symlink is forbidden in staging tree: {path}")


def ensure_empty_dir(path: Path) -> None:
    if path.exists():
        reject_symlink_tree(path)
        if any(path.iterdir()):
            die(f"refusing to overwrite non-empty staging directory: {path}")
    else:
        path.mkdir(parents=True)
    path.chmod(0o700)


def repo_root(repo: Path) -> Path:
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--show-toplevel"],
        check=True,
        capture_output=True,
        text=True,
    )
    return Path(result.stdout.strip()).resolve()


def archive_source(repo: Path, destination: Path) -> None:
    command = ["git", "-C", str(repo), "archive", "--format=tar", SOURCE_BASELINE]
    process = subprocess.Popen(command, stdout=subprocess.PIPE)
    assert process.stdout is not None
    with tarfile.open(fileobj=process.stdout, mode="r|") as archive:
        for member in archive:
            name = member.name
            allowed = name in SOURCE_FILES or any(name.startswith(prefix) for prefix in SOURCE_DIRS)
            if not allowed:
                continue
            if member.isdir():
                continue
            if not member.isfile():
                die(f"non-regular frozen source member: {name}")
            target = destination / "source" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(member) as source, target.open("wb") as output:
                assert source is not None
                shutil.copyfileobj(source, output)
            target.chmod(0o600)
    if process.wait() != 0:
        die("git archive failed")


def copy_verified_view(repo: Path, destination: Path, relative: str, seeded: bool) -> None:
    prefix = "seeded/" if seeded else "views/"
    manifest = repo / "docs/vrtv01" / ("SEEDED_HASHES.txt" if seeded else "VIEW_HASHES.txt")
    source = repo / "docs/vrtv01" / prefix / relative
    if not source.is_file() or source.is_symlink():
        die(f"missing or symlinked view: {source}")
    expected_name = prefix + relative
    expected = next(
        (line.split()[0] for line in manifest.read_text().splitlines() if line.split()[1] == expected_name),
        None,
    )
    if expected is None or sha256(source) != expected:
        die(f"hash mismatch for {relative}; verify the committed manifest first")
    target = destination / "images" / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    target.chmod(0o600)


def write_text(destination: Path, name: str, content: str) -> None:
    path = destination / name
    path.write_text(content)
    path.chmod(0o600)


def stage_reviewer_input(repo: Path, run_root: Path, run: str) -> None:
    stage1 = run_root / "stage-1"
    ensure_empty_dir(stage1)

    if run == "V0-CLEAN":
        archive_source(repo, stage1)
    elif run.startswith("V1"):
        seeded = run == "V1-SEEDED"
        views = SEEDED_VIEWS if seeded else CLEAN_VIEWS
        for view in views:
            copy_verified_view(repo, stage1, view, seeded and "seeded" in view)
        write_text(stage1, "LEGEND.txt", "These four images are non-authoritative projections of a completed simulation campaign. They were hand-authored from prose documentation, not mechanically derived. They may omit information and they may contain errors. They are not the system and they are not evidence.\n")
    elif run.startswith("V2"):
        seeded = run == "V2-SEEDED"
        archive_source(repo, stage1)
        views = SEEDED_VIEWS if seeded else CLEAN_VIEWS
        for view in views:
            copy_verified_view(repo, stage1, view, seeded and "seeded" in view)
        write_text(stage1, "LEGEND.txt", "These four images are non-authoritative projections of a completed simulation campaign. They were hand-authored from prose documentation, not mechanically derived. They may omit information and they may contain errors. They are not the system and they are not evidence.\n")
    else:
        die(f"unknown run {run}")

    reject_symlink_tree(run_root)


def assert_recorded_stage1(path: Path, stage_root: Path) -> None:
    if not path.is_file() or path.is_symlink() or path.stat().st_size == 0:
        die("V1 stage-1 output must be a closed, non-empty regular file")
    if stage_root in path.resolve().parents:
        die("stage-1 output must be stored outside the reviewer input directory")


def advance_v1(repo: Path, stage_root: Path, run: str, stage1_output: Path) -> None:
    run_root = stage_root / run
    stage1 = run_root / "stage-1"
    if not stage1.is_dir():
        die(f"missing stage-1 directory: {stage1}")
    assert_recorded_stage1(stage1_output.resolve(), stage_root)
    stage2 = run_root / "stage-2"
    ensure_empty_dir(stage2)
    archive_source(repo, stage2)
    reject_symlink_tree(run_root)


def stage_v3(repo: Path, stage_root: Path, normalized: Path) -> None:
    if not normalized.is_file() or normalized.is_symlink():
        die("normalized findings must be a regular file, not a symlink")
    try:
        payload = json.loads(normalized.read_text())
    except json.JSONDecodeError as error:
        die(f"normalized findings are not valid JSON: {error}")
    if isinstance(payload, dict) and {"rationale", "reviewer_confidence", "derived_from", "self_verdict"}.intersection(payload):
        die("normalized findings retain a forbidden reviewer field")
    text = json.dumps(payload).lower()
    if any(token in text for token in ("v0", "v1", "v2", "v3", "seeded", "view_a", "view_b", "view_c", "view_d")):
        die("normalized findings leak condition, seeding, or view identity")
    stage = stage_root / "V3" / "inputs"
    ensure_empty_dir(stage)
    copied = stage / "normalized_findings.json"
    shutil.copyfile(normalized, copied)
    copied.chmod(0o600)
    archive_source(repo, stage)
    reject_symlink_tree(stage.parent)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--stage-root", type=Path, required=True)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--run", choices=RUNS, action="append")
    modes.add_argument("--advance-v1", choices=("V1-CLEAN", "V1-SEEDED"))
    modes.add_argument("--stage-v3", action="store_true")
    parser.add_argument("--stage1-output", type=Path)
    parser.add_argument("--normalized-findings", type=Path)
    args = parser.parse_args()
    repo = repo_root(args.repo)
    stage_root = args.stage_root.resolve()
    if stage_root == repo or repo in stage_root.parents:
        die("stage root must be outside the git repository")
    stage_root.mkdir(parents=True, exist_ok=True)
    stage_root.chmod(0o700)
    if args.run:
        if any(stage_root.iterdir()):
            die("initial staging requires an empty stage root")
        for run in args.run:
            stage_reviewer_input(repo, stage_root / run, run)
    elif args.advance_v1:
        unexpected = [p.name for p in stage_root.iterdir() if p.name not in (*RUNS, "STAGING_MANIFEST.json")]
        if unexpected:
            die(f"unexpected stage-root entries: {unexpected}")
        if args.stage1_output is None:
            die("--advance-v1 requires --stage1-output")
        advance_v1(repo, stage_root, args.advance_v1, args.stage1_output)
    else:
        unexpected = [p.name for p in stage_root.iterdir() if p.name not in (*RUNS, "STAGING_MANIFEST.json")]
        if unexpected:
            die(f"unexpected stage-root entries: {unexpected}")
        if args.normalized_findings is None:
            die("--stage-v3 requires --normalized-findings")
        stage_v3(repo, stage_root, args.normalized_findings)
    manifest = []
    for path in sorted(stage_root.rglob("*")):
        if path.is_file():
            manifest.append({"path": str(path.relative_to(stage_root)), "sha256": sha256(path)})
    (stage_root / "STAGING_MANIFEST.json").write_text(json.dumps({"source_baseline": SOURCE_BASELINE, "files": manifest}, indent=2) + "\n")
    (stage_root / "STAGING_MANIFEST.json").chmod(0o600)
    print(f"staging operation completed under {stage_root}")
    return 0


if __name__ == "__main__":
    main()
