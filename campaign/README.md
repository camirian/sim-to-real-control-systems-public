# campaign — results aggregation (M4, REQ-S2R-102)

Turns a directory of gauntlet evidence packets (`run-<id>.json`, the format
`gauntlet/evidence.py` emits) into the MASTER_PLAN "money table": the
filtered-vs-unfiltered comparison over N seeded runs, as commit-quality
`results_table.md` plus machine-readable `results.json`.

Pure Python, deterministic, no ROS/Isaac. Packets are validated by
`gauntlet.evidence.load_packet` (reused, not reimplemented), so a corrupt or
tampered packet can never enter the table.

## Layout

| Module | Role | Runs where |
|---|---|---|
| `aggregate.py` | evidence dir -> `CampaignResult` (stats + honest deltas) | anywhere |
| `render.py` | `CampaignResult` -> `results_table.md` + `results.json` | anywhere |
| `cli.py` | `python -m campaign.cli` entry point | anywhere |
| `synth.py` | synthesize evidence packets for tests + smoke test | anywhere |
| `run_campaign.py` | orchestrate the live seeded sweep on the EdgeXpert | pure glue tested anywhere; live-sim parts EDGEXPERT-VERIFY |
| `example/` | a **synthetic** demonstration of the output (not a real run) | — |

## Condition classification

A run's condition is the leading token of its run id
(`filtered-0007` -> `filtered`, `unfiltered-0007` -> `unfiltered`). The campaign
runner writes ids following this convention. Packets whose id has no recognized
prefix are skipped with a recorded warning.

## Malformed packets: skip-with-warning (documented decision)

A single corrupt or unclassifiable packet is **skipped with a warning** — never
fatal — so one bad file cannot sink an otherwise-complete 40-run campaign. Every
skip is recorded in `CampaignResult.warnings` and surfaced on stderr and in both
rendered outputs, so a skip is always visible. An **empty or entirely
unusable** directory raises `CampaignError` (exit 2): there is no honest table
to render from zero runs.

## Honest deltas (no cooking)

Improvement figures are signed and oriented so positive means "filtered is
better". A filtered set that does **not** beat unfiltered yields a negative
improvement, `improved=False`, a `Better? = NO` row, a `REGRESSION` headline,
and CLI exit code 1. `filter_attenuation_db` is reported as an absolute dB gap
(a percentage over a logarithmic quantity is meaningless); the linear metrics
are reported as percentages.

## Run the aggregator (anywhere)

```bash
pip install -e "dsp/[test]"            # provides s2r_dsp (gauntlet needs it)
python -m campaign.cli <evidence_dir> --out-dir <out> [--timestamp <iso8601>]
```

Exit codes: `0` filtered beats unfiltered on tracking RMS · `1` no improvement
(honest) · `2` invalid input (no table emitted).

## Test without ROS (anywhere)

```bash
pip install -e "dsp/[test]"
python -m pytest campaign/ -q
```

## The full campaign on the EdgeXpert

See [docs/RUN_ON_EDGEXPERT.md](../docs/RUN_ON_EDGEXPERT.md). One command drives
the seeded sweep, grading, and aggregation:

```bash
python -m campaign.run_campaign --seeds $(seq 1 20) --evidence-dir evidence
```

The `ros2 launch` execution inside `run_campaign.py` is EDGEXPERT-VERIFY and
has only been syntax-checked in the cloud; the plan/command-builder glue it
relies on is unit-tested.
