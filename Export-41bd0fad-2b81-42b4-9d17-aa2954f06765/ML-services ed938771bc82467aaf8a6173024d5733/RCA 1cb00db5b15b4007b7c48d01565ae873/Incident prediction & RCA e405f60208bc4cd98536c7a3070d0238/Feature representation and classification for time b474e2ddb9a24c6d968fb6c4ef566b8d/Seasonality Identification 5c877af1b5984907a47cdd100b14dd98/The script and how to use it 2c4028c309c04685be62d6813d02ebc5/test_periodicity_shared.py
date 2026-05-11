from datetime import datetime
from bisect import bisect_left
from detecta import detect_peaks
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from os import walk
import numpy as np
from numpy.random import permutation
import pandas as pd
import pickle
import plotly.graph_objects as go
from scipy.fftpack import fft
from scipy.signal import butter, filtfilt, periodogram
from statsmodels.tsa import stattools
import stumpy
import time
import tqdm


def find_closest(my_list, my_number):
    """
    Assumes my_list is sorted. Returns closest value to my_number.

    If two numbers are equally close, return the smallest number.
    """
    pos = bisect_left(my_list, my_number)
    if pos == 0:
        return my_list[0]
    if pos == len(my_list):
        return my_list[-1]
    before = my_list[pos - 1]
    after = my_list[pos]
    if after - my_number < my_number - before:
        return after
    else:
        return before


def find_bound(my_list, my_number, bound_type):
    if bound_type is 'upper':
        less_list = [x for x in my_list if my_number < x]
        return min(less_list)
    elif bound_type is 'lower':
        more_list = [x for x in my_list if my_number > x]
        return max(more_list)
    else:
        print("Enter either 'upper' or 'lower'")


