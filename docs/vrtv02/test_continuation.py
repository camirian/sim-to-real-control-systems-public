#!/usr/bin/env python3
"""Fail-closed tests for the VRTV-02 two-stage continuation.

Makes NO API call. Uses synthetic stage-1 responses shaped like the provider's,
never any real reviewer output.

Proves: stage 2 cannot be built or run without that run's genuine, non-empty,
hash-matching stage-1 output; cross-run output is rejected; the bounded corpus
is byte-identical across every condition that receives source; and V1 stage-1
holds no source.
"""
from __future__ import annotations

import hashlib, json, shutil, subprocess, sys, tempfile
from pathlib import Path

RUNS = ("V0-CLEAN", "V1-CLEAN", "V1-SEEDED", "V2-CLEAN", "V2-SEEDED")
HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
STAGER = HERE / "stage_runs_v2.py"
RUNNER = REPO / "docs/vrtv01/harness/run_condition.py"
ok = fail = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global ok, fail
    if cond:
        ok += 1; print(f"  PASS  {name}")
    else:
        fail += 1; print(f"  FAIL  {name} {detail}")


def synth_response(run: str, text: str = None) -> dict:
    body = text if text is not None else json.dumps(
        [{"local_id": "f1", "claim": "synthetic test claim",
          "rationale": "synthetic", "severity_if_true": "NOTE",
          "requested_source_check": "RESULTS.md", "reviewer_confidence": "LOW"}])
    return {"id": f"resp_synthetic_{run}", "model": "gpt-5.6-sol",
            "output": [{"type": "message", "role": "assistant",
                        "content": [{"type": "output_text", "text": body}]}]}


def write_stage1(out: Path, run: str, resp: dict) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    rp = out / f"{run}_stage-1_raw_response.json"
    rp.write_text(json.dumps(resp, indent=2))
    (out / f"{run}_stage-1_metadata.json").write_text(
        json.dumps({"run": run, "stage": "stage-1"}))
    (out / f"{run}_stage-1_request.json").write_text(
        json.dumps({"input": [{"role": "user",
                               "content": [{"type": "input_text",
                                            "text": "STAGE1 PROMPT"}]}]}))
    return rp


def stage(root: Path) -> None:
    subprocess.run([sys.executable, str(STAGER), "--repo", str(REPO),
                    "--stage-root", str(root)], check=True,
                   stdout=subprocess.DEVNULL)


def advance(root: Path, run: str, resp: Path):
    return subprocess.run(
        [sys.executable, str(STAGER), "--repo", str(REPO), "--stage-root",
         str(root), "--advance-stage2", run, "--stage1-response", str(resp)],
        capture_output=True, text=True)


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="vrtv02-test-"))
    try:
        root = tmp / "stage"; out = tmp / "out"
        stage(root)

        print("\n[1] V1 stage-1 holds visuals only, no source")
        for r in ("V1-CLEAN", "V1-SEEDED"):
            src = list((root / r / "stage-1").rglob("source"))
            imgs = list((root / r / "stage-1/images").glob("*.png"))
            check(f"{r}: 0 source, 4 images", not src and len(imgs) == 4)

        print("\n[2] stage-2 blocked before stage-1 exists")
        for r in RUNS:
            check(f"{r}: absent stage-1 output blocks stage 2",
                  advance(root, r, tmp / "nope.json").returncode != 0)
            check(f"{r}: stage-2 dir not created", not (root / r / "stage-2").exists())

        print("\n[3] empty / no-text stage-1 output blocks stage 2")
        empty = write_stage1(out, "V0-CLEAN", {"id": "x", "output": []})
        check("empty output array blocked", advance(root, "V0-CLEAN", empty).returncode != 0)
        blank = write_stage1(out, "V0-CLEAN", synth_response("V0-CLEAN", text="   "))
        check("whitespace-only output blocked", advance(root, "V0-CLEAN", blank).returncode != 0)

        print("\n[4] wrong-run stage-1 output is rejected")
        wrong = write_stage1(out / "wrong", "V1-CLEAN", synth_response("V1-CLEAN"))
        r = advance(root, "V0-CLEAN", wrong)
        check("cross-condition output blocked", r.returncode != 0,
              "(expected refusal)")

        print("\n[5] stage-2 builds for ALL five runs with genuine stage-1")
        resp_paths = {}
        for run in RUNS:
            rp = write_stage1(out / run, run, synth_response(run))
            resp_paths[run] = rp
            res = advance(root, run, rp)
            check(f"{run}: stage-2 built", res.returncode == 0, res.stderr[:90])

        print("\n[6] stage-1 output hash recorded and matches")
        for run in RUNS:
            c = json.loads((root / run / "stage-2/STAGE1_CONTINUATION.json").read_text())
            disk = hashlib.sha256(resp_paths[run].read_bytes()).hexdigest()
            check(f"{run}: response sha256 recorded+correct",
                  c["stage1_response_sha256"] == disk and c["run"] == run)

        print("\n[7] stage-2 corpora byte-identical across all conditions")
        base = None
        for run in RUNS:
            files = sorted((root / run / "stage-2/source").rglob("*"))
            h = hashlib.sha256()
            for f in files:
                if f.is_file():
                    h.update(str(f.relative_to(root / run / "stage-2/source")).encode())
                    h.update(f.read_bytes())
            d = h.hexdigest()
            if base is None:
                base = d
            check(f"{run}: corpus digest matches V0-CLEAN", d == base)

        print("\n[8] runner rejects stage-2 with tampered stage-1 hash")
        c = root / "V0-CLEAN/stage-2/STAGE1_CONTINUATION.json"
        good = c.read_text(); bad = json.loads(good)
        bad["stage1_response_sha256"] = "0" * 64
        c.write_text(json.dumps(bad))
        env = {"OPENAI_API_KEY": "dummy", "PATH": "/usr/bin:/bin"}
        pin = tmp / "pin.json"; pin.write_text('{"treatment":{"pinned_model_id":"m"}}')
        pr = tmp / "p.txt"; pr.write_text("x")
        res = subprocess.run(
            [sys.executable, str(RUNNER), "--stage-root", str(root),
             "--run", "V0-CLEAN", "--stage", "stage-2", "--prompt-file", str(pr),
             "--out-dir", str(tmp / "o2"), "--model-pin", str(pin)],
            capture_output=True, text=True, env=env)
        check("tampered stage-1 hash blocks the run", res.returncode != 0
              and "hash mismatch" in res.stderr)
        c.write_text(good)

        print("\n[9] runner rejects stage-2 with continuation file removed")
        c.unlink()
        res = subprocess.run(
            [sys.executable, str(RUNNER), "--stage-root", str(root),
             "--run", "V0-CLEAN", "--stage", "stage-2", "--prompt-file", str(pr),
             "--out-dir", str(tmp / "o3"), "--model-pin", str(pin)],
            capture_output=True, text=True, env=env)
        check("missing continuation blocks the run", res.returncode != 0
              and "STAGE1_CONTINUATION" in res.stderr)

        print(f"\n{ok} passed, {fail} failed")
        return 1 if fail else 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
