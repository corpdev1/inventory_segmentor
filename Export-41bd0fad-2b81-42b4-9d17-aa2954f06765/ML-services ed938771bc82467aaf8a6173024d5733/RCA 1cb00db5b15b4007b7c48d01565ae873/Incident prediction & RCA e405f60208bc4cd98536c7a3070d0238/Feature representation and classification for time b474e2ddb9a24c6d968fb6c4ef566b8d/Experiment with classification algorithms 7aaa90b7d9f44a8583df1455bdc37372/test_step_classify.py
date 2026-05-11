from datetime import datetime
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from random import randint
from random import random
from random import seed
from sklearn.linear_model import RidgeClassifierCV
from sktime.transformations.panel.rocket import Rocket
import time

seed(datetime.now())

num_class = 3

sparse_data = []
periodic_data = []
step_data = []
# noisy_step_data = []

ts_len = 300
num_samples = 100

# sparse model
noise_range = 0.5
sparse_low = 4
sparse_high = 10
sparse_prob = [0.01, 0.05]  # data with different percentage of sparsity

# periodic data
signal_period = [5, 13, 29]  # data with different time periods
signal_range_amp = 5
signal_min_amp = 1

# step data
step_prob = [0.1]  # data with different frequencies in step occurence
step_range = 10

train_test_ratio = 0.5

train_period_ind = []
test_period_ind = []

for ind_sample in range(num_samples):
    indices_ts = np.arange(0, ts_len)

    # sparse data
    cur_sample = [sparse_low + random()*(sparse_high - sparse_low) if random() < sparse_prob[0] else random()*noise_range \
                  for _ in range(ts_len)]

    sparse_data.append(cur_sample)

    # periodic data
    period_samp = randint(0, len(signal_period)-1)
    cur_sample = (signal_min_amp + random()*signal_range_amp)*np.sin((2 * np.pi / signal_period[period_samp]) * indices_ts + random()*np.pi)

    periodic_data.append(cur_sample)

    cur_sample = []

    # step_data
    for cur_ind in range(ts_len):
        if random() < step_prob[0]:
            cur_sample.append(randint(0, step_range))
        else:
            if not cur_sample:
                cur_sample.append(randint(0, step_range))
            else:
                cur_sample.append(cur_sample[-1])

    step_data.append(cur_sample)

train_ind = []
test_ind = []

for cur_ind in range(num_samples):
    if random() < train_test_ratio:
        train_ind.append(cur_ind)
    else:
        test_ind.append(cur_ind)

ts_ip = []
y_ip = []

for cur_ind in range(num_samples):
    ts_ip.append(sparse_data[cur_ind])
    y_ip.append(0)
    ts_ip.append(periodic_data[cur_ind])
    y_ip.append(1)
    ts_ip.append(step_data[cur_ind])
    y_ip.append(2)

y_op = []

for cur_y, cur_ts in zip(y_ip, ts_ip):
    hist_ts = np.histogram(cur_ts)  # default 10 bins
    hist_bin_sizes = hist_ts[0]
    hist_bin_edges = hist_ts[1]
    bottom_30_size = hist_bin_sizes[0] + hist_bin_sizes[1] + hist_bin_sizes[2]

    if bottom_30_size < 0.8*len(cur_ts):  # not sparse
        diff_ts = []
        for cur_ind in range(len(cur_ts) - 1):
            diff_ts.append(abs(cur_ts[cur_ind + 1] - cur_ts[cur_ind]))
        hist_diff = np.histogram(diff_ts)  # default 10 bins
        hist_bin_sizes = hist_diff[0]
        hist_bin_edges = hist_ts[1]
        bottom_30_size = hist_bin_sizes[0] + hist_bin_sizes[1] + hist_bin_sizes[2]

        if bottom_30_size > 0.8*len(diff_ts):
            y_op.append(0)  # sparse difference -> original step
        else:
            y_op.append(1)
    else:
        y_op.append(1)  # sparse

misclass_cases = {}

for index, (cur_ip, cur_op) in enumerate(zip(y_ip, y_op)):
    if (cur_ip == 2 and cur_op != 0) or (cur_ip != 2 and cur_op == 0):
        if cur_ip in misclass_cases:
            misclass_cases[cur_ip].append(index)
        else:
            misclass_cases[cur_ip] = [index]

for i_class in range(3):
    if i_class not in misclass_cases:
        misclass_cases[i_class] = []
    else:
        print("Class {} misclassified {} times.".format(i_class, len(misclass_cases[i_class])))

fig = plt.figure()
ax = fig.add_subplot(111)

for cur_sample in range(num_samples):
    plt.plot(sparse_data[cur_sample])

plt.show()

fig = plt.figure()
ax = fig.add_subplot(111)

for cur_sample in range(num_samples):
    plt.plot(periodic_data[cur_sample])

plt.show()

fig = plt.figure()
ax = fig.add_subplot(111)

for cur_sample in range(num_samples):
    plt.plot(step_data[cur_sample])

plt.show()

time.sleep(1)