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
    "You are given one synthetic test image and one short synthetic sentence. "
    "This is a connectivity and capability check unrelated to any real task.\n\n"
    "Sentence: 'The preflight sentence contains exactly seven words.'\n\n"
    "Reply with ONLY a JSON object with keys: "
    "printed_word (string, the large word printed in the image), "
    "printed_number (integer, the large number printed in the image), "
    "top_left_block_color (string, one of: red, green, blue), "
    "sentence_word_count (integer)."
)

# Ground truth for the generated image. The preflight FAILS if the model does
# not reproduce these -- an image the model cannot read is not "ingested".
TRUTH = {"printed_word": "PREFLIGHT", "printed_number": 47,
         "top_left_block_color": "red", "sentence_word_count": 7}

def synthetic_png(path: Path) -> None:
    """Write a synthetic test image that is REPRESENTATIVE of the real stimulus.

    The real views are wide (~3168x560) diagrams whose information is carried by
    printed text. A 2x2 pixel swatch does not test that capability at all: it
    gets resampled and the model cannot read it, which produces a false PASS.

    This draws a wide canvas with a large printed word, a large printed number,
    and three labelled colour blocks. Entirely synthetic -- no VRTV content.
    """
    from PIL import Image, ImageDraw, ImageFont

    W, H = 1600, 600
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)

    # Three colour blocks; the leftmost/top-left one is red.
    for i, colour in enumerate(("red", "green", "blue")):
        x0 = 40 + i * 180
        d.rectangle([x0, 40, x0 + 150, 190], fill=colour, outline="black", width=3)

    def font(size: int):
        for candidate in (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/TTF/DejaVuSans.ttf",
        ):
            if Path(candidate).exists():
                return ImageFont.truetype(candidate, size)
        return ImageFont.load_default()

    d.text((60, 260), "PREFLIGHT", fill="black", font=font(140))
    d.text((60, 430), "47", fill="black", font=font(120))
    d.rectangle([5, 5, W - 5, H - 5], outline="black", width=4)
    img.save(path, "PNG")


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

    checks = {}
    if json_ok and isinstance(parsed, dict):
        for k, want in TRUTH.items():
            got = parsed.get(k)
            if isinstance(want, str):
                ok = isinstance(got, str) and want.lower() in got.lower()
            else:
                ok = got == want
            checks[k] = {"expected": want, "got": got, "pass": ok}
    image_checks = [k for k in ("printed_word", "printed_number",
                                "top_left_block_color")]
    image_ok = all(checks.get(k, {}).get("pass") for k in image_checks)

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
        "reasoning_tokens_observed":
            (raw.get("usage") or {}).get("output_tokens_details", {})
            .get("reasoning_tokens"),
        "tools_registered": [],
        "tools_key_sent": "tools" in payload,
        "transport": "https://api.openai.com/v1/responses only",
        "synthetic_image_size_px": "1600x600",
        "ground_truth_checks": checks,
        "image_ingestion": "OK" if image_ok else "FAILED",
        "json_output": json_ok,
        "model_answer": parsed if json_ok else text[:400],
        "usage": raw.get("usage"),
    })
    result["status"] = ("PASS" if (result["model_identity_match"] and json_ok
                                   and image_ok
                                   and not result["tools_key_sent"])
                        else "FAIL")
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
