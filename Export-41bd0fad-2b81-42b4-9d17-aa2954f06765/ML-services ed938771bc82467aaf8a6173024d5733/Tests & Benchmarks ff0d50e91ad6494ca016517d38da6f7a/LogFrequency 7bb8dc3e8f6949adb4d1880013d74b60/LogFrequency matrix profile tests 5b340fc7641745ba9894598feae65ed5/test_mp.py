from datetime import datetime, date
from os import walk
import numpy as np
import pandas as pd
from pathlib import Path
import pickle
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import stumpy
import time
import tqdm


def mp_score(df, sliding_window, n_train):
    df_train = df[:n_train]
    df_test = df[n_train:]
    stream = stumpy.stumpi(df_train.value.values.astype(float), sliding_window, egress=False)
    scores = [0]*len(df_train)

    for x in df_test.value:
        stream.update(x)
        score = stream.P_[-1] / stream.P_.max()
        scores.append(score)
    return scores


csv_folder = '/home/hari/data/Affluences_Logfrequency_Data/'
_, _, all_filenames = next(walk(csv_folder + 'input/'))

with open('mp_window_sizes.pickle', 'rb') as mp_pickle_file:
    mp_dict = pickle.load(mp_pickle_file)

n_train = 1440*7

for metric_name, mp_periods in tqdm.tqdm(mp_dict.items()):
    csv_filename = metric_name + '.csv'
    csv_full_path = csv_folder + 'input/' + csv_filename
    op_path = csv_folder + 'output/'
    Path(op_path).mkdir(parents=True, exist_ok=True)
    op_path += metric_name

    op_dict = {}
    df_all_cols = pd.read_csv(csv_full_path)

    df_input = df_all_cols[['timestamp', 'n_message']].copy()

    df_input = df_input.rename(columns={'n_message': 'value'})
    df_input['datetime'] = df_input.apply(lambda x: datetime.strptime(x['timestamp'], '%Y-%m-%d %H:%M:%S'), axis=1)
    df_input.drop('timestamp', 1)
    df_input['timestamp'] = df_input.apply(lambda x: time.mktime(x['datetime'].timetuple()), axis=1)
    df_input.sort_values('timestamp', inplace=True)
    df_input.drop_duplicates(subset='timestamp', inplace=True)
    df_input.set_index('datetime', inplace=True)

    value_list = df_input['value']
    timestamp_list = df_input['timestamp'].to_list()
    datetime_list = df_input.index.to_list()
    ori_y_value = df_input['value'].to_numpy()
    metric_y_value = np.array(ori_y_value)
    metric_y_value = metric_y_value.astype(float)

    num_values = df_input.shape[0]
    if n_train > 0.5*num_values:
        n_train = int(0.3333*num_values)

    n_test = num_values - n_train

    print(f"{metric_name} has period(s):")
    for mp_period in mp_periods:
        mp_period = 1440
        print(f"{mp_period}")
        if mp_period > n_train or mp_period > n_test:
            print(f"{metric_name} has problem with window size {mp_period}")
            continue
        scores = mp_score(df_input, mp_period, n_train)

        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Scatter(x=df_input.index, y=df_input['value'], name="True"), secondary_y=False,)
        fig.add_trace(go.Scatter(x=df_input.index, y=scores, name="MP Score"), secondary_y=True,)
        fig.update_layout(title_text=f"Metric time-series and MP score. MP Window: {mp_period} minutes.")
        fig.update_xaxes(title_text="Time")

        # Set y-axes titles
        fig.update_yaxes(title_text="Metric value", secondary_y=False)
        fig.update_yaxes(title_text="MP score", secondary_y=True)

        fig.write_image(op_path + '_mp_score.png')
        fig.write_html(op_path + '_mp_score.html')
