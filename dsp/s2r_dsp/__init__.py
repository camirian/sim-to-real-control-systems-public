"""s2r_dsp — DSP library for the sim-to-real control loop (REQ-S2R-001).

Public API:

- Filter design: :func:`design_fir_lowpass`, :func:`design_iir_lowpass`
- Causal, in-loop filtering: :func:`apply_filter_realtime`
- Zero-phase, offline-analysis-only filtering: :func:`apply_filter_offline`
- Seeded noisy joint-telemetry synthesizer: :func:`generate_telemetry`

Ground rule (see AGENTS.md §2): only the causal ``apply_filter_realtime``
path may be used in the closed loop; ``apply_filter_offline`` (zero-phase,
forward-backward) is for offline analysis only.
"""

from s2r_dsp.data_synthesizer import generate_telemetry
from s2r_dsp.filters import (
    apply_filter_offline,
    apply_filter_realtime,
    design_fir_lowpass,
    design_iir_lowpass,
)

__version__ = "0.1.0"

__all__ = [
    "apply_filter_offline",
    "apply_filter_realtime",
    "design_fir_lowpass",
    "design_iir_lowpass",
    "generate_telemetry",
    "__version__",
]
