from datetime import datetime
import json
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from os import walk
import pandas as pd
from pathlib import Path

import cvxopt
import cvxpy
import scipy

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


'''
d1 = datetime.datetime(2011, 1, 1)
d2 = datetime.datetime(2012, 12, 1)
df_yahoo = pd.read_csv('/home/hari/softwares/mplfinance/examples/data/yahoofinance-AAPL-20040819-20180120.csv')
df_yahoo['Date'] = pd.to_datetime(df_yahoo['Date'])
datetime_mask = (df_yahoo['Date'] >= d1) & (df_yahoo['Date'] < d2)
y = df_yahoo['High'].loc[datetime_mask].to_numpy()
'''

company_name = 'affluences'

data_paths = ['/home/hari/data/' + company_name + '_s3/6040a96cdcc614001153fc55-linux6040f7e73a9e9f0012cec090/dockerc3fb5b8782cdbf02/']

for data_path in data_paths:
    op_path = data_path.split('/')[-2]

    op_path += '/' + 'worker_1/'

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

    # metric_names = ['docker#network#in#packets-no_subject']

    for ts_name in metric_names:
        print(ts_name)
        metric_list = []
        timestamp_list = []

        for time_stamp in time_stamps:
            path = data_path + str(time_stamp)
            with open(path, 'rb') as f:
                for line in f:
                    msg = json.loads(line)
                    cur_timestamp = int(msg['timestamp'])
                    # print(msg)
                    cur_metric_list = [value['value'] for key, value in msg.items() if ts_name in key.lower()]
                    if len(cur_metric_list) > 0:
                        metric_list.append(cur_metric_list[0])
                        timestamp_list.append(cur_timestamp)

        df_metric = pd.DataFrame(list(zip(timestamp_list, metric_list)), columns=['timestamp', 'value'])
        df_metric.sort_values('timestamp', inplace=True)
        df_metric.drop_duplicates(subset='timestamp', inplace=True)
        df_metric.index = df_metric.apply(lambda x: datetime.fromtimestamp(x['timestamp']/1000), axis=1)
        df_metric = df_metric.asfreq('10S').fillna(method='ffill')

        date_list = df_metric.index.to_list()
        date_x_value = matplotlib.dates.date2num(date_list)
        x_fmt = matplotlib.dates.DateFormatter('%d-%m-%y %H:%M')
        y = df_metric['value'].to_numpy()

        y = compute_mwa(y, 360)
        y = y[:360]
        date_x_value = date_x_value[360:720]

        y = (y - y.mean())/y.std()
        # zero mean, unit variance normalization

        n = y.size
        ones_row = np.ones((1, n))
        D = scipy.sparse.spdiags(np.vstack((ones_row, -2*ones_row, ones_row)), range(3), n-2, n)

        lambda_list = [0, 0.1, 0.5, 1, 2, 5, 10, 50, 200, 500, 1000, 2000, 5000, 10000, 100000]

        # H-P trend filtering
        solver = cvxpy.CVXOPT
        reg_norm = 2

        # L1 trend filtering
        # solver = cvxpy.ECOS
        # reg_norm = 1

        fig, ax = plt.subplots(len(lambda_list) // 3, 3, figsize=(20, 20))
        ax = ax.ravel()
        ii = 0
        problem_lambdas = []
        for lambda_value in lambda_list:
            x = cvxpy.Variable(shape=n)
            # x is the filtered trend that we initialize
            objective = cvxpy.Minimize(0.5 * cvxpy.sum_squares(y - x)
                                       + lambda_value * cvxpy.norm(D @ x, reg_norm))
            # Note: D@x is syntax for matrix multiplication
            problem = cvxpy.Problem(objective)
            try:
                problem.solve(solver=solver, verbose=True)
            except:
                problem_lambdas.append(lambda_value)
                continue
            ax[ii].plot(date_x_value, y, '-', linewidth=1.0, c='b')
            ax[ii].plot(date_x_value, np.array(x.value), '-', linewidth=1.0, c='r')
            ax[ii].xaxis.set_major_formatter(x_fmt)
            for tick in ax[ii].get_xticklabels():
                tick.set_rotation(45)
            ax[ii].set_xlabel('Time')
            ax[ii].set_ylabel('Metric value')
            ax[ii].set_title('Lambda: {}\nSolver: {}\nObjective Value: {}'.format(lambda_value, problem.status,
                                                                                  round(objective.value, 3)))
            ii += 1

            plt.tight_layout()
            plt.savefig(op_path + ts_name + '.png')
            # plt.show()

        for problem_lambda in problem_lambdas:
            print("Optimization didn't converge: Metric name: {}, time-series length = {}, lambda = {}.".format(ts_name, n, problem_lambda))