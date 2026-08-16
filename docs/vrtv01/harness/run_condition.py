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
# Operator-only control files that live inside a stage dir but are NOT
# reviewer inputs. STAGE1_CONTINUATION.json records stage-1 response paths and
# hashes; feeding it to the model would leak run bookkeeping into the context.
OPERATOR_ONLY = {"STAGE1_CONTINUATION.json"}
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
    files = sorted(p for p in stage_dir.rglob("*")
                   if p.is_file() and p.name not in OPERATOR_ONLY)
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
                         files: list[Path], stage_dir: Path,
                         history: list | None = None) -> dict:
    """Build a Responses API request.

    `history`, when given, is the verbatim replay of the prior turn:
    [stage-1 user message, *stage-1 response output items]. With store=false
    the provider holds no state, so faithful two-stage continuation requires
    replaying the COMPLETE output array -- not just the text -- so reasoning
    items and assistant phase values survive into stage 2.
    """
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
    turns: list = list(history or [])
    turns.append({"role": "user", "content": content})
    return {
        "model": model,
        "input": turns,
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

    # ---- stage-2 continuation, fail-closed -------------------------------
    history = None
    stage1_meta = None
    if args.stage == "stage-2":
        cont_path = stage_dir / "STAGE1_CONTINUATION.json"
        if not cont_path.exists():
            die("stage-2 requires STAGE1_CONTINUATION.json; build it with "
                "stage_runs_v2.py --advance-stage2 after stage 1 completes")
        cont = json.loads(cont_path.read_text())
        if cont.get("run") != args.run:
            die(f"continuation belongs to run {cont.get('run')!r}, not "
                f"{args.run!r}; refusing cross-condition contamination")
        resp_path = Path(cont["stage1_response_path"])
        if not resp_path.exists():
            die(f"saved stage-1 response missing: {resp_path}")
        if sha256(resp_path) != cont["stage1_response_sha256"]:
            die("stage-1 response hash mismatch; it changed after staging")
        raw1 = json.loads(resp_path.read_text())
        out1 = raw1.get("output") or []
        if not out1:
            die("saved stage-1 response has empty output; nothing to continue")
        text1 = "".join(c.get("text", "")
                        for it in out1 for c in (it.get("content") or [])
                        if c.get("type") == "output_text")
        if not text1.strip():
            die("saved stage-1 response has no assistant-visible text")
        if hashlib.sha256(text1.encode()).hexdigest() != \
                cont["stage1_output_text_sha256"]:
            die("stage-1 output text hash mismatch")
        s1req = resp_path.parent / resp_path.name.replace(
            "_raw_response.json", "_request.json")
        if not s1req.exists():
            die(f"stage-1 request record missing: {s1req}; the stage-1 user "
                "turn must be replayed verbatim and cannot be reconstructed")
        prior_user = json.loads(s1req.read_text())["input"]
        history = [*prior_user, *out1]
        stage1_meta = {
            "stage1_response_sha256": cont["stage1_response_sha256"],
            "stage1_output_text_sha256": cont["stage1_output_text_sha256"],
            "stage1_output_items": len(out1),
            "stage1_output_text_chars": len(text1),
            "replayed_history_items": len(history),
        }

    if args.out_dir.resolve().is_relative_to(args.stage_root.resolve()):
        die("output directory must be outside the staging tree")
    args.out_dir.mkdir(parents=True, exist_ok=True)

    manifest = [{"path": str(p.relative_to(stage_dir)), "sha256": sha256(p)}
                for p in files]
    prompt = args.prompt_file.read_text()
    payload = build_openai_payload(model, args.effort, prompt, files,
                                   stage_dir, history=history)

    # G7 -- blinding guard, scoped to HARNESS-ADDED METADATA ONLY.
    #
    # Seeded artifacts are distinguishable by FILENAME ("..._seeded.png"), so
    # the risk is that the harness labels an input and thereby reveals the
    # packet assignment. Image filenames are not transmitted today, but that is
    # an implementation detail; a future edit adding labels would silently
    # unblind every seeded run.
    #
    # This must NOT scan file *contents*. The authoritative corpus legitimately
    # contains the word "seeded" ("Seeded disturbance 25 Hz + AWGN") and names
    # telemetry.csv in its documentation. Scanning bodies produced false
    # positives that would have blocked V0-CLEAN -- a condition that receives no
    # images at all -- and V2-*. Guarding content is G2/G3's job, at staging.
    scrubbed = re.sub(r"data:image/png;base64,[A-Za-z0-9+/=]+", "<IMG>",
                      json.dumps(payload))
    for f in files:
        if f.suffix.lower() in IMAGE_EXT and f.name in scrubbed:
            die(f"payload leaks image filename {f.name}; images must be sent "
                "without identifying metadata")
    # Inspect the payload STRUCTURE, not the serialized blob: json.dumps turns
    # real newlines into literal \n two-char sequences, so a line-oriented
    # regex over the dump spans the whole document and matches everything.
    for item in payload["input"][0]["content"]:
        if item.get("type") != "input_text":
            continue
        first_line = item.get("text", "").split("\n", 1)[0]
        if first_line.startswith("--- FILE:") and "seeded" in first_line.lower():
            die(f"harness label leaks packet assignment: {first_line!r}")

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
    # The exact request is preserved so a later stage can replay this turn
    # verbatim rather than reconstruct it.
    (args.out_dir / f"{stem}_request.json").write_text(
        json.dumps(payload, indent=2) + "\n")

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
        "stage1_continuation": stage1_meta,
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
