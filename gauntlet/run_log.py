"""Run-log loading: one logged closed-loop run = one directory (REQ-S2R-100).

Expected layout (written by the campaign runner / rosbag CSV export):

    <log_dir>/
        run_meta.json    {"run_id": str, "scenario": str, "seed": int,
                          optional "thresholds": {name: value}}
        telemetry.csv    header: t,reference,measured[,noisy]
                         t          — sample time (s, strictly increasing)
                         reference  — commanded/reference joint position (rad)
                         measured   — the stream under test (post-filter for
                                      filtered runs, raw for unfiltered runs)
                         noisy      — optional pre-filter stream (enables the
                                      attenuation check)

Every defect (missing files, bad header, non-numeric cells, empty data)
raises GauntletError — corrupt logs can never grade as PASS.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

import numpy as np

from gauntlet.errors import GauntletError

META_FILENAME = "run_meta.json"
TELEMETRY_FILENAME = "telemetry.csv"
_REQUIRED_COLUMNS = ("t", "reference", "measured")


@dataclass
class RunLog:
    run_id: str
    scenario: str
    seed: int
    t: np.ndarray
    reference: np.ndarray
    measured: np.ndarray
    noisy: Optional[np.ndarray]
    thresholds: Optional[Dict[str, float]]


def _load_meta(log_dir: Path) -> dict:
    meta_path = log_dir / META_FILENAME
    if not meta_path.is_file():
        raise GauntletError(f"missing {META_FILENAME} in {log_dir}")
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise GauntletError(f"corrupt {meta_path}: {e}") from e
    if not isinstance(meta, dict):
        raise GauntletError(f"{meta_path} must contain a JSON object")
    missing = [k for k in ("run_id", "scenario", "seed") if k not in meta]
    if missing:
        raise GauntletError(f"{meta_path} missing fields: {missing}")
    if not isinstance(meta["seed"], int) or isinstance(meta["seed"], bool):
        raise GauntletError(f"{meta_path}: seed must be an integer")
    return meta


def _load_telemetry(log_dir: Path):
    csv_path = log_dir / TELEMETRY_FILENAME
    if not csv_path.is_file():
        raise GauntletError(f"missing {TELEMETRY_FILENAME} in {log_dir}")
    with csv_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        try:
            header = next(reader)
        except StopIteration:
            raise GauntletError(f"{csv_path} is empty") from None
        header = [h.strip() for h in header]
        missing = [c for c in _REQUIRED_COLUMNS if c not in header]
        if missing:
            raise GauntletError(f"{csv_path} missing columns: {missing}")
        idx = {name: header.index(name) for name in header}
        columns: Dict[str, list] = {name: [] for name in header}
        for lineno, row in enumerate(reader, start=2):
            if len(row) != len(header):
                raise GauntletError(
                    f"{csv_path}:{lineno}: expected {len(header)} cells, got {len(row)}"
                )
            for name in header:
                cell = row[idx[name]].strip()
                try:
                    columns[name].append(float(cell))
                except ValueError:
                    raise GauntletError(
                        f"{csv_path}:{lineno}: non-numeric cell {cell!r} in column {name!r}"
                    ) from None
    if not columns["t"]:
        raise GauntletError(f"{csv_path} contains a header but no data rows")
    return {name: np.asarray(vals, dtype=float) for name, vals in columns.items()}


def load_run_log(log_dir) -> RunLog:
    """Load and validate one run-log directory."""
    log_dir = Path(log_dir)
    if not log_dir.is_dir():
        raise GauntletError(f"run log directory not found: {log_dir}")
    meta = _load_meta(log_dir)
    cols = _load_telemetry(log_dir)
    thresholds = meta.get("thresholds")
    if thresholds is not None:
        if not isinstance(thresholds, dict):
            raise GauntletError(f"{log_dir}/{META_FILENAME}: thresholds must be an object")
        thresholds = {str(k): float(v) for k, v in thresholds.items()}
    return RunLog(
        run_id=str(meta["run_id"]),
        scenario=str(meta["scenario"]),
        seed=meta["seed"],
        t=cols["t"],
        reference=cols["reference"],
        measured=cols["measured"],
        noisy=cols.get("noisy"),
        thresholds=thresholds,
    )
