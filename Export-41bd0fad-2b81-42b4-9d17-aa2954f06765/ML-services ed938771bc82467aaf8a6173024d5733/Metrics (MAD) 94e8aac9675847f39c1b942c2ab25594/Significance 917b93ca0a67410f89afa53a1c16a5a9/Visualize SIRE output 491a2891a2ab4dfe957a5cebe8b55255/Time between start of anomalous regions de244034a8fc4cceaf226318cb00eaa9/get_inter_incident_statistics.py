from datetime import datetime
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import pickle
import plotly.express as px

with open('sire_data_old.pickle', 'rb') as sire_pickle_file:
    total_sire_dict = pickle.load(sire_pickle_file)

inter_incident_times = []

for comp_path, comp_sire_dict in total_sire_dict.items():
    comp_name = comp_path  # comp_path.split('/')[-2]
    print(comp_name)
    '''
    # METRIC DATA
    with open('/home/hari/work/grok_time_series/mad/scripts/' + comp_name + '.pickle', 'rb') as pickle_data:
        metric_dict = pickle.load(pickle_data)
    '''
    for ts_name, sire_list in comp_sire_dict.items():
        print(ts_name)

        # all_value_list, all_timestamp_list, all_anom_labels_list = metric_dict[ts_name]  # METRIC DATA

        sire_all_timestamp_list = []
        sire_start_ts_list = []
        sire_end_ts_list = []
        sire_score_list = []

        for cur_incident in sire_list:
            sire_all_timestamp_list.append(cur_incident[0] / 1000)
            sire_all_timestamp_list.append(cur_incident[1] / 1000)
            sire_all_timestamp_list.append(cur_incident[2] / 1000)

            sire_start_ts_list.append(cur_incident[1] / 1000)
            sire_end_ts_list.append(cur_incident[2] / 1000)
            sire_score_list.append(cur_incident[3])

        start_timestamp = min(sire_all_timestamp_list) - 86400
        end_timestamp = max(sire_all_timestamp_list) + 86400

        '''
        # METRIC DATA
        pick_value_list = []
        pick_timestamp_list = []
        pick_anom_labels_list = []
        i_cnt = 0

        for i_timestamp in all_timestamp_list:
            if start_timestamp < i_timestamp / 1000 < end_timestamp:
                pick_value_list.append(all_value_list[i_cnt])
                pick_timestamp_list.append(all_timestamp_list[i_cnt])
                pick_anom_labels_list.append(all_anom_labels_list[i_cnt])
            i_cnt += 1
        '''
        sire_start_ts_list.sort()

        for i in range(len(sire_start_ts_list) - 1):
            inter_incident_times.append(sire_start_ts_list[i+1] - sire_start_ts_list[i])

lowest_inter_incident_times = [x for x in inter_incident_times if x < 3600]

plt.hist(lowest_inter_incident_times, bins=100)
plt.xlabel("Time between start of adjacent incidents (in seconds)")
plt.ylabel("Number of pairs")
plt.title(f"Total number of pairs: {len(lowest_inter_incident_times)}")
plt.show()
