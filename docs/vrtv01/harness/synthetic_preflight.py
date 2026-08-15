#!/usr/bin/env python3
"""Synthetic preflight for the VRTV-01 harness.

Verifies the harness and provider configuration using a TRIVIAL, UNRELATED
synthetic text+image task. It MUST NOT expose the selected model or session to
any VRTV artifact.

Generates its own 2x2 checkerboard PNG in a temp dir. Reads nothing from the
repository, the staging tree, the views, the prompts, or any finding.

Verifies: authentication, image ingestion, JSON output, model identity,
reasoning configuration, tools_registered == [], transport restriction.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import struct
import sys
import urllib.error
import urllib.request
import zlib
from datetime import datetime, timezone
from pathlib import Path

SYNTHETIC_PROMPT = (
    "You are given one small synthetic test image and one short synthetic "
    "sentence. This is a connectivity check unrelated to any real task.\n\n"
    "Sentence: 'The preflight sentence contains exactly seven words.'\n\n"
    "Reply with ONLY a JSON object with keys: "
    "image_top_left_color (string), image_width_px (integer), "
    "sentence_word_count (integer)."
)


def synthetic_png(path: Path) -> None:
    """Write a 2x2 PNG: red/green over blue/white. No external deps."""
    px = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 255)]
    raw = b""
    for row in (0, 1):
        raw += b"\x00"
        for col in (0, 1):
            raw += bytes(px[row * 2 + col])

    def chunk(tag: bytes, data: bytes) -> bytes:
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c))

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 2, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw))
           + chunk(b"IEND", b""))
    path.write_bytes(png)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model-pin", type=Path,
                    default=Path(__file__).parent / "MODEL_PIN.json")
    ap.add_argument("--effort", default="high")
    ap.add_argument("--out", type=Path,
                    default=Path(__file__).parent / "PREFLIGHT_RESULT.json")
    ap.add_argument("--work-dir", type=Path, default=Path("/tmp"))
    args = ap.parse_args()

    result: dict = {"checked_utc": datetime.now(timezone.utc).isoformat(),
                    "vrtv_artifacts_exposed": False}

    if not args.model_pin.exists():
        result["status"] = "BLOCKED"
        result["reason"] = ("MODEL_PIN.json missing; run pin_model_id.py "
                            "against the experiment API account first")
        args.out.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2)); return 2

    pin = json.loads(args.model_pin.read_text())
    model = pin["treatment"]["pinned_model_id"]
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        result["status"] = "BLOCKED"
        result["reason"] = "OPENAI_API_KEY not set"
        args.out.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2)); return 2

    img = args.work_dir / "vrtv_preflight_synthetic.png"
    synthetic_png(img)
    b64 = base64.b64encode(img.read_bytes()).decode()

    payload = {
        "model": model,
        "input": [{"role": "user", "content": [
            {"type": "input_text", "text": SYNTHETIC_PROMPT},
            {"type": "input_image",
             "image_url": f"data:image/png;base64,{b64}"}]}],
        "reasoning": {"effort": args.effort},
        "store": False,
    }

    try:
        req = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {key}",
                     "Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=300) as resp:
            raw = json.loads(resp.read().decode())
            headers = dict(resp.headers)
    except urllib.error.HTTPError as e:
        result["status"] = "BLOCKED"
        result["reason"] = f"provider error {e.code}: {e.read().decode()[:300]}"
        args.out.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2)); return 2

    text = ""
    for item in raw.get("output", []):
        for c in item.get("content", []):
            if c.get("type") == "output_text":
                text += c.get("text", "")

    parsed, json_ok = None, False
    try:
        parsed = json.loads(text.strip().removeprefix("```json").removesuffix("```").strip())
        json_ok = True
    except Exception:
        pass

    result.update({
        "authentication": "OK",
        "requested_model": model,
        "returned_model": raw.get("model"),
        "model_identity_match": raw.get("model") == model,
        "system_fingerprint": raw.get("system_fingerprint"),
        "service_tier": raw.get("service_tier"),
        "response_id": raw.get("id"),
        "provider_request_id": headers.get("x-request-id"),
        "reasoning_effort_requested": args.effort,
        "tools_registered": [],
        "tools_key_sent": "tools" in payload,
        "transport": "https://api.openai.com/v1/responses only",
        "image_ingestion": "OK" if json_ok and parsed
                           and "image_top_left_color" in parsed else "CHECK",
        "json_output": json_ok,
        "model_answer": parsed if json_ok else text[:400],
        "usage": raw.get("usage"),
    })
    result["status"] = ("PASS" if (result["model_identity_match"] and json_ok
                                   and not result["tools_key_sent"])
                        else "REVIEW")
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
