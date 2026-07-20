# campaign/example — SYNTHETIC demonstration (NOT the real campaign)

The `results_table.md` and `results.json` in this directory are a **synthetic
demonstration** of the aggregator's output shape. They are generated from
`campaign.synth` (hand-picked passing/failing metric profiles), **not** from a
real Isaac Sim run. They exist so a reviewer — or CI — can see the "money table"
format without a sim box.

The real REQ-S2R-102 artifact is produced on the EdgeXpert per
[docs/RUN_ON_EDGEXPERT.md](../../docs/RUN_ON_EDGEXPERT.md): 20+ seeded filtered
and 20+ seeded unfiltered live runs, graded by the gauntlet, then aggregated by
this same tool. Those numbers will differ from the synthetic ones here.

## Reproduce this example (no ROS/Isaac — runs anywhere)

From the repository root, with `s2r_dsp` installed (`pip install -e "dsp/[test]"`):

```bash
python -c "from campaign.synth import write_campaign; \
  write_campaign('/tmp/demo_evidence', n_filtered=20, n_unfiltered=20, \
  generated_at='2026-07-19T00:00:00Z')"
python -m campaign.cli /tmp/demo_evidence --out-dir campaign/example \
  --timestamp 2026-07-19T00:00:00Z
```

The synthetic evidence packets themselves are intentionally **not** committed
(they are derived and regenerate deterministically from the command above);
only the two rendered outputs are kept here as a reference.
