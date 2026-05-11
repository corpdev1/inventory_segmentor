from datetime import datetime
import matplotlib

matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import pandas as pd
import pickle
import plotly.express as px
import plotly.graph_objs as go
from plotly.subplots import make_subplots
import sys

with open('sire_data_july5th.pickle', 'rb') as sire_pickle_file:
    total_sire_dict = pickle.load(sire_pickle_file)

start_ts_values = []
score_values = []
duration_values = []
deviation_values = []
inter_region_times = []
point_names = []
datetime_values = []
level_values = []

yellow_color = "rgba(250, 250, 0, 0.75)"
orange_color = "rgba(250, 160, 0, 0.75)"
red_color = "rgba(250, 0, 0, 0.75)"

for comp_path, comp_sire_dict in total_sire_dict.items():
    comp_name = comp_path.split('/')[-2]
    print(comp_name)

    # METRIC DATA
    with open('/home/hari/work/grok_time_series/mad/scripts/' + comp_name + '.pickle', 'rb') as pickle_data:
        metric_dict, region_dict = pickle.load(pickle_data)

    for ts_name, cur_tup in region_dict.items():
        if ts_name in comp_sire_dict:
            start_list = cur_tup[0]
            dur_list = cur_tup[1]
            dev_list = cur_tup[2]

            sire_list = comp_sire_dict[ts_name]

            mad_sire_cnt = 0
            no_match_fnd = True

            cur_start_ts_values = []
            cur_score_values = []
            cur_dur_values = []
            cur_dev_values = []
            cur_point_names = []
            cur_datetime_values = []

            for cur_start in start_list:
                score_fnd = False
                sire_cnt = 0

                while not score_fnd and sire_cnt < len(sire_list):
                    if sire_list[sire_cnt][1] == cur_start:
                        no_match_fnd = False
                        score_fnd = True
                        cur_start_ts_values.append(cur_start / 1000)
                        cur_score_values.append(sire_list[sire_cnt][3])
                        cur_dur_values.append(dur_list[mad_sire_cnt])
                        cur_dev_values.append(dev_list[mad_sire_cnt])
                        cur_point_names.append("{}#{}".format(comp_name, ts_name))
                        cur_datetime_values.append(datetime.fromtimestamp(cur_start / 1000))

                    sire_cnt += 1

                mad_sire_cnt += 1

            if no_match_fnd:
                sys.exit("No match found between SIRE output and mad_metrics_output.")

            if len(cur_start_ts_values) > 1:
                sorted_ind = [i[0] for i in sorted(enumerate(cur_start_ts_values), key=lambda x: x[1])]

                cur_start_ts_sort = [cur_start_ts_values[i] for i in sorted_ind]
                cur_score_sort = [cur_score_values[i] for i in sorted_ind]
                cur_dur_sort = [cur_dur_values[i] for i in sorted_ind]
                cur_dev_sort = [cur_dev_values[i] for i in sorted_ind]
                cur_point_names_sort = [cur_point_names[i] for i in sorted_ind]
                cur_datetime_sort = [cur_datetime_values[i] for i in sorted_ind]
                cur_inter_times_sort = []

                for i in range(len(cur_start_ts_sort) - 1):
                    cur_inter_times_sort.append(cur_start_ts_sort[i + 1] - cur_start_ts_sort[i] - cur_dur_sort[i])

                cur_start_ts_sort = cur_start_ts_sort[1:]
                cur_score_sort = cur_score_sort[1:]
                cur_dur_sort = cur_dur_sort[1:]
                cur_dev_sort = cur_dev_sort[1:]
                cur_point_names_sort = cur_point_names_sort[1:]
                cur_datetime_sort = cur_datetime_sort[1:]

                for i in range(len(cur_start_ts_sort)):
                    region_score = cur_score_sort[i]

                    start_ts_values.append(cur_start_ts_sort[i])
                    score_values.append(region_score)
                    duration_values.append(cur_dur_sort[i])
                    deviation_values.append(cur_dev_sort[i])
                    inter_region_times.append(cur_inter_times_sort[i])
                    point_names.append(cur_point_names_sort[i])
                    datetime_values.append(cur_datetime_sort[i])

                    if region_score < 0.8:
                        fill_color = yellow_color
                    elif region_score < 0.9:
                        fill_color = orange_color
                    else:
                        fill_color = red_color

                    level_values.append(fill_color)

# fig = px.scatter(x=deviation_values, y=score_values)
# fig.write_html('deviation_score.html')

df_plot = pd.DataFrame({"start": start_ts_values, "score": score_values, "duration": duration_values,
                        "deviation": deviation_values, "inter_region_time": inter_region_times, "name": point_names,
                        "datetime": datetime_values, "level": level_values})

fig1 = px.scatter(df_plot, x="inter_region_time", y="score", color="level", color_discrete_map="identity", hover_name="name",
                  hover_data=["datetime", "score", "duration", "deviation", "inter_region_time"])

fig1.write_html('inter_region_score.html')

fig2 = px.scatter(df_plot, x="deviation", y="inter_region_time", color="level", color_discrete_map="identity", hover_name="name",
                  hover_data=["datetime", "score", "duration", "deviation", "inter_region_time"])

fig2.write_html('deviation_inter_region.html')

fig3 = px.scatter(df_plot, x="duration", y="inter_region_time", color="level", color_discrete_map="identity", hover_name="name",
                  hover_data=["datetime", "score", "duration", "deviation", "inter_region_time"])

fig3.write_html('duration_inter_region.html')

fig4 = px.scatter_3d(df_plot, x="duration", y="deviation", z="inter_region_time", color="level", color_discrete_map="identity", hover_name="name",
                  hover_data=["datetime", "score", "duration", "deviation", "inter_region_time"])

fig4.write_html('all_three.html')
