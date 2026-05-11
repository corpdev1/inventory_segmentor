import numpy as np
from scipy import stats
import pandas as pd
from itertools import combinations
import networkx as nx

def fisher_z_transform(x, y):
    """ calculate Pearson correlation along with the confidence interval using scipy and numpy

    Parameters
    ----------
    x, y : iterable object such as a list or np.array
      Input for correlation calculation

    Returns
    -------
    r : float
      Pearson's correlation coefficient
    p_value : float
      The corresponding p value
    """

    r, _ = stats.pearsonr(x, y)
    r_z = np.arctanh(r)
    se = 1 / np.sqrt(x.size - 3)
    p_value = 2 * stats.norm.cdf(-abs(r_z / se))
    return r, p_value


def open_csv(path, root = ""):
    """
    Open a corresponding csv file based on the provided path
    """
    # print(root + path)
    title = path.split("|")[-1].replace(".csv", "")
    df = pd.read_csv(root + path, parse_dates=["datetime"])
    return df


rank_all_kpis = True
win_before = 48
win_after = 48
win_middle = 0
time_stamp_scale = 10000
# smooth will apply moving average
smooth = True

paths = []
# anomalies_de17.txt file contains relative paths to csv files with anomalies
# /home/hariprasad-packetai/work/fluxinfer_valentin_poc/anomalies_de17.txt
# /home/hariprasad-packetai/work/dev/code/ml/mad/results/data/af211-af211/cpusat/list_of_metric_files.txt
with open("/home/hariprasad-packetai/work/dev/code/ml/mad/results/data/af211-af211/restoretable/list_of_metric_files.txt") as f:
    for line in f:
        # line = line.replace("|", "_")
        paths.append(line.replace("\n", ""))

# obtain all the time stamps
df_temp = open_csv(paths[0])
time_stamps = df_temp["timestamp"].to_numpy()

num_incidents = 0
incident_top_kpis = {}
incident_anomalous_kpis = {}
green_cases = []
yellow_cases = []
red_cases = []

num_steps = 0

