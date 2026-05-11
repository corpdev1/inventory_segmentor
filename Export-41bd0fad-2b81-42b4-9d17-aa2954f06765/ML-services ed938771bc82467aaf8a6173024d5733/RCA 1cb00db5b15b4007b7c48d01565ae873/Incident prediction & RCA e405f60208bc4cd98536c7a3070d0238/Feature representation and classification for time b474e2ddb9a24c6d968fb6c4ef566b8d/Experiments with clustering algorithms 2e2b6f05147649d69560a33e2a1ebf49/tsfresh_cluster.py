import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pathlib import Path
from tsfresh import extract_features
from tslearn.clustering import KShape
import sklearn.cluster as cluster
import statistics

ts_data = np.loadtxt(open('../data/Affluences/affluences_raw_data_10s_resample.csv', 'rb'), delimiter=',')

ts_data = ts_data[:, 1:]

ts_names = [line.rstrip() for line in open('../data/Affluences/affluences_raw_names_10s_resample.txt')]

value_name = 'value'

n_clusters = 6

init_type = 'k-means++'
random_seed = 0

op_root_path = init_type + '_' + str(n_clusters) + 'clusters'

num_ts, ts_len = ts_data.shape

norm_ts_data = np.zeros_like(ts_data)

for ts_ind in range(num_ts):
    row_avg = np.mean(ts_data[ts_ind, :])
    row_std = np.std(ts_data[ts_ind, :])
    if row_std > -1:
        for elem_ind in range(ts_len):
            norm_value = (ts_data[ts_ind, elem_ind] - row_avg)/row_std
            norm_ts_data[ts_ind, elem_ind] = norm_value

# Using TS Fresh features
value_list = []
id_list = []
time_list = []

diff_value_list = []
diff_id_list = []
diff_time_list = []

for ts_ind in range(num_ts):
    for elem_ind in range(ts_len):
        value_list.append(norm_ts_data[ts_ind, elem_ind])
        id_list.append(ts_ind)
        time_list.append(elem_ind)
        if elem_ind > 0:
            diff_value_list.append(norm_ts_data[ts_ind, elem_ind]-norm_ts_data[ts_ind, elem_ind-1])
            diff_id_list.append(ts_ind)
            diff_time_list.append(elem_ind-1)

ts_df = pd.DataFrame({'id': id_list, 'time': time_list, value_name: value_list}, columns=['id', 'time', value_name])

ts_features = extract_features(ts_df, column_id='id', column_sort='time')

ts_features.shape

computed_feature_names = list(ts_features.columns)

diff_ts_df = pd.DataFrame({'id': diff_id_list, 'time': diff_time_list, value_name: diff_value_list}, columns=['id', 'time', value_name])

diff_ts_features = extract_features(diff_ts_df, column_id='id', column_sort='time')

fft_feature_subname = 'fft_coefficient__attr_"abs"__coeff_'

other_feature_names = ['mean', 'standard_deviation', 'skewness', 'kurtosis']

all_fft_feature_names = [x for x in computed_feature_names if fft_feature_subname in x]

all_fft_feature_values = ts_features[all_fft_feature_names]

energy_values = [0 for _ in range(num_ts)]
periodicity_values = []

for ts_ind, fft_values in all_fft_feature_values.iterrows():
    max_fft_value = 0
    for col_name, fft_value in fft_values.items():
        energy_values[ts_ind] += fft_value**2

        if fft_feature_subname + '0' not in col_name and fft_value > max_fft_value:
            max_col_name = col_name
            max_fft_value = fft_value

    periodicity_values.append(int(max_col_name.split('_')[-1]))

    energy_values[ts_ind] /= ts_len

# all_feature_values = [periodicity_values, energy_values]
all_feature_values = []

for feature_name in other_feature_names:
    all_feature_values.append(ts_features[value_name + '__' + feature_name].tolist())
    all_feature_values.append(diff_ts_features[value_name + '__' + feature_name].tolist())

all_norm_feature_values = []

for value_list in all_feature_values:
    list_mean = statistics.mean(value_list)
    list_std = statistics.stdev(value_list)

    norm_value_list = [(x-list_std)/list_std for x in value_list]

    all_norm_feature_values.append(norm_value_list)

features_to_cluster = np.array(all_norm_feature_values)

features_to_cluster = features_to_cluster.transpose()

if init_type == 'k-means++':
    kmeans = cluster.KMeans(n_clusters=n_clusters, init=init_type).fit(features_to_cluster)
elif init_type == 'random':
    kmeans = cluster.KMeans(n_clusters=n_clusters, random_state=random_seed).fit(features_to_cluster)
    op_root_path += '_' + str(random_seed)

op_labels = kmeans.labels_

# kshape approach
# op_labels = KShape(n_clusters=n_clusters, n_init=1, random_state=0).fit_predict(norm_ts_data)

ts_groups = {}
ts_cnt = 0

for i_label in op_labels:
    if i_label in ts_groups:
        ts_groups[i_label].append(ts_cnt)
    else:
        ts_groups[i_label] = [ts_cnt]
    ts_cnt += 1

for cluster_ind, ts_ind_list in ts_groups.items():
    op_path = op_root_path + '/' + str(cluster_ind) + '/'
    Path(op_path).mkdir(parents=True, exist_ok=True)

    for ts_ind in ts_ind_list:
        ts_name = ts_names[ts_ind]
        plt_value_list = []
        for elem_ind in range(ts_len):
            plt_value_list.append(norm_ts_data[ts_ind, elem_ind])
        fig = plt.figure()
        ax = fig.add_subplot(111)
        fig.autofmt_xdate()
        plt.plot(plt_value_list)
        # x_fmt = matplotlib.dates.DateFormatter('%d-%m-%y %H:%M')
        # ax.xaxis.set_major_formatter(x_fmt)
        # plt.xticks(rotation=90)
        plt.tight_layout(rect=[0, 0.03, 1, 0.95])
        plt.title(ts_name)
        plt.savefig(op_path + ts_name + '.png')
        plt.close(fig=fig)
