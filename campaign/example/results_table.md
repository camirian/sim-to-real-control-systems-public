# Campaign results — filtered vs unfiltered (REQ-S2R-102)

- Scenario: `franka-joint-tracking-synthetic`
- Generated at: 2026-07-19T00:00:00Z
- Evidence packets: 40 used

## Headline

- Overall pass rate: filtered 20/20 vs unfiltered 0/20.
- Tracking RMS: filtered 0.09 rad vs unfiltered 0.236 rad (down 61.9% improvement).
- Filter attenuation at the vibration band: filtered 33.6 dB vs unfiltered 0.05 dB.
- Settling time: unfiltered never reaches the band (inf); filtered is finite.

## Per-condition summary

| Condition | Runs | Pass rate | RMS mean (rad) | Settling mean (s) | Overshoot mean (%) | Attenuation mean (dB) |
|---|---|---|---|---|---|---|
| filtered | 20 | 20/20 (100%) | 0.09 | 0.12 | 10.3 | 33.6 |
| unfiltered | 20 | 0/20 (0%) | 0.236 | inf | 34.5 | 0.05 |

## Metric deltas (filtered vs unfiltered)

Positive improvement = filtered is better. Percentages are signed and uncooked; a regression shows a negative improvement.

| Metric | Unit | Unfiltered mean | Filtered mean | Improvement | Better? |
|---|---|---|---|---|---|
| tracking_rms_error | rad | 0.236 | 0.09 | +61.9% | yes |
| settling_time_s | s | inf | 0.12 | unfiltered never reaches the band (inf); filtered is finite | yes |
| overshoot_pct | % | 34.5 | 10.3 | +70.1% | yes |
| filter_attenuation_db | dB | 0.05 | 33.6 | +33.55 dB | yes |

## Per-run detail

| Run | Condition | Seed | Verdict | RMS | Settling | Overshoot | Attenuation |
|---|---|---|---|---|---|---|---|
| filtered-0001 | filtered | 1 | PASS | 0.086 | 0.11 | 9.7 | 33.1 |
| filtered-0002 | filtered | 2 | PASS | 0.09 | 0.12 | 10.3 | 33.6 |
| filtered-0003 | filtered | 3 | PASS | 0.094 | 0.13 | 10.9 | 34.1 |
| filtered-0004 | filtered | 4 | PASS | 0.098 | 0.14 | 11.5 | 34.6 |
| filtered-0005 | filtered | 5 | PASS | 0.082 | 0.1 | 9.1 | 32.6 |
| filtered-0006 | filtered | 6 | PASS | 0.086 | 0.11 | 9.7 | 33.1 |
| filtered-0007 | filtered | 7 | PASS | 0.09 | 0.12 | 10.3 | 33.6 |
| filtered-0008 | filtered | 8 | PASS | 0.094 | 0.13 | 10.9 | 34.1 |
| filtered-0009 | filtered | 9 | PASS | 0.098 | 0.14 | 11.5 | 34.6 |
| filtered-0010 | filtered | 10 | PASS | 0.082 | 0.1 | 9.1 | 32.6 |
| filtered-0011 | filtered | 11 | PASS | 0.086 | 0.11 | 9.7 | 33.1 |
| filtered-0012 | filtered | 12 | PASS | 0.09 | 0.12 | 10.3 | 33.6 |
| filtered-0013 | filtered | 13 | PASS | 0.094 | 0.13 | 10.9 | 34.1 |
| filtered-0014 | filtered | 14 | PASS | 0.098 | 0.14 | 11.5 | 34.6 |
| filtered-0015 | filtered | 15 | PASS | 0.082 | 0.1 | 9.1 | 32.6 |
| filtered-0016 | filtered | 16 | PASS | 0.086 | 0.11 | 9.7 | 33.1 |
| filtered-0017 | filtered | 17 | PASS | 0.09 | 0.12 | 10.3 | 33.6 |
| filtered-0018 | filtered | 18 | PASS | 0.094 | 0.13 | 10.9 | 34.1 |
| filtered-0019 | filtered | 19 | PASS | 0.098 | 0.14 | 11.5 | 34.6 |
| filtered-0020 | filtered | 20 | PASS | 0.082 | 0.1 | 9.1 | 32.6 |
| unfiltered-0001 | unfiltered | 1 | FAIL | 0.23 | inf | 33.7 | 0.03 |
| unfiltered-0002 | unfiltered | 2 | FAIL | 0.236 | inf | 34.5 | 0.05 |
| unfiltered-0003 | unfiltered | 3 | FAIL | 0.242 | inf | 35.3 | 0.07 |
| unfiltered-0004 | unfiltered | 4 | FAIL | 0.248 | inf | 36.1 | 0.09 |
| unfiltered-0005 | unfiltered | 5 | FAIL | 0.224 | inf | 32.9 | 0.01 |
| unfiltered-0006 | unfiltered | 6 | FAIL | 0.23 | inf | 33.7 | 0.03 |
| unfiltered-0007 | unfiltered | 7 | FAIL | 0.236 | inf | 34.5 | 0.05 |
| unfiltered-0008 | unfiltered | 8 | FAIL | 0.242 | inf | 35.3 | 0.07 |
| unfiltered-0009 | unfiltered | 9 | FAIL | 0.248 | inf | 36.1 | 0.09 |
| unfiltered-0010 | unfiltered | 10 | FAIL | 0.224 | inf | 32.9 | 0.01 |
| unfiltered-0011 | unfiltered | 11 | FAIL | 0.23 | inf | 33.7 | 0.03 |
| unfiltered-0012 | unfiltered | 12 | FAIL | 0.236 | inf | 34.5 | 0.05 |
| unfiltered-0013 | unfiltered | 13 | FAIL | 0.242 | inf | 35.3 | 0.07 |
| unfiltered-0014 | unfiltered | 14 | FAIL | 0.248 | inf | 36.1 | 0.09 |
| unfiltered-0015 | unfiltered | 15 | FAIL | 0.224 | inf | 32.9 | 0.01 |
| unfiltered-0016 | unfiltered | 16 | FAIL | 0.23 | inf | 33.7 | 0.03 |
| unfiltered-0017 | unfiltered | 17 | FAIL | 0.236 | inf | 34.5 | 0.05 |
| unfiltered-0018 | unfiltered | 18 | FAIL | 0.242 | inf | 35.3 | 0.07 |
| unfiltered-0019 | unfiltered | 19 | FAIL | 0.248 | inf | 36.1 | 0.09 |
| unfiltered-0020 | unfiltered | 20 | FAIL | 0.224 | inf | 32.9 | 0.01 |

---

_Seeded, reproducible campaign — regenerate every packet from its seed and re-run `python -m campaign.cli` to reproduce this table (AGENTS.md §2)._
