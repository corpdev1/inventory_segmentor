from bisect import bisect_left
from datetime import datetime
from detecta import detect_peaks
import json
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from os import walk
import numpy as np
from numpy.random import permutation
import pandas as pd
from pathlib import Path
import pickle
from random import random, randint, seed
from scipy.fftpack import fft
from scipy.signal import butter, filtfilt, welch, periodogram, sosfilt
from statsmodels.tsa import stattools
import sys
import time

seed(0)


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

'''
# Based on https://ataspinar.com/2018/04/04/machine-learning-with-signal-processing-techniques/
# It is not dividing by variance. 
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


data_paths = ['/home/hari/data/affluences_s3/6040a96cdcc614001153fc55-linux6040f7e73a9e9f0012cec090/dockerc3fb5b8782cdbf02/']

for data_path in data_paths:
    op_path = data_path.split('/')[-2]

    op_path += '/'

    Path(op_path).mkdir(parents=True, exist_ok=True)

    _, _, time_stamps = next(walk(data_path))

    time_stamps = [int(x) for x in time_stamps]

    time_stamps.sort()

    path = data_path + str(time_stamps[0])
    with open(path, "rb") as f:
        for line in f:
            msg = json.loads(line)
            # print(msg)
            all_keys = [key for key, value in msg.items()]

    exclude_strings = ['timestamp', 'isAnomaly', 'duration_deviation', 'detector_outputs']

    metric_names = []

    for cur_string in all_keys:
        if not any([x in cur_string for x in exclude_strings]):
            metric_names.append(cur_string)

    # metric_names = ['mysql#status#aborted#clients-no_subject']

    # metric_names

    time_taken = []

    op_dict = {}

    for ts_name in metric_names:
        print(ts_name)
        metric_list = []

        for time_stamp in time_stamps:
            path = data_path + str(time_stamp)
            with open(path, "rb") as f:
                for line in f:
                    msg = json.loads(line)
                    # print(msg)
                    cur_metric_list = [value['value'] for key, value in msg.items() if ts_name in key.lower()]
                    if len(cur_metric_list) > 0:
                        metric_list.append(cur_metric_list[0])

        metric_y_value = np.array(metric_list)

        metric_y_value = compute_mwa(metric_y_value, 360)

        # metric_y_value = metric_y_value[60000:140000]

        if np.all(metric_y_value == metric_y_value[0]):
            print('{} is a constant array of value {}.'.format(ts_name, metric_y_value[0]))
        else:
            start_time = time.process_time()

            f_s = 1
            t_n = int(metric_y_value.size/f_s)
            samp_period = 1/f_s
            num_samp = t_n*f_s
            autocorr_lags = num_samp//3
            acf_thresh = 0
            acf_peak_thresh = 0.05

            ori_y_value = metric_y_value[:num_samp]

            ori_y_value = (ori_y_value - ori_y_value.mean())/ori_y_value.std()  # zero mean, unit variance normalization

            ip_y_value = []

            for i in range(ori_y_value.size - 1):
                ip_y_value.append(ori_y_value[i+1] - ori_y_value[i])

            ip_y_value = np.array(ip_y_value)

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
            else:
                reverse_ind = select_ind[::-1]

                if reverse_ind.size == 1 and reverse_ind[0] == 0:
                    print("No periodicity in the given time-series.")
                else:
                    candidate_clusters = [[reverse_ind[0]]]

                    if reverse_ind.size > 1:
                        next_thresh = num_samp/(candidate_clusters[0][0] - 1) + 1
                        cur_cluster = 0

                        for cur_ind in reverse_ind[1:]:
                            if cur_ind == 0:
                                if 1 in candidate_clusters[cur_cluster]:
                                    candidate_clusters[cur_cluster].append(cur_ind)
                            else:
                                if num_samp/cur_ind < next_thresh and len(candidate_clusters[cur_cluster]) == 1:
                                    candidate_clusters[cur_cluster].append(cur_ind)
                                else:
                                    candidate_clusters.append([cur_ind])
                                    cur_cluster += 1

                                if cur_ind > 1:
                                    next_thresh = num_samp/(cur_ind - 1) + 1

                    candidate_freq_inds = []

                    # print('Candidate frequency clusters')
                    # print(candidate_clusters)

                    for cur_cluster in candidate_clusters:
                        candidate_freq_inds.append(cur_cluster[0])

                    # print('Candidate frequency indices')
                    # print(candidate_freq_inds)

                    candidate_periods = []
                    for cur_freq_ind in candidate_freq_inds:
                        candidate_period = int(num_samp/cur_freq_ind)
                        if candidate_period < autocorr_statsmodels.size:
                            candidate_periods.append(candidate_period)

                    ip_lp_filter = np.copy(ip_y_value)
                    acf_lp_filter = np.copy(autocorr_statsmodels)

                    acf_peak_periods = []
                    acf_quadratics = {}
                    acf_lp_filter_dict = {}

                    all_candidate_periods = candidate_periods
                    print("Candidate periods")
                    print(candidate_periods)

                    for cur_period in candidate_periods:
                        # print("Testing period {}".format(cur_period))
                        left_lim = int(0.5*cur_period)
                        right_lim = min(int(1.5*cur_period), acf_lp_filter.size)

                        poly_coeff = np.polyfit(np.arange(left_lim, right_lim), acf_lp_filter[left_lim:right_lim], 2)

                        if poly_coeff[0] < 0:
                            left_val = np.polyval(poly_coeff, left_lim)
                            right_val = np.polyval(poly_coeff, right_lim)
                            quad_x_values = np.arange(left_lim, right_lim)
                            quad_y_values = np.polyval(poly_coeff, quad_x_values)
                            max_val = max(quad_y_values)

                            left_ht = max_val - left_val
                            right_ht = max_val - right_val

                            if left_ht > acf_peak_thresh and right_ht > acf_peak_thresh and left_ht > 0.5*right_ht and right_ht > 0.5*left_ht:
                                # find closest peak in the corresponding ACF
                                acf_peak_ind = detect_peaks(acf_lp_filter)
                                acf_peak_ind = [int(x) for x in acf_peak_ind]
                                acf_valley_ind = detect_peaks(acf_lp_filter, valley=True)
                                acf_valley_ind = [int(x) for x in acf_valley_ind]

                                closest_peak = find_closest(acf_peak_ind, cur_period)

                                if closest_peak == cur_period:
                                    acf_peak_period = cur_period
                                elif closest_peak < cur_period:
                                    if any([x in range(closest_peak, cur_period) for x in acf_valley_ind]):
                                        closest_ind = acf_peak_ind.index(closest_peak)
                                        if closest_ind < len(acf_peak_ind) - 1:
                                            acf_peak_period = find_bound(acf_peak_ind[closest_ind:], cur_period, 'upper')
                                        else:
                                            acf_peak_period = cur_period
                                    else:
                                        acf_peak_period = closest_peak
                                else:
                                    if any([x in range(cur_period, closest_peak) for x in acf_valley_ind]):
                                        closest_ind = acf_peak_ind.index(closest_peak)
                                        if closest_ind > 0:
                                            acf_peak_period = find_bound(acf_peak_ind[:closest_ind], cur_period, 'lower')
                                        else:
                                            acf_peak_period = cur_period
                                    else:
                                        acf_peak_period = closest_peak

                                if acf_lp_filter[acf_peak_period] > acf_peak_thresh:
                                    acf_peak_periods.append(acf_peak_period)
                                    acf_lp_filter_dict[acf_peak_period] = acf_lp_filter
                                    acf_quadratics[acf_peak_period] = (quad_x_values, quad_y_values)

                                    cur_freq_ind = int(num_samp/cur_period)

                                    filter_success = False

                                    while not filter_success:
                                        try:
                                            filt_num, filt_den = butter(5, samp_period / (
                                                        (num_samp / (cur_freq_ind + 1)) * samp_period - 1))
                                            ip_lp_filter = filtfilt(filt_num, filt_den, ip_lp_filter)
                                            acf_lp_filter = stattools.acf(ip_lp_filter, nlags=autocorr_lags)[1:]
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
                        candidate_period = int(num_samp/cur_freq_ind)
                        if candidate_period < autocorr_statsmodels.size:
                            candidate_periods.append(candidate_period)

                    ip_lp_filter = np.copy(ip_y_value)
                    acf_lp_filter = np.copy(autocorr_statsmodels)

                    all_candidate_periods.extend(candidate_periods)
                    print("Candidate periods")
                    print(candidate_periods)

                    for cur_period in candidate_periods:
                        # print("Testing period {}".format(cur_period))
                        left_lim = int(0.5*cur_period)
                        right_lim = min(int(1.5*cur_period), acf_lp_filter.size)

                        poly_coeff = np.polyfit(np.arange(left_lim, right_lim), acf_lp_filter[left_lim:right_lim], 2)

                        if poly_coeff[0] < 0:
                            left_val = np.polyval(poly_coeff, left_lim)
                            right_val = np.polyval(poly_coeff, right_lim)
                            quad_x_values = np.arange(left_lim, right_lim)
                            quad_y_values = np.polyval(poly_coeff, quad_x_values)
                            max_val = max(quad_y_values)

                            left_ht = max_val - left_val
                            right_ht = max_val - right_val

                            if left_ht > acf_peak_thresh and right_ht > acf_peak_thresh and left_ht > 0.5*right_ht and right_ht > 0.5*left_ht:
                                # find closest peak in the corresponding ACF
                                acf_peak_ind = detect_peaks(acf_lp_filter)
                                acf_peak_ind = [int(x) for x in acf_peak_ind]
                                acf_valley_ind = detect_peaks(acf_lp_filter, valley=True)
                                acf_valley_ind = [int(x) for x in acf_valley_ind]

                                closest_peak = find_closest(acf_peak_ind, cur_period)

                                if closest_peak == cur_period:
                                    acf_peak_period = cur_period
                                elif closest_peak < cur_period:
                                    if any([x in range(closest_peak, cur_period) for x in acf_valley_ind]):
                                        closest_ind = acf_peak_ind.index(closest_peak)
                                        acf_peak_period = find_bound(acf_peak_ind[closest_ind:], cur_period, 'upper')
                                    else:
                                        acf_peak_period = closest_peak
                                else:
                                    if any([x in range(cur_period, closest_peak) for x in acf_valley_ind]):
                                        closest_ind = acf_peak_ind.index(closest_peak)
                                        acf_peak_period = find_bound(acf_peak_ind[:closest_ind], cur_period, 'lower')
                                    else:
                                        acf_peak_period = closest_peak

                                if acf_lp_filter[acf_peak_period] > acf_peak_thresh:
                                    acf_peak_periods.append(acf_peak_period)
                                    acf_lp_filter_dict[acf_peak_period] = acf_lp_filter
                                    acf_quadratics[acf_peak_period] = (quad_x_values, quad_y_values)

                                    cur_freq_ind = int(num_samp/cur_period)

                                    # if (filt_num > 1e-17).all():
                                    filter_success = False

                                    while not filter_success:
                                        try:
                                            filt_num, filt_den = butter(5, samp_period / (
                                                        (num_samp / (cur_freq_ind + 1)) * samp_period - 1))
                                            ip_lp_filter = filtfilt(filt_num, filt_den, ip_lp_filter)
                                            acf_lp_filter = stattools.acf(ip_lp_filter, nlags=autocorr_lags)[1:]
                                            filter_success = True
                                        except Exception as ex:
                                            template = "An exception of type {0} occurred. Arguments:\n{1!r}"
                                            message = template.format(type(ex).__name__, ex.args)
                                            print(message)
                                            cur_freq_ind -= 1

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
                        if 1.1*acf_peak_cluster_center > x:
                            val_to_remove.append(x)

                    for x in val_to_remove:
                        acf_peak_periods.remove(x)
                        acf_quadratics.pop(x)
                        acf_lp_filter_dict.pop(x)
            else:
                acf_peak_periods_merged = list(acf_peak_periods)

            time_taken.append(time.process_time() - start_time)

            fig = plt.figure()
            ax = fig.add_subplot(111)
            plt.plot(autocorr_statsmodels)
            for cur_period in all_candidate_periods:
                plt.plot(cur_period, autocorr_statsmodels[cur_period], 'g*')
            for cur_period in acf_peak_periods_merged:
                plt.plot(cur_period, autocorr_statsmodels[cur_period], 'y^')
            plt.savefig(op_path + ts_name + '_acf.png')
            plt.close(fig=fig)

            for acf_peak_period_merged in acf_peak_periods_merged:
                fig = plt.figure()
                ax = fig.add_subplot(111)
                plt.plot(acf_lp_filter_dict[acf_peak_period_merged])
                plt.plot(acf_peak_period_merged, acf_lp_filter_dict[acf_peak_period_merged][acf_peak_period_merged], 'y^')
                plt.title('ACF peak value = {}'.format(acf_lp_filter_dict[acf_peak_period_merged][acf_peak_period_merged]))
                plt.savefig(op_path + ts_name + '_' + str(acf_peak_period_merged) + '.png')
                plt.close(fig=fig)

            print('ACF peak periods after merging')
            print(acf_peak_periods_merged)

            op_dict[ts_name] = acf_peak_periods_merged

            fig, axs = plt.subplots(1, 3, figsize=(25.6, 9.6))
            fig.tight_layout()
            axs[0].plot(np.arange(num_samp), ip_y_value, linestyle='-', color='blue')
            axs[0].set_title('The time-series')
            axs[1].plot(f_values_psd, psd_values, linestyle='-', color='blue')
            axs[1].plot(f_values_psd, [psd_thresh for _ in range(len(f_values_psd))], 'r--')
            axs[1].set_title('Power spectral density')
            axs[2].plot(autocorr_statsmodels)
            axs[2].plot(all_candidate_periods, autocorr_statsmodels[all_candidate_periods], 'g*')
            axs[2].plot(acf_peak_periods_merged, autocorr_statsmodels[acf_peak_periods_merged], 'y^')
            for acf_peak_period, cur_quad in acf_quadratics.items():
                axs[2].plot(cur_quad[0], cur_quad[1], 'm-')
            axs[2].set_title('Statsmodels ACF, candidate and validated time periods')
            plt.savefig(op_path + ts_name + '.png')
            plt.close(fig=fig)

    op_dict['num_time_candidates'] = len(all_candidate_periods)
    op_dict['min_time'] = min(time_taken)
    op_dict['max_time'] = max(time_taken)
    op_dict['avg_time'] = sum(time_taken)/len(time_taken)
    op_dict['data_path'] = data_path
    op_dict['start_datetime'] = datetime.utcfromtimestamp(time_stamps[0]).strftime('%Y-%m-%d %H:%M:%S')
    op_dict['ts_length'] = ip_y_value.size

    with open(op_path + 'results.pickle', 'wb') as pickle_file:
        pickle.dump(op_dict, pickle_file)

    time.sleep(1)