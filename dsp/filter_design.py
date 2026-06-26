import numpy as np
import scipy.signal as signal
import matplotlib.pyplot as plt
import os

def generate_ros2_mock_data(t, true_freq=1.0, noise_freqs=[20.0, 45.0], noise_levels=[0.5, 0.3], white_noise_level=0.2):
    """Generates mock ROS 2 joint state data (sine wave + high freq noise + white noise)"""
    # True underlying joint motion (e.g., repeating 1Hz sinusoidal movement)
    true_signal = np.sin(2 * np.pi * true_freq * t)
    
    noisy_signal = np.copy(true_signal)
    
    # Add predictable motor/gearbox harmonic noise
    for freq, level in zip(noise_freqs, noise_levels):
        noisy_signal += level * np.sin(2 * np.pi * freq * t)
        
    # Add random electromagnetic interference (white noise)
    noisy_signal += np.random.normal(0, white_noise_level, size=len(t))
    
    return true_signal, noisy_signal

def main():
    # Simulation Parameters
    fs = 100.0  # 100 Hz sampling rate (typical for ROS 2 joint_states)
    T = 2.0     # 2 seconds of data
    t = np.arange(0, T, 1/fs)
    
    # Generate data
    true_signal, noisy_signal = generate_ros2_mock_data(t)
    
    # Filter Specifications
    cutoff_freq = 5.0  # We want to keep the 1Hz signal but remove 20Hz+ noise
    nyq_freq = 0.5 * fs
    normalized_cutoff = cutoff_freq / nyq_freq
    
    # 1. FIR Filter Design (Window method)
    numtaps = 41 # Filter order + 1
    fir_coeffs = signal.firwin(numtaps, normalized_cutoff, window='hamming')
    
    # 2. IIR Filter Design (Butterworth)
    iir_order = 4
    iir_b, iir_a = signal.butter(iir_order, normalized_cutoff, btype='low')
    
    # Apply filters using filtfilt for zero phase shift
    # (Typical for offline analysis; realtime would use lfilter and accept phase delay)
    fir_filtered = signal.filtfilt(fir_coeffs, 1.0, noisy_signal)
    iir_filtered = signal.filtfilt(iir_b, iir_a, noisy_signal)
    
    # --- Plotting Time Domain ---
    plt.figure(figsize=(12, 8))
    
    plt.subplot(3, 1, 1)
    plt.plot(t, noisy_signal, label='Raw ROS 2 Joint Data (Noisy)', color='lightgray')
    plt.plot(t, true_signal, label='True Joint Kinematics', color='black', linestyle='--')
    plt.title('Time Domain: Mock Joint State Telemetry')
    plt.ylabel('Angle (rad)')
    plt.legend()
    plt.grid(True)
    
    plt.subplot(3, 1, 2)
    plt.plot(t, noisy_signal, color='lightgray', alpha=0.5)
    plt.plot(t, fir_filtered, label=f'FIR Filtered (Order={numtaps-1})', color='blue')
    plt.ylabel('Angle (rad)')
    plt.legend()
    plt.grid(True)
    
    plt.subplot(3, 1, 3)
    plt.plot(t, noisy_signal, color='lightgray', alpha=0.5)
    plt.plot(t, iir_filtered, label=f'IIR Filtered (Butterworth Order={iir_order})', color='darkorange')
    plt.xlabel('Time (s)')
    plt.ylabel('Angle (rad)')
    plt.legend()
    plt.grid(True)
    
    plt.tight_layout()
    plt.savefig('filter_comparison.png', dpi=300)
    plt.close()
    
    # --- Plotting Frequency Response (Bode Plot) ---
    plt.figure(figsize=(10, 6))
    
    # FIR Response
    w_fir, h_fir = signal.freqz(fir_coeffs, 1, worN=8000)
    freq_fir = w_fir * fs / (2 * np.pi)
    
    # IIR Response
    w_iir, h_iir = signal.freqz(iir_b, iir_a, worN=8000)
    freq_iir = w_iir * fs / (2 * np.pi)
    
    plt.plot(freq_fir, 20 * np.log10(np.abs(h_fir)), color='blue', label=f'FIR (order={numtaps-1})')
    plt.plot(freq_iir, 20 * np.log10(np.abs(h_iir)), color='darkorange', label=f'IIR Butterworth (order={iir_order})')
    
    plt.axvline(cutoff_freq, color='red', linestyle='--', label=f'Cutoff Frequency ({cutoff_freq} Hz)')
    plt.title('Bode Plot: Filter Frequency Response Comparison')
    plt.xlabel('Frequency (Hz)')
    plt.ylabel('Magnitude (dB)')
    plt.ylim(-80, 5)
    plt.xlim(0, fs/2)
    plt.grid(True, which='both', linestyle='--', alpha=0.7)
    plt.legend()
    
    plt.tight_layout()
    plt.savefig('bode_plot.png', dpi=300)
    plt.close()
    
    print("Files 'filter_comparison.png' and 'bode_plot.png' generated successfully.")

if __name__ == '__main__':
    main()
