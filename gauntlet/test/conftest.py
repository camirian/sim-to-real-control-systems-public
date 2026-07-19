"""Shared fixtures: synthesized run logs from s2r_dsp (no ROS, no Isaac).

Variants (all deterministic — the synthesizer's internal RNG is seeded):

- ``clean``    — measured == the clean reference (no noisy column).
- ``noisy``    — measured == the raw noisy stream (an unfiltered run).
- ``filtered`` — measured == causal IIR (order 4, 10 Hz cutoff at 200 Hz)
  applied to the noisy stream, noisy column present.
"""

import csv
import json
from pathlib import Path

import numpy as np
import pytest
from s2r_dsp import apply_filter_realtime, design_iir_lowpass, generate_telemetry

FS = 200.0
DURATION_S = 5.0
FILTER_CUTOFF_HZ = 10.0
FILTER_ORDER = 4
SCENARIO = "franka-joint-tracking-synthetic"


def synth_streams():
    t, clean, noisy = generate_telemetry(duration=DURATION_S, fs=FS)
    b, a = design_iir_lowpass(FS, FILTER_CUTOFF_HZ, FILTER_ORDER)
    filtered = np.asarray(apply_filter_realtime(b, a, noisy))
    return t, clean, noisy, filtered


def write_run_log(
    log_dir: Path,
    variant: str,
    run_id: str = None,
    seed: int = 0,
    thresholds: dict = None,
) -> Path:
    """Write a run-log directory for one variant; returns the directory."""
    t, clean, noisy, filtered = synth_streams()
    if variant == "clean":
        measured, noisy_col = clean, None
    elif variant == "noisy":
        measured, noisy_col = noisy, noisy
    elif variant == "filtered":
        measured, noisy_col = filtered, noisy
    else:
        raise ValueError(f"unknown variant {variant!r}")

    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "run_id": run_id or f"{variant}-0001",
        "scenario": SCENARIO,
        "seed": seed,
    }
    if thresholds is not None:
        meta["thresholds"] = thresholds
    (log_dir / "run_meta.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    header = ["t", "reference", "measured"] + (["noisy"] if noisy_col is not None else [])
    with (log_dir / "telemetry.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        for i in range(len(t)):
            row = [repr(t[i]), repr(clean[i]), repr(float(measured[i]))]
            if noisy_col is not None:
                row.append(repr(float(noisy_col[i])))
            writer.writerow(row)
    return log_dir


@pytest.fixture()
def clean_log(tmp_path):
    return write_run_log(tmp_path / "clean", "clean")


@pytest.fixture()
def noisy_log(tmp_path):
    return write_run_log(tmp_path / "noisy", "noisy")


@pytest.fixture()
def filtered_log(tmp_path):
    return write_run_log(tmp_path / "filtered", "filtered")
