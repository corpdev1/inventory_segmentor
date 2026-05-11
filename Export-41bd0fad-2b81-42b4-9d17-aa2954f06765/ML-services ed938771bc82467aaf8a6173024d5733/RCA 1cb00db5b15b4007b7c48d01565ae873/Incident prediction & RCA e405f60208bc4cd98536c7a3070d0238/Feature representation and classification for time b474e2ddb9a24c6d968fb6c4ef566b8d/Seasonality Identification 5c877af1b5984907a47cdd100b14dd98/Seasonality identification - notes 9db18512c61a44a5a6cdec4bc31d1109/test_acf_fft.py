from detecta import detect_peaks
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import numpy as np
from random import random
from random import randint
from scipy.fftpack import fft
from scipy.signal import welch
from sklearn.neighbors import KernelDensity
from statsmodels.tsa import stattools
import time


def get_fft_values(y_values, num_samp, f_s):
    f_values = np.linspace(0.0, f_s / 2.0, num_samp // 2)
    fft_values_ = fft(y_values)
    # fft_values = 2.0 / num_samp * np.abs(fft_values_[0:num_samp // 2])
    fft_real = fft_values_.real[0:num_samp//2]
    fft_imag = fft_values_.imag[0:num_samp//2]

    return f_values, fft_real, fft_imag


def get_psd_values(y_values, f_s):
    f_values, psd_values = welch(y_values, fs=f_s)
    return f_values, psd_values

'''
# Based on https://ataspinar.com/2018/04/04/machine-learning-with-signal-processing-techniques/
# It is not implementing the definition of autocorrelation. It is not dividing by variance. 
def autocorr(x):
    result = np.correlate(x, x, mode='full')
    return result[len(result)//2:]


def get_autocorr_values(y_values, samp_period, num_samp, f_s):
    autocorr_values = autocorr(y_values)
    x_values = np.array([samp_period*i_samp for i_samp in range(num_samp)])
    return x_values, autocorr_values
'''

def estimate_autocorrelation(x):
    """
    http://stackoverflow.com/q/14297012/190597
    http://en.wikipedia.org/wiki/Autocorrelation#Estimation
    """
    x = np.array(x)
    n = len(x)
    variance = x.var()
    x = x-x.mean()
    r = np.correlate(x, x, mode='full')[-n:]
    assert np.allclose(r, np.array([(x[:n-k]*x[-(n-k):]).sum() for k in range(n)]))
    result = r/(variance*(np.arange(n, 0, -1)))
    return result

t_n = 10000  # time in seconds
num_samp = 1000
samp_period = t_n / num_samp
f_s = 1 / samp_period
autocorr_lags = num_samp//3

x_value = np.linspace(0, t_n, num_samp)

# sinusoidal composite signal
amplitudes = [10]  # [4, 6, 8, 10, 14]
frequencies = [0.4]  # [6.5, 5, 3, 1.5, 1]  # Frequency in Hz
y_values = [amplitudes[i_comp]*np.sin(2*np.pi*frequencies[i_comp]*x_value) for i_comp in range(0, len(amplitudes))]
composite_y_value = np.sum(y_values, axis=0)

# periodic sparse model
noise_range = 0.5
sparse_low = 4
sparse_high = 6
sparse_period = 100  # in terms of number of samples

sparse_y_value = [random() * noise_range for _ in range(num_samp)]

for spike_ind in range(50, num_samp, sparse_period):
    sparse_y_value[spike_ind] = sparse_low + random()*(sparse_high - sparse_low)

# random sparse model
sparse_prob = [0.01, 0.05]  # data with different percentage of sparsity

sparse_random_y_value = [sparse_low + random() * (sparse_high - sparse_low) if random() < sparse_prob[0]
                         else random() * noise_range for _ in range(num_samp)]

# periodic step model
noise_range = 0
step_low = 4
step_high = 4
step_period = 10  # in terms of number of samples

step_y_value = [random() * noise_range for _ in range(num_samp)]

for step_ind in range(50, num_samp, step_period):
    step_y_value[step_ind:(step_ind + (step_period//2))] = [step_low + random()*(step_high - step_low)]*(step_period//2)

# random step model
step_prob = [0.1]  # data with different frequencies in step occurrence
step_range = 10

step_random_y_value = []

for cur_ind in range(num_samp):
    if random() < step_prob[0]:
        step_random_y_value.append(randint(0, step_range))
    else:
        if not step_random_y_value:
            step_random_y_value.append(randint(0, step_range))
        else:
            step_random_y_value.append(step_random_y_value[-1])

ip_y_value = np.array(composite_y_value)

ip_y_value = (ip_y_value - ip_y_value.mean())/ip_y_value.std()  # zero mean, unit variance normalization

# From: https://ataspinar.com/2018/04/04/machine-learning-with-signal-processing-techniques/
# Doesn't divide by variance.
# t_values, autocorr_values = get_autocorr_values(sparse_random_y_value, samp_period, num_samp, f_s)

autocorr_unutbu = estimate_autocorrelation(ip_y_value)[1:autocorr_lags]  # first (no lag) ACF value will be equal to 1

autocorr_statsmodels = stattools.acf(ip_y_value, nlags=autocorr_lags)[1:]

# Begin: Logic for measuring size of peaks that assumes that the peaks are in the form of spikes.
'''
peak_ind = detect_peaks(autocorr_statsmodels, show=True)

peak_val = []

for i_peak in peak_ind:
    peak_val.append(max(autocorr_statsmodels[i_peak] - autocorr_statsmodels[i_peak-1],
                        autocorr_statsmodels[i_peak+1] - autocorr_statsmodels[i_peak]))

max_peak_val = max(peak_val)
'''
# End: Logic for measuring size of peaks that assumes that the peaks are in the form of spikes.

# Picking peaks based on the maximum positive ACF peak.
all_peak_ind = detect_peaks(autocorr_statsmodels, show=True)

max_peak_val = max(autocorr_statsmodels[all_peak_ind])

if max_peak_val <= 0:
    print('Time-series is not periodic.')
else:
    all_peak_ind = detect_peaks(autocorr_statsmodels, threshold=0.1*max_peak_val, show=True)

    peak_ind = []

    for cur_ind in all_peak_ind:
        if autocorr_statsmodels[cur_ind] > 0.2*max_peak_val:
            peak_ind.append(cur_ind)

    if len(peak_ind) == 0:
        print("ACF has no peaks!")
        s = [0]
        e = [0]
    elif len(peak_ind) == 1:
        print("ACF has only one peak!")
        acf_clusters = [peak_ind*samp_period]
        s = [peak_ind]
        e = [1]
    else:
        acf_intervals = []

        for i_peak, j_peak in zip(peak_ind, peak_ind[1:]):
            acf_intervals.append(j_peak - i_peak)

        a = np.array(acf_intervals).reshape(-1, 1)
        kde = KernelDensity(kernel='gaussian', bandwidth=3).fit(a)
        s = np.linspace(0, 2*max(acf_intervals))
        e = kde.score_samples(s.reshape(-1, 1))

        acf_cluster_ind = detect_peaks(e, show=True)
        acf_clusters = s[acf_cluster_ind]*samp_period

# spectral analysis based on https://ataspinar.com/2018/04/04/machine-learning-with-signal-processing-techniques/
f_values_fft, fft_real, fft_imag = get_fft_values(ip_y_value, num_samp, f_s)

f_values_psd, psd_values = get_psd_values(ip_y_value, f_s)

"""
fig = plt.figure()
ax = fig.add_subplot(111)
plt.plot(ip_y_value, linestyle='-', color='blue')
plt.title('The time-series')
plt.show()

fig = plt.figure()
ax = fig.add_subplot(111)
plt.plot(autocorr_unutbu)
plt.title('Unutbu autocorrelation')
plt.show()

fig = plt.figure()
ax = fig.add_subplot(111)
plt.plot(autocorr_statsmodels)
plt.title('Statsmodels autocorrelation')
plt.show()

fig = plt.figure()
ax = fig.add_subplot(111)
plt.plot(s, e)
plt.title('Autocorrelation KDE')
plt.show()

fig = plt.figure()
ax = fig.add_subplot(111)
plt.plot(f_values_fft, fft_values, linestyle='-', color='blue')
plt.xlabel('Frequency [Hz]')
plt.ylabel('Amplitude')
plt.title('Frequency domain representation of the time-series')
plt.show()

fig = plt.figure()
ax = fig.add_subplot(111)
plt.plot(f_values_psd, psd_values, linestyle='-', color='blue')
plt.xlabel('Frequency [Hz]')
plt.ylabel('PSD [V**2 / Hz]')
plt.title('Power spectral density')
plt.show()
"""

fig, axs = plt.subplots(3, 3)
axs[0, 0].plot(np.arange(num_samp)*samp_period, ip_y_value, linestyle='-', color='blue')
axs[0, 0].set_title('The time-series')
axs[0, 1].plot(autocorr_unutbu)
axs[0, 1].set_title('Unutbu autocorrelation')
axs[0, 2].plot(autocorr_statsmodels)
axs[0, 2].plot(peak_ind, autocorr_statsmodels[peak_ind], 'r+')
axs[0, 2].set_title('Statsmodels autocorrelation')
axs[1, 0].plot(s, e)
axs[1, 0].set_title('Autocorrelation KDE')
axs[1, 1].plot(f_values_fft, fft_real, linestyle='-', color='blue')
axs[1, 1].set_title('Real part of the FFT')
axs[1, 2].plot(f_values_fft, fft_imag, linestyle='-', color='blue')
axs[1, 2].set_title('Imaginary part of the FFT')
axs[2, 0].plot(f_values_psd, psd_values, linestyle='-', color='blue')
axs[2, 0].set_title('Power spectral density')
plt.show()

time.sleep(1)