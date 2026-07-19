# Compliance report — run golden-0001

**Verdict: PASSED**

- Scenario: `franka-joint-tracking-synthetic`
- Seed: `42`
- Schema version: 1
- Generated at: 2026-07-19T00:00:00Z

## Checks

| Check | Value | Threshold | Result |
|---|---|---|---|
| tracking_rms_error | 0.0912 | <= 0.15 | PASS |
| settling_time_s | 0.115 | <= 2 | PASS |
| overshoot_pct | 10.26 | <= 25 | PASS |
| filter_attenuation_db | 33.6 | >= 20 | PASS |

## Environment

- gauntlet: 0.1.0
- numpy: 1.26.4
- python: 3.10.12
- s2r_dsp: 0.1.0
- scipy: 1.11.4

## Thresholds

- filter_attenuation_min_db: 20
- overshoot_max_pct: 25
- settling_band_rad: 0.2
- settling_time_max_s: 2
- tracking_rms_error_max: 0.15
- vibration_band_halfwidth_hz: 2
- vibration_band_hz: 25

---

_Seeded, reproducible run — regenerate this packet from the same seed
and log to reproduce these numbers (AGENTS.md §2)._
