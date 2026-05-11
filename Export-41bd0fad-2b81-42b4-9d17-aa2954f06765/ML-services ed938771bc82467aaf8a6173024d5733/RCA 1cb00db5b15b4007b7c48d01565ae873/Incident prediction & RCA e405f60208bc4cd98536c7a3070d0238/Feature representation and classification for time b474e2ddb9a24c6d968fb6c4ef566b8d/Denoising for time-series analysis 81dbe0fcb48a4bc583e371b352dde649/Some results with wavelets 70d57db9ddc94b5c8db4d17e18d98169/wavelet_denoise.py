from datetime import datetime
from os import walk
import pandas as pd
from pathlib import Path
import plotly.graph_objects as go
import pywt
import sys
import time
import tqdm

csv_folder = '/home/hari/data/Affluences_Logfrequency_Data/'
_, _, all_filenames = next(walk(csv_folder + 'input/'))

csv_filenames = []
for cur_filename in all_filenames:
    if cur_filename[-4:] == '.csv':
        csv_filenames.append(cur_filename)

# csv_filenames = ['lfanalyzer_6040a96cdcc614001153fc55-docker-log-monitoring_prometheus-stashed.csv']
# csv_filenames = ['lfanalyzer_6040a96cdcc614001153fc55-docker-log-mysql_router-stashed.csv']
# csv_filenames = ['lfanalyzer_6040a96cdcc614001153fc55-docker-log-monitoring_prometheus-stashed.csv']
# csv_filenames = ['lfanalyzer_6040a96cdcc614001153fc55-docker-log-rabbitmqqueue_rabbitmq-stashed.csv']
# csv_filenames = ['lfanalyzer_6040a96cdcc614001153fc55-docker-log-nodeapp_app-web-stashed.csv']
# csv_filenames = ['lfanalyzer_6040a96cdcc614001153fc55-docker-log-nodesensinglabs-mqtt_sensinglabs-mqtt-stashed.csv']
# csv_filenames = ['lfanalyzer_6040a96cdcc614001153fc55-docker-log-nodesensor-service_sensor-service-stashed.csv']
# csv_filenames = ["lfanalyzer_6040a96cdcc614001153fc55-docker-log-nodescrapers_scrapers-stashed.csv"]

total_num_samples = 8640

for csv_filename in tqdm.tqdm(csv_filenames):
    print(csv_filename)
    csv_full_path = csv_folder + 'input/' + csv_filename
    csv_filename_core = csv_filename.split('.')[0]
    op_path = csv_folder + 'output/'
    Path(op_path).mkdir(parents=True, exist_ok=True)
    op_path = csv_filename_core

    op_dict = {}
    df_all_cols = pd.read_csv(csv_full_path)

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
    df_input = df_input[:total_num_samples]

    num_values = df_input.shape[0]

    value_list = df_input['value']

    timestamp_list = df_input['timestamp'].to_list()

    datetime_list = df_input.index.to_list()
    ori_y_value = df_input['value'].to_numpy()

    # Create wavelet object and define parameters
    w = pywt.Wavelet('coif5')
    maxlev = pywt.dwt_max_level(len(ori_y_value), w.dec_len)
    print("maximum level is " + str(maxlev))
    threshold = 0.5  # Threshold for filtering

    # Decompose into wavelet components, to the level selected:
    coeffs = pywt.wavedec(ori_y_value, 'sym4', level=maxlev)

    # cA = pywt.threshold(cA, threshold*max(cA))
    # plt.figure()
    for i in range(1, len(coeffs)):
        # plt.subplot(maxlev, 1, i)
        # plt.plot(coeffs[i])
        coeffs[i] = pywt.threshold(coeffs[i], threshold*max(coeffs[i]))
        # plt.plot(coeffs[i])

    # plt.show()

    rec_y_value = pywt.waverec(coeffs, 'sym4')

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_input.index, y=ori_y_value, name='True', opacity=0.5))
    fig.add_trace(go.Scatter(x=df_input.index, y=rec_y_value, name="Smooth"))

    fig.update_layout(showlegend=True, title='Input time-series')
    fig.write_image(op_path + f"_ori_denoise_{threshold}.png")
    fig.write_html(op_path + f"_ori_denoise_{threshold}.html")