for time_stamp in time_stamps:
    if num_steps > win_before + win_middle and num_steps < len(time_stamps) - win_middle - win_after:
        anomalous_metrics = []
        for path in paths:
            cur_df = open_csv(path)
            time_stamp_off = -win_middle
            is_anomalous = False
            while not is_anomalous and time_stamp_off < (win_middle + 1):
                if time_stamp + time_stamp_off*time_stamp_scale < time_stamps[-1]:
                    row_df = cur_df.loc[cur_df["timestamp"] == time_stamp + time_stamp_off*time_stamp_scale]
                    if not row_df.empty:
                        if not row_df.iloc[0]["isAnomaly"].item():
                            time_stamp_off += 1
                        else:
                            # print(len(row_df["isAnomaly"]))
                            # bool_val = row_df["isAnomaly"].item()
                            is_anomalous = True
                            anomalous_metrics.append(path)
                    else:
                        time_stamp_off += 1
                else:
                    time_stamp_off += 1

        if anomalous_metrics:
            incident_anomalous_kpis[num_incidents] = anomalous_metrics
            print(anomalous_metrics)
            edges = []

            if rank_all_kpis:
                for path in combinations(paths, 2):
                    df1 = open_csv(path[0])
                    df2 = open_csv(path[1])
                    merged = pd.merge(
                        df1[["timestamp", "value"]],
                        df2[["timestamp", "value"]],
                        how="left",
                        on="timestamp",
                    )
                    merged.dropna(inplace=True)
                    merged.sort_values(by="timestamp", inplace=True)
                    merged = merged[merged.timestamp < time_stamp + win_after*time_stamp_scale]
                    merged = merged[merged.timestamp > time_stamp - win_before*time_stamp_scale]
                    if smooth:
                        merged = merged.set_index("timestamp").rolling(6).mean().dropna()
                    x = merged['value_x'].values
                    y = merged['value_y'].values
                    r, p_value = fisher_z_transform(x, y)
                    name_x = path[0].split("/")[-1].replace(".csv", "")
                    name_y = path[1].split("/")[-1].replace(".csv", "")
                    if np.isnan(r):
                        print("An input array is constant; the correlation coefficent is not defined for metrics:")
                        print("- ", name_x, "\n- ", name_y, "\n")
                        continue
                    weight = 1 / (p_value + 1e-10)
                    edges.append((name_x, name_y, weight))
            else:
                for path in combinations(anomalous_metrics, 2):
                    df1 = open_csv(path[0])
                    df2 = open_csv(path[1])
                    merged = pd.merge(
                        df1[["timestamp", "value"]],
                        df2[["timestamp", "value"]],
                        how="left",
                        on="timestamp",
                    )
                    merged.dropna(inplace=True)
                    merged.sort_values(by="timestamp", inplace=True)
                    merged = merged[merged.timestamp < time_stamp + win_after*time_stamp_scale]
                    merged = merged[merged.timestamp > time_stamp - win_before*time_stamp_scale]
                    if smooth:
                        merged = merged.set_index("timestamp").rolling(6).mean().dropna()
                    x = merged['value_x'].values
                    y = merged['value_y'].values
                    r, p_value = fisher_z_transform(x, y)
                    name_x = path[0].split("/")[-1].replace(".csv", "")
                    name_y = path[1].split("/")[-1].replace(".csv", "")
                    if np.isnan(r):
                        print("An input array is constant; the correlation coefficent is not defined for metrics:")
                        print("- ", name_x, "\n- ", name_y, "\n")
                        continue
                    weight = 1 / (p_value + 1e-10)
                    edges.append((name_x, name_y, weight))

            G = nx.Graph()
            G.add_weighted_edges_from(edges)
            pr = nx.pagerank(G, alpha=0.85)

            print("Incident {}".format(num_incidents))
            d = {}
            for idx, (kpi, rank) in enumerate(sorted(pr.items(), key=lambda item: item[1], reverse=True)):
                #         print(idx + 1, kpi)
                if np.any([kpi in anomalous_metric for anomalous_metric in anomalous_metrics]):
                    top_rank = "green"
                    middle_rank = "yellow"
                    low_rank = "red"
                else:
                    top_rank = "blue"
                    middle_rank = "cyan"
                    low_rank = "magenta"

                if idx < 5:
                    print("KPI: {}, Rank score: {}.".format(kpi, rank))
                    if num_incidents in incident_top_kpis:
                        incident_top_kpis[num_incidents].append("KPI: {}, Rank score: {}.".format(kpi, rank))
                    else:
                        incident_top_kpis[num_incidents] = ["KPI: {}, Rank score: {}.".format(kpi, rank)]

                    if kpi in d:
                        d[kpi].append(str(time_stamp) + ":" + top_rank + ":" + str(idx) + ":" + str(rank))
                    else:
                        d[kpi] = [str(time_stamp) + ":" + top_rank + ":" + str(idx) + ":" + str(rank)]
                elif idx + 1 > 5 and idx < 10:  #len(pr.items()) - 5:
                    if kpi in d:
                        d[kpi].append(str(time_stamp) + ":" + middle_rank + ":" + str(idx) + ":" + str(rank))
                    else:
                        d[kpi] = [str(time_stamp) + ":" + middle_rank + ":" + str(idx) + ":" + str(rank)]
                else:
                    if kpi in d:
                        d[kpi].append(str(time_stamp) + ":" + low_rank + ":" + str(idx) + ":" + str(rank))
                    else:
                        d[kpi] = [str(time_stamp) + ":" + low_rank + ":" + str(idx) + ":" + str(rank)]

            for kpi, op_strings in d.items():
                write_string = kpi
                if np.any([kpi in anomalous_metric for anomalous_metric in anomalous_metrics]):
                    for op_string in op_strings:
                        write_string += " " + op_string
                    if np.any(["green" in op_string for op_string in op_strings]):
                        green_cases.append(write_string)
                    if np.any(["yellow" in op_string for op_string in op_strings]):
                        yellow_cases.append(write_string)
                    if np.any(["red" in op_string for op_string in op_strings]):
                        red_cases.append(write_string)

            num_incidents += 1

    num_steps += 1

print("Number of incidents = {}, green KPIs = {}, yellow KPIs = {}, red KPIs = {}".format(num_incidents, len(green_cases), len(yellow_cases), len(red_cases)))
for num_incident in range(num_incidents):
    print("Incident number {}".format(num_incident))
    print("Top KPIs")
    for top_kpi in incident_top_kpis[num_incident]:
        print(top_kpi)

    print("Anomalous KPIs")
    for anomalous_kpi in incident_anomalous_kpis[num_incident]:
        print(anomalous_kpi)

print(green_cases)
print(yellow_cases)
print(red_cases)
