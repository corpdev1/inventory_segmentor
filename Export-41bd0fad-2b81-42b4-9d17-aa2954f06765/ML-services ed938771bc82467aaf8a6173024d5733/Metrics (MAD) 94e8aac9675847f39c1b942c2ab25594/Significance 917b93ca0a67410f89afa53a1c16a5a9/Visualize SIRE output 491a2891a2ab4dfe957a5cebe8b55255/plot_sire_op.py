import ast
import calendar
from datetime import datetime
import json
import jsonlines
import kafka
from kafka.admin import KafkaAdminClient, NewTopic
import os
import sys
ABS_PATH = os.path.dirname(os.path.dirname(os.path.abspath(sys.argv[0])))
if ABS_PATH not in sys.path:
    sys.path.append(ABS_PATH)
from kafka import KafkaConsumer, KafkaProducer, TopicPartition, OffsetAndMetadata
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import pandas as pd
from pathlib import Path
import pickle
import random
import time
from time import sleep
import tqdm

import plotly.graph_objs as go
from plotly.subplots import make_subplots
import numpy as np

def plot_sire_data(sire_dict, pickle_file):
    print("Plot SIRE data")

    print('PICKLE FILE {}'.format(pickle_file))
    comp_name = pickle_file.split('.')[-2]
    comp_name = comp_name.split('/')[-1]

    # Path(op_path).mkdir(parents=True, exist_ok=True)
    with open(pickle_file, 'rb') as pickle_data:
        metric_dict = pickle.load(pickle_data)

    for ts_name, data_tuple in metric_dict.items():
        print(ts_name)
        if ts_name in sire_dict:
            Path(comp_name).mkdir(parents=True, exist_ok=True)

            all_value_list, all_timestamp_list, all_anom_labels_list = data_tuple

            sire_list = sire_dict[ts_name]

            sire_timestamp_list = []

            for cur_incident in sire_list:
                sire_timestamp_list.append(cur_incident[0]/1000)
                sire_timestamp_list.append(cur_incident[1]/1000)
                sire_timestamp_list.append(cur_incident[2]/1000)

            start_timestamp = min(sire_timestamp_list) - 86400
            end_timestamp = max(sire_timestamp_list) + 86400

            pick_value_list = []
            pick_timestamp_list = []
            pick_anom_labels_list = []
            i_cnt = 0

            for i_timestamp in all_timestamp_list:
                if start_timestamp < i_timestamp/1000 < end_timestamp:
                    pick_value_list.append(all_value_list[i_cnt])
                    pick_timestamp_list.append(all_timestamp_list[i_cnt])
                    pick_anom_labels_list.append(all_anom_labels_list[i_cnt])
                i_cnt += 1

            if len(pick_value_list) > 0:
                pick_datetime_list = [datetime.utcfromtimestamp(x/1000) for x in pick_timestamp_list]

                max_val = max([abs(x) for x in pick_value_list])

                df_plot = pd.DataFrame(list(zip(pick_timestamp_list, pick_datetime_list, pick_value_list, pick_anom_labels_list)),
                                       columns=['timestamp', 'datetime', 'value', 'isAnomaly'])
                df_plot.sort_values('timestamp', inplace=True)

                '''
                x_fmt = matplotlib.dates.DateFormatter('%d-%m-%y %H:%M')
                date_x_value = matplotlib.dates.date2num(pick_datetime_list)
                fig = plt.figure()
                ax = fig.add_subplot(111)
                # fig.autofmt_xdate()
                # plt.plot(pick_value_list, 'r-')
                plt.plot(date_x_value, pick_value_list, 'r-')

                for cur_incident in sire_list:
                    incident_start_ts = cur_incident[1]/1000
                    incident_end_ts = cur_incident[2]/1000
                    incident_score = cur_incident[3]

                    if start_timestamp < incident_start_ts < end_timestamp:
                        incident_start_dt = datetime.utcfromtimestamp(incident_start_ts)
                        incident_end_dt = datetime.utcfromtimestamp(incident_end_ts)
                        incident_start_dt2num = matplotlib.dates.date2num(incident_start_dt)
                        incident_end_dt2num = matplotlib.dates.date2num(incident_end_dt)
                        ax.add_patch(Rectangle((incident_start_dt2num, 0), incident_end_dt2num-incident_start_dt2num, incident_score*max_val))

                plt.plot()
                # plt.plot(date_x_value, metric_y_value[zscore_win:], 'g-')
                # plt.plot_date(date_x_value, ip_y_value, fmt='-')
                ax.xaxis.set_major_formatter(x_fmt)
                plt.xticks(rotation=90)
                plt.tight_layout(rect=[0, 0.03, 1, 0.95])
                # plt.plot(ip_y_value)
                plt.title(comp_name + '#' + ts_name)
                plt.savefig(comp_name + '#' + ts_name + '.png')
                plt.close(fig=fig)
                '''
                incident_start_ts_list = []
                incident_end_ts_list = []
                incident_start_dt_list = []
                incident_end_dt_list = []
                incident_score_list = []
                incident_y_list = []

                # trace for metric values
                trace1 = go.Scatter(
                    x=df_plot["datetime"],
                    y=df_plot["value"],
                    mode="lines+markers",
                    name="metric value",
                    text=[f"timestamp: {timestamp}" for timestamp in df_plot.timestamp.tolist()],
                    marker=dict(size=1),
                )

                traces = [trace1]

                yellow_color = "rgba(250, 250, 0, 0.75)"
                orange_color = "rgba(250, 160, 0, 0.75)"
                red_color = "rgba(250, 0, 0, 0.75)"

                incident_cnt = 0

                for cur_incident in sire_list:
                    incident_start_ts = cur_incident[1]/1000
                    incident_end_ts = cur_incident[2]/1000
                    incident_score = cur_incident[3]

                    if start_timestamp < incident_start_ts < end_timestamp:
                        incident_start_dt = datetime.utcfromtimestamp(incident_start_ts)
                        incident_end_dt = datetime.utcfromtimestamp(incident_end_ts)

                        if incident_score < 0.8:
                            fill_color = yellow_color
                        elif incident_score < 0.9:
                            fill_color = orange_color
                        else:
                            fill_color = red_color

                        display_txt = f"start: {incident_start_ts} end: {incident_end_ts} score: {incident_score}"

                        cur_trace = go.Scatter(
                            x=[incident_start_dt, incident_start_dt, incident_end_dt, incident_end_dt],
                            y=[0, max_val, max_val, 0],
                            mode="lines",
                            name=f"incident {incident_cnt}",
                            text=display_txt,
                            fill="tozeroy",
                            fillcolor=fill_color,
                            line_color=fill_color,
                        )

                        traces.append(cur_trace)

                        incident_cnt += 1
                '''
                trace2 = go.Scatter(
                    x=incident_start_dt_list,
                    y=incident_y_list,
                    mode="markers",
                    marker_symbol="square",
                    name="incident start",
                    text=start_display_list,
                    marker=dict(size=10, color="rgba(250, 0, 0, 0.8)"),
                )
                # trace for incident end
                trace3 = go.Scatter(
                    x=incident_end_dt_list,
                    y=incident_y_list,
                    mode="markers",
                    marker_symbol="cross",
                    name="incident end",
                    text=end_display_list,
                    marker=dict(size=10, color="rgba(0, 0, 0, 0.8)"),
                )
                '''
                # traces = [trace1, trace2]
                # traces = [trace1, trace2, trace3]

                fig = make_subplots(
                    rows=1,
                    cols=1,
                    shared_xaxes=True,
                    vertical_spacing=0.05,
                    specs=[
                        [{"type": "scatter"}],
                    ],
                    row_heights=[1.0],
                )
                for trace in traces:
                    fig.add_trace(trace, row=1, col=1)

                fig.update_layout(
                    autosize=True,
                    height=1000,
                    title=comp_name + '#' + ts_name,
                    clickmode="event+select",
                )
                fig.update_yaxes(automargin=True)

                fig.write_html(comp_name + '/' + comp_name + '#' + ts_name + '.html')

