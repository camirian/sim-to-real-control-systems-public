# gauntlet — certification gauntlet (M3, REQ-S2R-100/101)

Grades logged closed-loop runs into immutable JSON evidence packets and
markdown compliance reports. Pure Python — no ROS, no Isaac, runs anywhere.

Provenance: ports the evidence-packet concept from the archived
`camirian/sim-to-real-benchmarking` repo (see `gauntlet/__init__.py` for the
full note — the archive was unreachable from the cloud sandbox, so this is a
clean-room re-implementation of the documented concept).

## Grade a run

```bash
pip install -e "dsp/[test]"   # provides s2r_dsp for the fixtures/tests
python -m gauntlet.cli path/to/run-log --evidence-dir evidence \
    --timestamp 2026-07-19T12:00:00Z
```

Exit codes: `0` graded + PASSED, `1` graded + FAILED, `2` invalid input (no
verdict emitted — corrupt logs can never PASS).

## Run-log format (rosbag/CSV export)

```
<log_dir>/
  run_meta.json   {"run_id": "0001", "scenario": "...", "seed": 42,
                   "thresholds": {...}}          # thresholds optional
  telemetry.csv   t,reference,measured[,noisy]   # noisy = pre-filter stream;
                                                 # enables the attenuation check
```

## Checks

| Check | Default threshold | Definition |
|---|---|---|
| `tracking_rms_error` | ≤ 0.15 rad | RMS of measured − reference |
| `settling_time_s` | ≤ 2.0 s | earliest time after which \|error\| stays ≤ 0.2 rad |
| `overshoot_pct` | ≤ 25 % | worst \|error\| as % of reference span |
| `filter_attenuation_db` | ≥ 20 dB | band-power drop noisy→measured at 25±2 Hz (SKIPPED without a `noisy` column) |

Every packet embeds seed, scenario, thresholds, per-check verdicts, and
environment versions; identical inputs produce identical bytes (timestamps
only via `--timestamp`). Committed packets are immutable — regenerate under a
new run id, never edit (AGENTS.md §2).

## Tests

```bash
python -m pytest gauntlet/    # fixture-driven, incl. golden-file report test
```
