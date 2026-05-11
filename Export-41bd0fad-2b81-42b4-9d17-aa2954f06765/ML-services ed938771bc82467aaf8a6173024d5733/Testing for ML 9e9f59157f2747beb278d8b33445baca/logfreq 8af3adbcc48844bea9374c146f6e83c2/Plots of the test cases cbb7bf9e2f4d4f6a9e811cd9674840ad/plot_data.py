import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
import pickle
import plotly.graph_objects as go
import plotly.express as px

mpl_ply_flag = 'ply'

final_op_anom_ts = []

anom_wins = [[1636970940, 1636971060]]

scenario_name = 'scenario12'

with open(f'{scenario_name}_lf_debug.pickle', 'rb') as pickle_file:
    scaled_ts_list, all_isAnomaly_list, all_value_list, all_anomalyScore_list = pickle.load(pickle_file)

ts_list = []
isAnomaly_list = []
value_list = []
anomalyScore_list = []

cnt_ind = 0

for scaled_ts in scaled_ts_list:
    cur_ts = int(scaled_ts/1000)

    if len(anom_wins) > 0:
        for anom_win in anom_wins:
            if anom_win[0] - 10800 <= cur_ts <= anom_win[1] + 10800:
                ts_list.append(cur_ts)
                isAnomaly_list.append(all_isAnomaly_list[cnt_ind])
                value_list.append(all_value_list[cnt_ind])
                anomalyScore_list.append(all_anomalyScore_list[cnt_ind])
    else:
        ts_list.append(cur_ts)
        isAnomaly_list.append(all_isAnomaly_list[cnt_ind])
        value_list.append(all_value_list[cnt_ind])
        anomalyScore_list.append(all_anomalyScore_list[cnt_ind])

    cnt_ind += 1

cnt_ind = 0

anom_ts_list = []

for cur_ts in ts_list:
    if isAnomaly_list[cnt_ind]:
        anom_ts_list.append(ts_list[cnt_ind])
    cnt_ind += 1

if mpl_ply_flag == 'mpl':
    plt.plot(ts_list, value_list, mfc='none', alpha=0.3)
elif mpl_ply_flag == 'ply':
    df = pd.DataFrame({'timestamp': ts_list, 'values': value_list})
    fig = px.line(df, x='timestamp', y='values')
    fig.update_layout(xaxis_tickformat='f')

if mpl_ply_flag == 'mpl':
    for cur_ts in anom_ts_list:
        ts_ind = ts_list.index(cur_ts)

        plt.plot(ts_list[ts_ind], value_list[ts_ind], 'gd', mfc='none', alpha=0.3)
elif mpl_ply_flag == 'ply':
    ts_plt = []
    value_plt = []
    for cur_ts in anom_ts_list:
        ts_ind = ts_list.index(cur_ts)
        ts_plt.append(ts_list[ts_ind])
        value_plt.append(value_list[ts_ind])

    fig.add_trace(go.Scatter(x=ts_plt, y=value_plt,
                             marker=dict(color="green", size=12), mode="markers", name="anomalies-topic"))

if mpl_ply_flag == 'mpl':
    for anom_win in anom_wins:
        for cur_ts in anom_win:
            ts_ind = ts_list.index(cur_ts)

            plt.plot(ts_list[ts_ind], value_list[ts_ind], 'ro', mfc='none', alpha=0.3)
elif mpl_ply_flag == 'ply':
    ts_plt = []
    value_plt = []
    for anom_win in anom_wins:
        for cur_ts in anom_win:
            ts_ind = ts_list.index(cur_ts)
            ts_plt.append(ts_list[ts_ind])
            value_plt.append(value_list[ts_ind])

    fig.add_trace(go.Scatter(x=ts_plt, y=value_plt,
                             marker=dict(color="red", size=12), mode="markers", name="anomaly windows"))

if mpl_ply_flag == 'mpl':
    for anom_ts in final_op_anom_ts:
        ts_ind = ts_list.index(anom_ts)

        plt.plot(ts_list[ts_ind], value_list[ts_ind], 'c+', mfc='none', alpha=0.3)
elif mpl_ply_flag == 'ply':
    ts_plt = []
    value_plt = []
    for cur_ts in final_op_anom_ts:
        ts_ind = ts_list.index(cur_ts)
        ts_plt.append(ts_list[ts_ind])
        value_plt.append(value_list[ts_ind])

    fig.add_trace(go.Scatter(x=ts_plt, y=value_plt,
                             marker=dict(color="cyan", size=12), mode="markers", name="anomalies-evaluate"))

if mpl_ply_flag == 'mpl':
    plt.savefig(f"{scenario_name}_debug_plot.png", dpi=1200)
    plt.close()
elif mpl_ply_flag == 'ply':
    fig.write_html(f"{scenario_name}_debug_plot.html")