# comp_pickle_files = ['/home/hari/work/grok_time_series/mad/scripts/rabbitmqqueue_rabbitmq.pickle']

metrics_datapath = '/home/hari/work/grok_time_series/mad/scripts/'

with open(metrics_datapath + 'download_list_july5th.txt', 'r') as download_list:
    data_paths = download_list.read().splitlines()

comp_pickle_files = []

for data_path in data_paths:
    comp_name = data_path.split('/')[-2]
    comp_pickle_files.append(metrics_datapath + comp_name + '.pickle')

with open('sire_data_july5th.pickle', 'rb') as sire_pickle_file:
    total_sire_dict = pickle.load(sire_pickle_file)

total_sire_keys = list(total_sire_dict.keys())

sire_comp_names = [x.split('/')[-2] for x in total_sire_keys]

sire_key_paths = []

for sire_key in total_sire_keys:
    sire_key_parts = sire_key.split('/')
    sire_key_path = '/'.join(sire_key_parts[:-2])
    sire_key_path += '/'
    sire_key_paths.append(sire_key_path)

'''
already_done = [x for x in comp_names for y in comp_pickle_files if x in y]
keys_to_do = list(set(comp_names) - set(already_done))
s3_paths_to_do = []
for key_to_do in keys_to_do:
    s3_path_to_do = []
    for sire_key in total_sire_keys:
        if key_to_do == sire_key.split('/')[-2]:
            s3_path_to_do.append(sire_key)
    if len(s3_path_to_do) > 1:
        print('MORE THAN ONE S3 PATHS ARE MATCHING!')
        sys.exit()
    s3_paths_to_do.extend(s3_path_to_do)
'''

for comp_pickle_file in tqdm.tqdm(comp_pickle_files):
    comp_name = comp_pickle_file.split('.')[-2]
    comp_name = comp_name.split('/')[-1]

    if comp_name in sire_comp_names:
        sire_key_path = sire_key_paths[sire_comp_names.index(comp_name)]
        plot_sire_data(total_sire_dict[sire_key_path + comp_name + '/'], comp_pickle_file)