def get_fft_values(y_values, num_samp, f_s):
    f_values = np.arange(num_samp // 2)  # np.linspace(0.0, f_s / 2.0, num_samp // 2)
    fft_values_ = fft(y_values)
    # fft_values = 2.0 / num_samp * np.abs(fft_values_[0:num_samp // 2])
    fft_real = fft_values_.real[0:num_samp//2]
    fft_imag = fft_values_.imag[0:num_samp//2]

    return f_values, fft_real, fft_imag


def get_psd_values(y_values, f_s):
    f_values, psd_values = periodogram(y_values, fs=f_s)
    # Note: for the welch method, it is not clear how to set the parameters like fs and nperseg to produce expected
    # results.
    return f_values, psd_values


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


# compute moving window aggregate (MWA) version of input sequence
# For logstash output, which is aggregated every ten seconds.
# 5 minute window, win_size = 30, 10 minute window, win_size = 60
# 30 minute window, win_size = 180
def compute_mwa(ip_data, win_size, stat_type='mean'):
    series_size = ip_data.shape[0]
    mwa_data = []

    if ip_data.ndim == 1:
        for i in range(series_size - win_size):
            if stat_type is 'mean':
                mwa_data.append(sum(ip_data[i:i+win_size])/win_size)
            elif stat_type is 'max':
                mwa_data.append(max(ip_data[i:i+win_size]))
        return np.array(mwa_data)
    else:
        for i_col in range(ip_data.shape[1]):
            col_data = []
            for i in range(series_size - win_size):
                if stat_type is 'mean':
                    col_data.append(sum(ip_data[i:i+win_size, i_col])/win_size)
                elif stat_type is 'max':
                    col_data.append(max(ip_data[i:i+win_size, i_col]))
            mwa_data.append(col_data)

        return np.array(mwa_data).transpose()


def exp_wt_avg_std(ip_buffer):
    ip_series = pd.Series(ip_buffer)
    exp_mean = ip_series.ewm(ignore_na=False, min_periods=0, adjust=True, com=50).mean()
    exp_std = ip_series.ewm(ignore_na=False, min_periods=0, adjust=True, com=50).std(bias=False)

    return exp_mean.iloc[-1], exp_std.iloc[-1]


# Variables to set
sampling_period_num = 60
target_scale = "1H_to_1D"  # "1M_to_1H"
zscore_flag = False
zscore_win = 1440
csv_filenames = ["lfanalyzer_6040a96cdcc614001153fc55-docker-log-post-processing_post-processing-stashed.csv"]

sampling_period = f"{sampling_period_num}S"

if target_scale == "1H_to_1D":
    total_num_samples = int(86400/sampling_period_num)*7
    mwa_win = int(3600/sampling_period_num)
    period_low_lim = int(2700/sampling_period_num)
elif target_scale == '1M_to_1H':
    total_num_samples = int(3600/sampling_period_num)*7
    mwa_win = 2
    period_low_lim = int(120/sampling_period_num)

mp_dict = {}

tp_op_all_in_one_dict = {}

for csv_filename in tqdm.tqdm(csv_filenames):
    print(csv_filename)
    csv_filename_core = csv_filename.split('.')[0]
    op_core = 'smaller_scale_' + csv_filename_core

    op_dict = {}
    df_all_cols = pd.read_csv(csv_filename)

    df_input = df_all_cols[['timestamp', 'n_message']].copy()
    if df_input.empty:
        print(f"{csv_filename} is empty")
        continue
    df_input = df_input.rename(columns={'n_message': 'value'})
    df_input['datetime'] = df_input.apply(lambda x: datetime.strptime(x['timestamp'], '%Y-%m-%d %H:%M:%S'), axis=1)
    df_input.drop('timestamp', 1)
    df_input['timestamp'] = df_input.apply(lambda x: time.mktime(x['datetime'].timetuple()), axis=1)
    df_input.sort_values('timestamp', inplace=True)
    df_input.drop_duplicates(subset='timestamp', inplace=True)
    df_input.set_index('datetime', inplace=True)
    df_input = df_input.asfreq(sampling_period).fillna(method='ffill')
    df_input = df_input[:total_num_samples + zscore_win]

    num_values = df_input.shape[0]

    if num_values < mwa_win or num_values < zscore_win:
        print('Very few samples')
        continue

    value_list = df_input['value']

    timestamp_list = df_input['timestamp'].to_list()

    datetime_list = df_input.index.to_list()
    ori_y_value = df_input['value'].to_numpy()

    if zscore_flag:
        moving_buffer = ori_y_value[:zscore_win].tolist()
        cur_value = moving_buffer[zscore_win-1]
        zscore_value = []

        for i in range(zscore_win, len(ori_y_value)):
            cur_mean, cur_std = exp_wt_avg_std(moving_buffer)
            zscore_value.append(abs(cur_value - cur_mean))

            cur_value = ori_y_value[i]
            moving_buffer.append(cur_value)
            moving_buffer.pop(0)

        metric_y_value = np.array(zscore_value)

        metric_y_value = compute_mwa(metric_y_value, mwa_win)
    else:
        if len(ori_y_value) > 2*mwa_win:
            mwa_y_value = compute_mwa(ori_y_value, mwa_win)
        else:
            mwa_y_value = np.copy(ori_y_value)
        metric_y_value = np.array(mwa_y_value)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_input.index, y=df_input['value'], name='True', opacity=0.5))
    fig.update_layout(showlegend=True, title='Input time-series')
    fig.write_image(op_core + '_ori_ts.png')
    fig.write_html(op_core + '_ori_ts.html')

    start_time = time.process_time()
    all_candidate_periods = []
    if np.all(metric_y_value == metric_y_value[0]):
        print('{} is a constant array of value {}.'.format(csv_filename, metric_y_value[0]))
        op_dict['detected_time_periods'] = []
    else:
        # set sampling frequency as 1, irrespective of actual sampling frequency.
        # Output time period needs to be multiplied by the sampling period to get absolute time period
        # Thus, if the sampling is every 5 minutes. An output of 100 means a time period of 500 minutes.
        f_s = 1
        f_nyq = f_s / 2
        t_n = int(metric_y_value.size / f_s)
        samp_period = 1 / f_s
        num_samp = t_n * f_s
        autocorr_lags = num_samp // 3
        acf_peak_thresh = 0.1

        metric_y_value = metric_y_value[:num_samp]
        datetime_list = datetime_list[:num_samp]
        # metric_y_value = (metric_y_value - metric_y_value.mean()) / metric_y_value.std()
        # zero mean, unit variance normalization

        ip_y_value = np.array(metric_y_value)

        autocorr_statsmodels, confint_statsmodels = stattools.acf(ip_y_value, nlags=autocorr_lags, fft=True, alpha=0.05)

        autocorr_statsmodels = autocorr_statsmodels[1:]
        confint_statsmodels = confint_statsmodels[1:]

        f_values_fft, fft_real, fft_imag = get_fft_values(ip_y_value, num_samp, f_s)

        f_values_psd, psd_values = get_psd_values(ip_y_value, f_s)

        peak_psd_vals = []

        # Select spectral threshold
        for _ in range(100):
            perm_y_value = permutation(ip_y_value)
            perm_f_values, perm_psd_values = get_psd_values(perm_y_value, f_s)
            peak_psd_vals.append(max(perm_psd_values))

        psd_thresh = sorted(peak_psd_vals)[1]

        select_ind = np.where(psd_values >= psd_thresh)[0]

        if select_ind.size == 0:
            print("No periodicity in the given time-series.")
            op_dict['detected_time_periods'] = []
        else:
            reverse_ind = select_ind[::-1]

            if reverse_ind.size == 1 and reverse_ind[0] == 0:
                print("No periodicity in the given time-series.")
                op_dict['detected_time_periods'] = []
            else:
                candidate_clusters = [[reverse_ind[0]]]

                if reverse_ind.size > 1:
                    next_thresh = num_samp / (candidate_clusters[0][0] - 1) + 1
                    cur_cluster = 0

                    for cur_ind in reverse_ind[1:]:
                        # TODO: document cases when cur_ind == 0
                        if cur_ind == 0:
                            if 1 in candidate_clusters[cur_cluster]:
                                candidate_clusters[cur_cluster].append(cur_ind)
                        else:
                            # Create clusters of utmost size 2
                            if num_samp / cur_ind < next_thresh and len(candidate_clusters[cur_cluster]) == 1:
                                candidate_clusters[cur_cluster].append(cur_ind)
                            else:
                                candidate_clusters.append([cur_ind])
                                cur_cluster += 1

                            if cur_ind > 1:
                                next_thresh = num_samp / (cur_ind - 1) + 1

                candidate_freq_inds = []

                # print('Candidate frequency clusters')
                # print(candidate_clusters)

                for cur_cluster in candidate_clusters:
                    candidate_freq_inds.append(cur_cluster[0])

                # print('Candidate frequency indices')
                # print(candidate_freq_inds)

                candidate_periods = []
                for cur_freq_ind in candidate_freq_inds:
                    candidate_period = int(num_samp / cur_freq_ind)
                    if candidate_period < autocorr_statsmodels.size:
                        candidate_periods.append(candidate_period)

                candidate_periods = sorted(set(candidate_periods))

                ip_lp_smooth = np.copy(ip_y_value)
                acf_lp_smooth = np.copy(autocorr_statsmodels)

                acf_peak_periods = []
                acf_quadratics = {}
                acf_lp_smooth_dict = {}

                all_candidate_periods = candidate_periods
                print("Candidate periods")
                print(candidate_periods)

                for cur_period in candidate_periods:
                    # print("Testing period {}".format(cur_period))
                    left_lim = int(0.5 * cur_period)
                    right_lim = min(int(1.5 * cur_period), acf_lp_smooth.size)

                    poly_coeff = np.polyfit(np.arange(left_lim, right_lim), acf_lp_smooth[left_lim:right_lim], 2)

                    if poly_coeff[0] < 0:
                        left_val = np.polyval(poly_coeff, left_lim)
                        right_val = np.polyval(poly_coeff, right_lim)
                        quad_x_values = np.arange(left_lim, right_lim)
                        quad_y_values = np.polyval(poly_coeff, quad_x_values)
                        max_val = max(quad_y_values)

                        left_ht = max_val - left_val
                        right_ht = max_val - right_val

                        if left_ht > acf_peak_thresh and right_ht > acf_peak_thresh \
                                and left_ht > 0.5 * right_ht and right_ht > 0.5 * left_ht:
                            # find closest peak in the corresponding ACF
                            acf_peak_inds = detect_peaks(acf_lp_smooth)
                            acf_peak_inds = [int(x) for x in acf_peak_inds]
                            acf_valley_inds = detect_peaks(acf_lp_smooth, valley=True)
                            acf_valley_inds = [int(x) for x in acf_valley_inds]

                            closest_peak = find_closest(acf_peak_inds, cur_period)

                            if closest_peak == cur_period:
                                acf_peak_period = cur_period
                            elif closest_peak < cur_period:
                                if any([x in range(closest_peak, cur_period) for x in acf_valley_inds]):
                                    closest_ind = acf_peak_inds.index(closest_peak)
                                    if closest_ind < len(acf_peak_inds) - 1:
                                        acf_peak_period = find_bound(acf_peak_inds[closest_ind:], cur_period,
                                                                     'upper')
                                    else:
                                        acf_peak_period = cur_period
                                else:
                                    acf_peak_period = closest_peak
                            else:
                                if any([x in range(cur_period, closest_peak) for x in acf_valley_inds]):
                                    closest_ind = acf_peak_inds.index(closest_peak)
                                    if closest_ind > 0:
                                        acf_peak_period = find_bound(acf_peak_inds[:closest_ind], cur_period,
                                                                     'lower')
                                    else:
                                        acf_peak_period = cur_period
                                else:
                                    acf_peak_period = closest_peak

                            # Check for more peaks in the ACF, at least a particular fraction of the expected number of
                            # peaks in the noise free case should be present
                            if 2*acf_peak_period > len(acf_lp_smooth):
                                continue

                            # First check whether there are any significant peaks beyond the current peak
                            acf_peak_inds_beyond = [cur_peak_ind for cur_peak_ind in acf_peak_inds
                                                    if cur_peak_ind > acf_peak_period
                                                    and acf_lp_smooth[cur_peak_ind] > acf_peak_thresh]

                            # Now check whether the peaks happen in regular intervals
                            regular_flag = False
                            if len(acf_peak_inds_beyond) > 0:
                                regular_interval_cnt = 0
                                for test_period in range(2*acf_peak_period, len(acf_lp_smooth), acf_peak_period):
                                    valid_peak_inds = [cur_peak_ind for cur_peak_ind in acf_peak_inds
                                                       if 0.9*test_period < cur_peak_ind < 1.1*test_period
                                                       and acf_lp_smooth[cur_peak_ind] > acf_peak_thresh]

                                    if len(valid_peak_inds) > 0:
                                        regular_interval_cnt += 1

                                if regular_interval_cnt > 0.5*(int(len(acf_lp_smooth)/acf_peak_period) - 1):
                                    regular_flag = True

                            if regular_flag and acf_lp_smooth[acf_peak_period] > acf_peak_thresh:
                                acf_peak_periods.append(acf_peak_period)
                                acf_lp_smooth_dict[acf_peak_period] = acf_lp_smooth
                                acf_quadratics[acf_peak_period] = (quad_x_values, quad_y_values)

                                cur_freq_ind = int(num_samp / cur_period)

                                filter_success = False

                                while not filter_success:
                                    try:
                                        # filt_num, filt_den = butter(5, samp_period / (
                                        #                      (num_samp / (cur_freq_ind + 1)) * samp_period - 1))
                                        filt_num, filt_den = butter(4, 1/(((num_samp/(cur_freq_ind + 1)) - 1)*f_nyq))
                                        ip_lp_smooth = filtfilt(filt_num, filt_den, ip_lp_smooth)
                                        acf_lp_smooth = stattools.acf(ip_lp_smooth, nlags=autocorr_lags, fft=True)[1:]
                                        filter_success = True
                                    except Exception as ex:
                                        template = "An exception of type {0} occurred. Arguments:\n{1!r}"
                                        message = template.format(type(ex).__name__, ex.args)
                                        print(message)
                                        cur_freq_ind -= 1

                candidate_freq_inds = []

                for cur_cluster in candidate_clusters:
                    if len(cur_cluster) == 2:
                        candidate_freq_inds.append(cur_cluster[1])

                # print('Candidate frequency indices')
                # print(candidate_freq_inds)

                candidate_periods = []
                for cur_freq_ind in candidate_freq_inds:
                    candidate_period = int(num_samp / cur_freq_ind)
                    if candidate_period < autocorr_statsmodels.size:
                        candidate_periods.append(candidate_period)

                candidate_periods = sorted(set(candidate_periods))

                ip_lp_smooth = np.copy(ip_y_value)
                acf_lp_smooth = np.copy(autocorr_statsmodels)

                acf_diff = []

                for i in range(len(acf_lp_smooth)-1):
                    acf_diff.append(acf_lp_smooth[i+1] - acf_lp_smooth[i])

                acf_abs_diff = [abs(x) for x in acf_diff]

                all_candidate_periods.extend(candidate_periods)
                print("Candidate periods")
                print(candidate_periods)

                for cur_period in candidate_periods:
                    # print("Testing period {}".format(cur_period))
                    left_lim = int(0.5 * cur_period)
                    right_lim = min(int(1.5 * cur_period), acf_lp_smooth.size)

                    poly_coeff = np.polyfit(np.arange(left_lim, right_lim), acf_lp_smooth[left_lim:right_lim], 2)

                    if poly_coeff[0] < 0:
                        left_val = np.polyval(poly_coeff, left_lim)
                        right_val = np.polyval(poly_coeff, right_lim)
                        quad_x_values = np.arange(left_lim, right_lim)
                        quad_y_values = np.polyval(poly_coeff, quad_x_values)
                        max_val = max(quad_y_values)

                        left_ht = max_val - left_val
                        right_ht = max_val - right_val

                        if left_ht > acf_peak_thresh and right_ht > acf_peak_thresh and left_ht > 0.5 * right_ht and right_ht > 0.5 * left_ht:
                            # find closest peak in the corresponding ACF
                            acf_peak_inds = detect_peaks(acf_lp_smooth)
                            acf_peak_inds = [int(x) for x in acf_peak_inds]
                            acf_valley_inds = detect_peaks(acf_lp_smooth, valley=True)
                            acf_valley_inds = [int(x) for x in acf_valley_inds]

                            closest_peak = find_closest(acf_peak_inds, cur_period)

                            if closest_peak == cur_period:
                                acf_peak_period = cur_period
                            elif closest_peak < cur_period:
                                if any([x in range(closest_peak, cur_period) for x in acf_valley_inds]):
                                    closest_ind = acf_peak_inds.index(closest_peak)
                                    acf_peak_period = find_bound(acf_peak_inds[closest_ind:], cur_period, 'upper')
                                else:
                                    acf_peak_period = closest_peak
                            else:
                                if any([x in range(cur_period, closest_peak) for x in acf_valley_inds]):
                                    closest_ind = acf_peak_inds.index(closest_peak)
                                    if closest_ind > 0:  # to deal with a corner case
                                        acf_peak_period = find_bound(acf_peak_inds[:closest_ind], cur_period, 'lower')
                                    else:
                                        acf_peak_period = closest_peak
                                else:
                                    acf_peak_period = closest_peak

                            # Check for more peaks in the ACF, at least a particular fraction of the expected number of peaks
                            # in the noise free case should be present

                            # First check whether there are any significant peaks beyond the current peak
                            acf_peak_inds_beyond = [cur_peak_ind for cur_peak_ind in acf_peak_inds
                                                    if cur_peak_ind > acf_peak_period
                                                    and acf_lp_smooth[cur_peak_ind] > acf_peak_thresh]

                            # Now check whether the peaks happen in regular intervals
                            regular_flag = False
                            if len(acf_peak_inds_beyond) > 0:
                                regular_interval_cnt = 0
                                for test_period in range(2*acf_peak_period, len(acf_lp_smooth), acf_peak_period):
                                    valid_peak_inds = [cur_peak_ind for cur_peak_ind in acf_peak_inds
                                                       if 0.9*test_period < cur_peak_ind < 1.1*test_period
                                                       and acf_lp_smooth[cur_peak_ind] > acf_peak_thresh]

                                    if len(valid_peak_inds) > 0:
                                        regular_interval_cnt += 1

                                if regular_interval_cnt > 0.5*(int(len(acf_lp_smooth)/acf_peak_period) -1):
                                    regular_flag = True

                            if regular_flag and acf_lp_smooth[acf_peak_period] > acf_peak_thresh:
                                acf_peak_periods.append(acf_peak_period)
                                acf_lp_smooth_dict[acf_peak_period] = acf_lp_smooth
                                acf_quadratics[acf_peak_period] = (quad_x_values, quad_y_values)

                                cur_freq_ind = int(num_samp / cur_period)

                                # if (filt_num > 1e-17).all():
                                filter_success = False

                                while not filter_success:
                                    try:
                                        # filt_num, filt_den = butter(5, samp_period / (
                                        #                      (num_samp / (cur_freq_ind + 1)) * samp_period - 1))
                                        filt_num, filt_den = butter(4, 1/(((num_samp/(cur_freq_ind + 1)) - 1)*f_nyq))
                                        ip_lp_smooth = filtfilt(filt_num, filt_den, ip_lp_smooth)
                                        acf_lp_smooth = stattools.acf(ip_lp_smooth, nlags=autocorr_lags, fft=True)[1:]
                                        filter_success = True
                                    except Exception as ex:
                                        template = "An exception of type {0} occurred. Arguments:\n{1!r}"
                                        message = template.format(type(ex).__name__, ex.args)
                                        print(message)
                                        cur_freq_ind -= 1

                print("All candidate periods")
                print(all_candidate_periods)

                print("ACF peak periods")
                print(acf_peak_periods)

                if len(acf_peak_periods) > 1:
                    acf_peak_periods = list(set(acf_peak_periods))

                    acf_peak_periods.sort()

                    acf_peak_periods_merged = []

                    while len(acf_peak_periods) > 0:
                        acf_peak_cluster_center = acf_peak_periods[0]

                        acf_peak_periods.remove(acf_peak_cluster_center)

                        acf_peak_periods_merged.append(acf_peak_cluster_center)

                        val_to_remove = []
                        for x in acf_peak_periods:
                            if 1.1 * acf_peak_cluster_center > x:
                                val_to_remove.append(x)

                        for x in val_to_remove:
                            acf_peak_periods.remove(x)
                            acf_quadratics.pop(x)
                            acf_lp_smooth_dict.pop(x)
                else:
                    acf_peak_periods_merged = list(acf_peak_periods)

                # Enforce an upper limit (half the ACF lag) and lower limit on the time periods
                periods_in_lim = []
                for cur_period in acf_peak_periods_merged:
                    if period_low_lim < cur_period < 0.5*autocorr_lags:
                        periods_in_lim.append(cur_period)

                fig = plt.figure()
                ax = fig.add_subplot(111)
                plt.plot(autocorr_statsmodels)
                for cur_period in all_candidate_periods:
                    plt.plot(cur_period, autocorr_statsmodels[cur_period], 'g*')
                for cur_period in periods_in_lim:
                    plt.plot(cur_period, autocorr_statsmodels[cur_period], 'y^')
                plt.savefig(op_core + '_acf.png')
                plt.close(fig=fig)

                for period_in_lim in periods_in_lim:
                    fig = plt.figure()
                    ax = fig.add_subplot(111)
                    plt.plot(acf_lp_smooth_dict[period_in_lim])
                    plt.plot(period_in_lim, acf_lp_smooth_dict[period_in_lim][period_in_lim], 'y^')
                    cur_quad = acf_quadratics[period_in_lim]
                    plt.plot(cur_quad[0], cur_quad[1], 'm-')
                    plt.title('ACF peak value = {}'.format(acf_lp_smooth_dict[period_in_lim][period_in_lim]))
                    plt.savefig(op_core + '_' + str(period_in_lim) + '.png')
                    plt.close(fig=fig)

                print('ACF peak periods after merging')
                print(acf_peak_periods_merged)
                print('ACF periods within limit')
                print(periods_in_lim)

                op_dict['detected_time_periods'] = periods_in_lim

                date_x_value = matplotlib.dates.date2num(datetime_list)

                fig, axs = plt.subplots(1, 3, figsize=(25.6, 9.6))
                fig.tight_layout()
                axs[0].plot(date_x_value, ip_y_value, linestyle='-', color='blue')
                x_fmt = matplotlib.dates.DateFormatter('%d-%m-%y %H:%M')
                axs[0].xaxis.set_major_formatter(x_fmt)
                # axs[0].xticks(rotation=90)
                for tick in axs[0].get_xticklabels():
                    tick.set_rotation(45)
                axs[0].set_title('The time-series')
                axs[1].plot(f_values_psd, psd_values, linestyle='-', color='blue')
                axs[1].plot(f_values_psd, [psd_thresh for _ in range(len(f_values_psd))], 'r--')
                axs[1].set_title('Power spectral density')
                axs[2].plot(autocorr_statsmodels)
                axs[2].plot(all_candidate_periods, autocorr_statsmodels[all_candidate_periods], 'g*')
                axs[2].plot(periods_in_lim, autocorr_statsmodels[periods_in_lim], 'y^')
                axs[2].set_title('Statsmodels ACF, candidate and validated time periods')
                plt.tight_layout(rect=[0, 0.03, 1, 0.95])
                plt.savefig(op_core + '.png')
                plt.close(fig=fig)

                mp_y_value = np.copy(ori_y_value)
                mp_y_value = mp_y_value.astype(float)

                for period_in_lim in periods_in_lim:
                    win_low_lim = int(0.8*period_in_lim)
                    win_up_lim = int(1.2*period_in_lim)
                    win_step = int(0.05*(win_up_lim - win_low_lim))

                    # pmp_op = stumpy.stimp(T=ip_y_value, min_m=win_low_lim, max_m=win_up_lim, step=win_step, percentage=1.)
                    # pmp_mat = pmp_op.PAN_

                    for win_mp in range(win_low_lim, win_up_lim, win_step):
                        # mp = stumpy.stump(metric_y_value, win_mp)
                        mp = stumpy.stump(mp_y_value, win_mp)

                        mp_list = mp[:, 0].tolist()

                        if win_mp == win_low_lim:
                            pmp_mat_all = [mp_list]
                            min_len = len(mp_list)
                        else:
                            pmp_mat_all.append(mp_list)
                            if len(mp_list) < min_len:
                                min_len = len(mp_list)

                    pmp_mat_crop = []

                    for mp_list in pmp_mat_all:
                        pmp_mat_crop.append(mp_list[:min_len])

                    pmp_mat = np.array(pmp_mat_crop, dtype=np.float)
                    num_pmp_win = pmp_mat.shape[0]
                    pmp_len = pmp_mat.shape[1]
                    max_val = np.max(pmp_mat)
                    min_val = np.min(pmp_mat)
                    row_sum = pmp_mat.sum(axis=1)
                    max_row_sum = np.max(row_sum)
                    min_pmp_ind = np.argmin(row_sum)
                    row_sum = row_sum/max_row_sum
                    row_sum = row_sum*(int(0.1*pmp_len))
                    # pmp_mat[0, :] = max_val

                    fig, ax = plt.subplots()
                    axes = [ax, ax.twinx()]
                    fig.suptitle(f"{csv_filename_core} \n Pan Matrix Profile: Lower limit {win_low_lim}, Upper limit {win_up_lim}.")
                    axes[0].imshow(pmp_mat, aspect='auto', alpha=0.5, extent=[0, pmp_mat.shape[1], win_up_lim, win_low_lim])
                    axes[1].plot(mp_y_value[:min_len])
                    axes[0].plot(row_sum, np.arange(win_low_lim, win_up_lim, win_step), 'r-')
                    if min_pmp_ind == 0:
                        axes[0].axhline(y=win_low_lim+1, color='orange', linestyle='--')
                    else:
                        axes[0].axhline(y=win_low_lim+min_pmp_ind*win_step, color='orange', linestyle='--')
                    axes[0].set_ylabel('Pan Matrix Profile')
                    axes[1].set_ylabel('Time-series value')
                    axes[0].set_xlabel('Time steps (1 minute)')
                    plt.savefig(op_core + '_pmp_ts_' + str(period_in_lim) + '.png', bbox_inches='tight')
                    plt.close()

                    if csv_filename_core in mp_dict:
                        mp_dict[csv_filename_core].append(win_low_lim+min_pmp_ind*win_step)
                    else:
                        mp_dict[csv_filename_core] = [win_low_lim + min_pmp_ind * win_step]

                    # input("Press enter key...")

    op_dict['num_time_candidates'] = len(all_candidate_periods)
    time_taken = time.process_time() - start_time
    op_dict['time_taken'] = time_taken
    op_dict['csv_filename'] = csv_filename
    op_dict['start_datetime'] = datetime.utcfromtimestamp(timestamp_list[0]).strftime('%Y-%m-%d %H:%M:%S')
    op_dict['ts_length'] = ip_y_value.size

    tp_op_all_in_one_dict[csv_filename_core] = op_dict

    with open(op_core + '_results.pickle', 'wb') as pickle_file:
        pickle.dump(op_dict, pickle_file)
