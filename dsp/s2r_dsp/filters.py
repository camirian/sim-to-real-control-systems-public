import numpy as np
import scipy.signal as signal

def design_fir_lowpass(fs, cutoff, numtaps=101):
    """
    Design an FIR (Finite Impulse Response) low-pass filter using the window method.
    FIR filters have guaranteed stability and exact linear phase.
    
    Args:
        fs (float): Sampling frequency.
        cutoff (float): Cutoff frequency in Hz.
        numtaps (int): Number of filter coefficients (taps).
        
    Returns:
        tuple: (b, a) FIR filter coefficients. 'a' is always [1.0] for FIR.
    """
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq
    # Using a Hamming window for good side-lobe attenuation
    b = signal.firwin(numtaps, normal_cutoff, window='hamming')
    a = [1.0]
    return b, a

def design_iir_lowpass(fs, cutoff, order=4):
    """
    Design an IIR (Infinite Impulse Response) low-pass Butterworth filter.
    IIR filters offer steeper roll-off with fewer coefficients (lower latency).
    
    Args:
        fs (float): Sampling frequency.
        cutoff (float): Cutoff frequency in Hz.
        order (int): Order of the Butterworth filter.
        
    Returns:
        tuple: (b, a) IIR filter coefficients.
    """
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq
    b, a = signal.butter(order, normal_cutoff, btype='low', analog=False)
    return b, a

def apply_filter_realtime(b, a, data):
    """
    Apply a filter mimicking a real-time ROS 2 node stream (causal).
    This introduces phase delay inherent to the filter design.
    """
    return signal.lfilter(b, a, data)

def apply_filter_offline(b, a, data):
    """
    Apply a filter with zero phase distortion by filtering forwards and backwards.
    Useful for offline trajectory analysis, but impossible in real-time edge control.
    """
    return signal.filtfilt(b, a, data)
