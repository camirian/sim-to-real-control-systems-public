#!/usr/bin/env python3
"""Minimal VRTV-01 API execution harness.

Submits one staged reviewer condition to the pinned model over a plain provider
API client with ZERO tools registered, and records raw responses plus full
identity metadata.

Deliberately minimal. It does not orchestrate, retry, parse findings, or reason.
Anything it cannot verify, it refuses.

Guarantees:
  - consumes only an already-frozen staging directory;
  - registers no tools (`tools` is never sent);
  - fails closed on extra inputs or unexpected configuration;
  - never touches the repository -- refuses any staging root containing .git;
  - saves the raw provider response verbatim before any interpretation;
  - saves request/model/config metadata and the exact input manifest+hashes.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

RUNS = ("V0-CLEAN", "V1-CLEAN", "V1-SEEDED", "V2-CLEAN", "V2-SEEDED")
STAGES = ("stage-1", "stage-2")
TEXT_EXT = {".md", ".txt", ".json", ".yaml", ".yml"}
IMAGE_EXT = {".png"}
# Anything outside these is an unexpected input and fails the run closed.
ALLOWED_EXT = TEXT_EXT | IMAGE_EXT
# Artifacts that must never reach a reviewer.
FORBIDDEN_SUBSTRINGS = (
    "ANSWER_KEY", "VISUAL_ROUND_TRIP_EXPERIMENT", "EXECUTION_CONTROL",
    ".mmd", "packages/", "SEEDED_ANSWER",
)


def die(msg: str) -> "NoReturn":
    print(f"FAIL-CLOSED: {msg}", file=sys.stderr)
    raise SystemExit(2)


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def collect_inputs(stage_dir: Path) -> list[Path]:
    if not stage_dir.is_dir():
        die(f"stage directory missing: {stage_dir}")
    files = sorted(p for p in stage_dir.rglob("*") if p.is_file())
    if not files:
        die(f"stage directory empty: {stage_dir}")
    for p in files:
        if p.is_symlink():
            die(f"symlink in staged inputs: {p}")
        rel = str(p.relative_to(stage_dir))
        if p.suffix.lower() not in ALLOWED_EXT:
            die(f"unexpected input extension: {rel}")
        for bad in FORBIDDEN_SUBSTRINGS:
            if bad.lower() in rel.lower():
                die(f"forbidden artifact staged for a reviewer: {rel}")
    return files


def assert_no_repo(stage_root: Path) -> None:
    probe = stage_root.resolve()
    for parent in [probe, *probe.parents]:
        if (parent / ".git").exists():
            die(f"repository visible from staging root at {parent}; "
                "reviewers must never be launched from the repository")


def build_openai_payload(model: str, effort: str, prompt: str,
                         files: list[Path], stage_dir: Path) -> dict:
    content: list[dict] = [{"type": "input_text", "text": prompt}]
    for p in files:
        rel = p.relative_to(stage_dir)
        if p.suffix.lower() in IMAGE_EXT:
            b64 = base64.b64encode(p.read_bytes()).decode()
            content.append({"type": "input_image",
                            "image_url": f"data:image/png;base64,{b64}"})
        else:
            content.append({"type": "input_text",
                            "text": f"--- FILE: {rel} ---\n{p.read_text()}"})
    return {
        "model": model,
        "input": [{"role": "user", "content": content}],
        "reasoning": {"effort": effort},
        # tools deliberately omitted -- registering zero tools is a hard
        # requirement, and an empty list still advertises tool capability.
        "store": False,
    }


def post(url: str, payload: dict, headers: dict[str, str]) -> tuple[dict, dict]:
    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=1800) as resp:
        return json.loads(resp.read().decode()), dict(resp.headers)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stage-root", type=Path, required=True)
    ap.add_argument("--run", required=True, choices=RUNS)
    ap.add_argument("--stage", required=True, choices=STAGES)
    ap.add_argument("--prompt-file", type=Path, required=True,
                    help="verbatim prompt text; operator supplies from package")
    ap.add_argument("--out-dir", type=Path, required=True,
                    help="output location OUTSIDE the staging tree")
    ap.add_argument("--model-pin", type=Path,
                    default=Path(__file__).parent / "MODEL_PIN.json")
    ap.add_argument("--effort", default="high")
    args = ap.parse_args()

    if not args.model_pin.exists():
        die("MODEL_PIN.json missing. Run pin_model_id.py first; the model ID "
            "must come from the provider, not from memory.")
    pin = json.loads(args.model_pin.read_text())
    model = pin["treatment"]["pinned_model_id"]
    if not model:
        die("pinned_model_id is empty")

    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        die("OPENAI_API_KEY not set")

    assert_no_repo(args.stage_root)
    stage_dir = args.stage_root / args.run / args.stage
    files = collect_inputs(stage_dir)

    if args.out_dir.resolve().is_relative_to(args.stage_root.resolve()):
        die("output directory must be outside the staging tree")
    args.out_dir.mkdir(parents=True, exist_ok=True)

    manifest = [{"path": str(p.relative_to(stage_dir)), "sha256": sha256(p)}
                for p in files]
    prompt = args.prompt_file.read_text()
    payload = build_openai_payload(model, args.effort, prompt, files, stage_dir)

    # G7 -- blinding guard. Seeded artifacts are distinguishable by FILENAME
    # ("..._seeded.png"). Image filenames are not transmitted today, but that is
    # an implementation detail of build_openai_payload; a future edit adding
    # filename labels would silently unblind every seeded run and the experiment
    # would look fine while measuring nothing. Assert it at the payload level.
    scrubbed = re.sub(r"data:image/png;base64,[A-Za-z0-9+/=]+", "<IMG>",
                      json.dumps(payload))
    if "seeded" in scrubbed.lower():
        die("payload leaks the string 'seeded'; this would unblind the run")
    for f in files:
        if f.suffix.lower() in IMAGE_EXT and f.name in scrubbed:
            die(f"payload leaks image filename {f.name}; images must be sent "
                "without identifying metadata")
    if "tools" in payload:
        die("tools key present in payload; zero tools must mean the key is omitted")

    started = datetime.now(timezone.utc).isoformat()
    try:
        raw, resp_headers = post(
            "https://api.openai.com/v1/responses", payload,
            {"Authorization": f"Bearer {key}",
             "Content-Type": "application/json"})
    except urllib.error.HTTPError as e:
        die(f"provider error {e.code}: {e.read().decode()[:400]}")
    ended = datetime.now(timezone.utc).isoformat()

    stem = f"{args.run}_{args.stage}"
    (args.out_dir / f"{stem}_raw_response.json").write_text(
        json.dumps(raw, indent=2) + "\n")

    meta = {
        "run": args.run,
        "stage": args.stage,
        "started_utc": started,
        "ended_utc": ended,
        "requested_model": model,
        "returned_model": raw.get("model"),
        "response_id": raw.get("id"),
        "system_fingerprint": raw.get("system_fingerprint"),
        "service_tier": raw.get("service_tier"),
        "provider_request_id": resp_headers.get("x-request-id"),
        "openai_processing_ms": resp_headers.get("openai-processing-ms"),
        "reasoning_effort": args.effort,
        "tools_registered": [],
        "usage": raw.get("usage"),
        "input_manifest": manifest,
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "stage_dir": str(stage_dir),
    }
    (args.out_dir / f"{stem}_metadata.json").write_text(
        json.dumps(meta, indent=2) + "\n")

    if meta["returned_model"] != model:
        print(f"WARNING: returned model {meta['returned_model']!r} != requested "
              f"{model!r}. Per EXECUTION_CONTROL section 4, VOID this run "
              "rather than accepting model drift.", file=sys.stderr)

    print(json.dumps({k: meta[k] for k in (
        "run", "stage", "requested_model", "returned_model", "response_id",
        "system_fingerprint", "provider_request_id")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
