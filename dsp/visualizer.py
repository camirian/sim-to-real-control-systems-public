import os
import numpy as np
import matplotlib.pyplot as plt
import scipy.signal as signal
from s2r_dsp import (
    apply_filter_realtime,
    design_fir_lowpass,
    design_iir_lowpass,
    generate_telemetry,
)

def plot_bode(b, a, fs, title, filename):
    """Generate and save a Bode plot (magnitude and phase) for a given filter."""
    w, h = signal.freqz(b, a, worN=8000)
    w_hz = w * fs / (2 * np.pi)
    
    fig, ax1 = plt.subplots(figsize=(8, 5))
    ax1.set_title(title)
    
    # Magnitude plot
    ax1.plot(w_hz, 20 * np.log10(np.clip(abs(h), 1e-10, None)), 'b')
    ax1.set_ylabel('Amplitude [dB]', color='b')
    ax1.set_xlabel('Frequency [Hz]')
    ax1.set_ylim([-100, 10])
    
    # Phase plot
    ax2 = ax1.twinx()
    angles = np.unwrap(np.angle(h))
    ax2.plot(w_hz, angles * 180 / np.pi, 'g')
    ax2.set_ylabel('Phase [degrees]', color='g')
    
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(filename)
    plt.close()

def plot_time_domain(t, clean, noisy, fir_filtered, iir_filtered, filename):
    """Plot time-domain comparison of the filters tracking the truth signal."""
    plt.figure(figsize=(10, 6))
    
    plt.plot(t, noisy, label="Raw Noisy Telemetry (ROS 2 /joint_states)", color='lightgray', alpha=0.7)
    plt.plot(t, clean, label="Ground Truth (Ideal Kinematics)", color='k', linestyle='--', linewidth=2)
    
    # Note: real-time filters will exhibit a phase delay. FIR delay is constant.
    plt.plot(t, fir_filtered, label="FIR Filtered Output (delay = N/2 taps)", color='b', linewidth=1.5)
    plt.plot(t, iir_filtered, label="IIR Filtered Output (non-linear phase delay)", color='r', alpha=0.8, linewidth=1.5)
    
    plt.title('Time-Domain Comparison: Filter Tracking Performance')
    plt.xlabel('Time [s]')
    plt.ylabel('Amplitude')
    plt.legend()
    plt.xlim([0, t[-1]])
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(filename)
    plt.close()

def main():
    # Configuration
    fs = 200.0  # Sampling frequency in Hz
    cutoff = 5.0  # Low-pass cutoff frequency in Hz
    asset_dir = 'assets'
    os.makedirs(asset_dir, exist_ok=True)
    
    # 1. Synthesize Data
    t, clean_signal, noisy_signal = generate_telemetry(duration=5.0, fs=fs)
    
    # 2. Design Filters
    fir_b, fir_a = design_fir_lowpass(fs, cutoff, numtaps=101)
    iir_b, iir_a = design_iir_lowpass(fs, cutoff, order=4)
    
    # 3. Generate Bode Plots
    plot_bode(fir_b, fir_a, fs, 'FIR Low-pass Filter Frequency Response (N=101, Hamming)', os.path.join(asset_dir, 'fir_bode.png'))
    plot_bode(iir_b, iir_a, fs, 'IIR Low-pass Filter Frequency Response (Butterworth N=4)', os.path.join(asset_dir, 'iir_bode.png'))
    
    # 4. Apply Filters (using realtime/causal implementation to demonstrate phase lag)
    fir_filtered = apply_filter_realtime(fir_b, fir_a, noisy_signal)
    iir_filtered = apply_filter_realtime(iir_b, iir_a, noisy_signal)
    
    # 5. Generate Time-Domain plot
    plot_time_domain(t, clean_signal, noisy_signal, fir_filtered, iir_filtered, os.path.join(asset_dir, 'time_domain_comparison.png'))
    
    print(f"Visualizations successfully generated and saved to {os.path.abspath(asset_dir)}/")

if __name__ == "__main__":
    main()
