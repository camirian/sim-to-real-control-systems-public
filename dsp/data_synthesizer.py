import numpy as np

def generate_telemetry(duration=5.0, fs=200.0):
    """
    Synthesize noisy ROS 2 joint state telemetry data.
    
    Args:
        duration (float): Time length of the simulation in seconds.
        fs (float): Sampling frequency in Hz (e.g., 200Hz typical for joint state publishers).
        
    Returns:
        tuple: (t, clean_signal, noisy_signal)
    """
    # Time array
    t = np.arange(0, duration, 1/fs)
    
    # Base kinematic signal (e.g., a slow-moving robotic joint, 0.5 Hz)
    f_base = 0.5 
    clean_signal = np.sin(2 * np.pi * f_base * t)
    
    # Interference 1: High frequency motor structural vibration (e.g., 25 Hz)
    f_vibration = 25.0
    vibration_noise = 0.3 * np.sin(2 * np.pi * f_vibration * t)
    
    # Interference 2: Additive White Gaussian Noise (AWGN) from encoder quantization
    awgn = np.random.normal(0, 0.1, len(t))
    
    # Combined noisy signal representing the raw ROS 2 `/joint_states` topic data
    noisy_signal = clean_signal + vibration_noise + awgn
    
    return t, clean_signal, noisy_signal

if __name__ == "__main__":
    t, clean_signal, noisy_signal = generate_telemetry()
    print(f"Generated {len(t)} data points representing {t[-1]:.2f} seconds of telemetry.")
