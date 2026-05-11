from datetime import datetime
import json
import numpy as np
from os import walk
import pickle
from random import seed
import time


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


seed(datetime.now())

data_path = '/home/hari/data/gmu_s3/602f799fad3c6f00114c1fb4-linux602f88cdad3c6f00114c1fc5/mysql8f8fd6c89154d836/'

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


op_dict = {}

sparse_cnt = 0
nonsparse_cnt = 0

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

    metric_y_value = np.abs(metric_y_value)

    metric_y_value = metric_y_value[60000:140000]

    hist_ts = np.histogram(metric_y_value)  # default 10 bins
    hist_bin_sizes = hist_ts[0]
    hist_bin_edges = hist_ts[1]
    bottom_30_size = hist_bin_sizes[0] + hist_bin_sizes[1] + hist_bin_sizes[2]

    if bottom_30_size > 0.8*len(metric_y_value):
        op_dict[ts_name] = True
        sparse_cnt += 1
    else:
        op_dict[ts_name] = False
        nonsparse_cnt += 1

with open('sparse_test' + data_path.replace('/', '_') + '.pickle', 'wb') as pickle_file:
    pickle.dump(op_dict, pickle_file)

print("Number of sparse cases {}, non-sparse cases {}.".format(sparse_cnt, nonsparse_cnt))

time.sleep(1)