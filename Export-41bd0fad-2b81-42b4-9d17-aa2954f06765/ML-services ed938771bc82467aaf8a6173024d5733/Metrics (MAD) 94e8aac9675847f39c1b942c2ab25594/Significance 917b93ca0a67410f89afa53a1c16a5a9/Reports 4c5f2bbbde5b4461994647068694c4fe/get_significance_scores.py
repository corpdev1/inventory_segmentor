import pickle

import boto3
from statsmodels.distributions import ECDF
from scipy import stats
from src.conf import aws_credentials
from utils.general_utils import make_directory
from utils.s3_utils import download_file_s3
import os
import json
import glob
import numpy as np
import pandas as pd
from datetime import datetime
import matplotlib.pyplot as plt


def compose_anomaly_dict(path):
    current_dict = {}
    with open(path, "rb") as f:
        for line in f:
            msg = json.loads(line)
            if msg.get("duration_deviation", {}):
                for metric in msg["duration_deviation"]:
                    if metric not in current_dict:
                        current_dict[metric] = {
                            "deviation": [
                                msg["duration_deviation"][metric]["deviation"]
                            ],
                            "duration": [
                                msg["duration_deviation"][metric]["duration"]],
                            "start": [
                                msg["duration_deviation"][metric]["start"]],
                        }
                    else:
                        current_dict[metric]["deviation"].append(
                            msg["duration_deviation"][metric]["deviation"]
                        )
                        current_dict[metric]["duration"].append(
                            msg["duration_deviation"][metric]["duration"]
                        )
                        current_dict[metric]["start"].append(
                            msg["duration_deviation"][metric]["start"]
                        )
    return current_dict


def merge_anomaly_dicts(anomaly_dicts_list):
    merged_dict = {}
    for d in anomaly_dicts_list:
        for metric in d:
            if metric not in merged_dict:
                merged_dict[metric] = d[metric]
            else:
                merged_dict[metric]["deviation"] += d[metric]["deviation"]
                merged_dict[metric]["duration"] += d[metric]["duration"]
                merged_dict[metric]["start"] += d[metric]["start"]
    return merged_dict


def analyze(df, verbose=False):
    vals = []
    for idx, anomaly in df.iterrows():
        weights = {
            "deviation": 2,
            "duration": 2,
            "tb": 2,
        }
        if idx > 10:
            current_duration = anomaly["duration"]
            current_deviation = anomaly["deviation"]
            # duration significance
            # rule-based significance
            if current_duration > 12:
                duration_significance = 1.0
            elif current_duration > 6:
                duration_significance = 0.8
            elif current_duration > 3:
                duration_significance = 0.6
            elif current_duration > 1:
                duration_significance = 0.4
            else:
                duration_significance = 0.2

            # deviation significance
            deviation_ecdf = ECDF(df[:idx].deviation, side="right")
            deviation_significance = deviation_ecdf(current_deviation)

            # time between anomalies significance
            df2 = df[:idx + 1].copy()
            df2["time_between"] = (
                    df2.start - df2.start.shift(1) - df2.duration.shift(
                1) * 10 * 1000
            )
            tb_zscores = abs(
                stats.zscore(np.log(1 + df2.dropna().time_between)))
            tb_significance = (tb_zscores / 3).clip(min=0, max=1)[-1]
            current_time_between = df2.dropna().time_between.values[-1]
            if verbose:
                print(idx)
                print(
                    f"deviation: {current_deviation}, "
                    f"duration: {current_duration}, "
                    f"time_between: {current_time_between}"
                )
                print(
                    f"duration_significance: {duration_significance:.3f}\n"
                    f"deviation_significance: {deviation_significance:.3f}\n"
                    f"tb_significance: {tb_significance:.3f}\n "
                )
            # avg_dur_dev = (
            #                       duration_significance * weights["duration"]
            #                       + deviation_significance * weights[
            #                           "deviation"]
            #               ) / (weights["duration"] + weights["deviation"])
            # avg_tb_dev = (
            #                      tb_significance * weights["tb"]
            #                      + deviation_significance * weights[
            #                          "deviation"]
            #              ) / (weights["tb"] + weights["deviation"])
            avg_score = (
                                duration_significance * weights["duration"]
                                + deviation_significance * weights["deviation"]
                                + tb_significance * weights["tb"]
                        ) / (weights["duration"] + weights["deviation"] +
                             weights["tb"])
            if verbose:
                # print(f"Avg. duration_deviation score = {avg_dur_dev}")
                print(f"Avg. score = {avg_score}")
                print("=" * 20)
            vals += [
                [
                    current_deviation,
                    anomaly["start"] + 10000 * i,
                    current_time_between,
                    duration_significance,
                    deviation_significance,
                    tb_significance,
                    # avg_dur_dev,
                    # avg_tb_dev,
                    avg_score,
                ]
                for i in range(int(current_duration) + 1)
            ]

    return vals


def parse_path(path):
    s = path.replace(".csv", "").split("/")
    metric = s[-1]
    component = s[-2]
    source = s[-3]
    return source, component, metric


def format_time(t):
    n = t // 1000
    day = int(n // (24 * 3600))

    n = n % (24 * 3600)
    hour = int(n // 3600)

    n %= 3600
    minutes = int(n // 60)

    n %= 60
    seconds = n

    if day > 0:
        return f"{day} day(s) {hour} hour(s) {minutes} minute(s) {seconds} s."
    elif hour > 0:
        return f"{hour} hour(s) {minutes} minute(s) {seconds} s."
    elif minutes > 0:
        return f"{minutes} minute(s) {seconds} s."
    else:
        return f"{seconds} s."


def compose_report(root_csv, report_path):
    total_anomalies, abnormal_periods, total_metrics = 0, 0, 0
    dfs = []
    min_date, max_date = None, None
    for a, b, c in os.walk(root_csv):
        if c:
            for csv_name in c:
                if csv_name.endswith(".csv"):
                    total_metrics += 1
                    csv_path = os.path.join(a, csv_name)
                    df = pd.read_csv(csv_path)
                    if len(df) > 0:
                        source, component, metric = parse_path(csv_path)
                        df["metric"] = metric
                        df["source"] = source
                        df["component"] = component
                        if not min_date:
                            min_date = min(df.timestamp)
                        else:
                            if min_date > min(df.timestamp):
                                min_date = min(df.timestamp)
                        if not max_date:
                            max_date = max(df.timestamp)
                        else:
                            if max_date < max(df.timestamp):
                                max_date = max(df.timestamp)
                        total_anomalies += len(df)
                        abnormal_periods += len(
                            df.drop_duplicates(
                                subset=["time_between", "deviation"])
                        )
                        dfs.append(df)
    output_strings = []
    s = f"Time span: from {min_date} to {max_date} "
    output_strings.append(s)
    output_strings.append(
        f"({(pd.to_datetime(max_date) - pd.to_datetime(min_date)).days} days)\n")
    s = f"Total anomalies: {total_anomalies}, abnormal periods = {abnormal_periods}, total number of metrics = {total_metrics}\n"
    output_strings.append(s)
    dfs = pd.concat(dfs).reset_index(drop=True)
    dfs["timestamp"] = pd.to_datetime(dfs["timestamp"])
    output_strings.append(
        f"\n##### Number of anomalies according to significance levels: #####\n")
    for level in [0.7, 0.8, 0.9]:
        s = f"Significance at least " \
            f"{level * 100}%:\n\t{len(dfs[dfs.avg_score_significance >= level])} " \
            f"anomalies ({100 * len(dfs[dfs.avg_score_significance >= level]) / total_anomalies:.2f}% of overall amount of anomalies)\n"
        output_strings.append(s)

    # anomalies per component over time
    temp = dfs.set_index("timestamp").copy()
    temp["count"] = 1
    temp = temp[["count", "component"]].groupby(["component"]).resample(
        "12H").sum().reset_index()
    for compo in temp.component.unique():
        ax = temp[temp["component"] == compo].plot(x="timestamp", y="count",
                                                   kind="bar", figsize=(16, 6),
                                                   title=compo)
        fig = ax.get_figure()
        plt.tight_layout()
        fig.savefig(os.path.join(report_path, f'anomalies_{compo}.png'))
        plt.close(fig)

    # overall anomalies
    temp = dfs.set_index("timestamp").copy()
    temp["count"] = 1
    agg = "12H"
    ax = temp[["count"]].resample(agg).sum().plot(kind="bar", figsize=(16, 6),
                                                  title=f"Total amount of anomalies per {agg}")
    fig = ax.get_figure()
    plt.tight_layout()
    fig.savefig(os.path.join(report_path, 'total_amount_of_anomalies.png'))
    plt.close(fig)

    # most significant anomalies
    most_significant = dfs[dfs.avg_score_significance >= 0.8].sort_values(
        by="timestamp")
    most_significant["duration"] = 1
    most_significant = most_significant.groupby(
        [col for col in most_significant.columns if col != "timestamp"],
        as_index=False
    ).agg(
        {"duration": sum, "timestamp": "first"}
    )

    output_strings.append(
        f"\n##### The most significant anomalies per component: #####\n")
    for group, df in most_significant.groupby(["source", "component"]):
        s = "\nSource: {0[0]}\n\tComponent: {0[1]}\n".format(group)
        output_strings.append(s)
        for _, row in df.sort_values(
                by=["avg_score_significance", "timestamp"],
                ascending=False).iterrows():
            s = f'{row["timestamp"]} ' \
                f'-- score: {row["avg_score_significance"]:.3f} ' \
                f'-- duration: {format_time(row["duration"] * 10000)} ' \
                f'-- deviation: {row["deviation"]:.2f} ' \
                f'-- time since last anomaly: {format_time(row["time_between"])} ' \
                f'seconds ' \
                f'-- {row["metric"]}\n'
            output_strings.append(s)
    print("".join(output_strings))
    with open(os.path.join(report_path, "report.txt"), "w") as file1:
        file1.writelines(output_strings)
    dfs.to_csv(os.path.join(report_path, "all_anomalies.csv"), index=None)


def get_relevance_scores(my_bucket_name):
    # my_bucket_name = "packetai.ingest.affluences"

    # download directories
    my_local_download_path = "../relevance_score/"
    merged_dict_root = os.path.join(my_local_download_path, "merged_dicts")

    s3 = boto3.client(
        "s3",
        aws_access_key_id=aws_credentials["aws_access_key_id"],
        aws_secret_access_key=aws_credentials["aws_secret_access_key"],
    )
    last_local_path = None
    all_paths = [key["Key"] for key in s3.list_objects(Bucket=my_bucket_name,
                                                       Prefix="mad_metrics_output")[
        "Contents"]]
    all_paths_dict = {}
    for current_s3_path in all_paths:
        # current_s3_path = key["Key"]
        current_local_path = os.path.join(my_local_download_path,
                                          *current_s3_path.split("/")[:-1])
        if current_local_path not in all_paths_dict:
            all_paths_dict[current_local_path] = [current_s3_path]
        else:
            all_paths_dict[current_local_path].append(current_s3_path)

    for current_local_path in all_paths_dict:
        print(f"\n***** {current_local_path} *****\n")
        current_download_path = os.path.join(my_local_download_path,
                                             current_local_path)
        make_directory(current_download_path)
        for current_s3_path in all_paths_dict[current_local_path]:
            current_file_name = current_s3_path.split("/")[-1]
            download_file_s3(s3_path=current_s3_path,
                             local_path=current_local_path,
                             output_name=current_file_name,
                             bucket_name=my_bucket_name)
        # break
        print("Merging anomaly dicts...")
        anomaly_dicts = [
            compose_anomaly_dict(path) for path in [name for name in
                                                    glob.glob(
                                                        current_download_path + "/*")]
        ]

        merged_dicts = merge_anomaly_dicts(anomaly_dicts)

        print(f"Extracted {len(merged_dicts.keys())} metrics")
        # save dictionary with anomalies
        current_merged_dict_path = os.path.join(merged_dict_root,
                                                *all_paths_dict[
                                                     current_local_path][
                                                     0].split("/")[:-1])
        make_directory(current_merged_dict_path)
        with open(os.path.join(current_merged_dict_path, "merged.pickle"),
                  "wb") as handle:
            pickle.dump(merged_dicts, handle, protocol=pickle.HIGHEST_PROTOCOL)

        csv_report_root = os.path.join(my_local_download_path, "csv_reports")
        csv_path = os.path.join(csv_report_root,
                                *all_paths_dict[
                                     current_local_path][
                                     0].split("/")[:-1])
        make_directory(csv_path)
        print("Calculating the relevance score...")
        for idx, metric in enumerate(merged_dicts.keys()):
            df = pd.DataFrame(merged_dicts[metric])
            df = df.sort_values(by="start").reset_index(drop=True)
            vals = analyze(df, verbose=False)
            df_anomalies = pd.DataFrame(
                vals,
                columns=[
                    "deviation",
                    "timestamp",
                    "time_between",
                    "duration_significance",
                    "deviation_significance",
                    "tb_significance",
                    # "avg_dur_dev_significance",
                    # "avg_tb_dev",
                    "avg_score_significance",
                ],
            )
            df_anomalies["timestamp"] = df_anomalies["timestamp"].apply(
                lambda x: datetime.utcfromtimestamp(x / 1000)
            )
            df_anomalies.to_csv(
                os.path.join(csv_path, metric + ".csv"), index=None)
            # df_anomalies.drop_duplicates(subset=["time_between",
            #                                      "deviation"]).to_csv(
            #     os.path.join(csv_path, metric + ".csv"), index=None)
            print(f"Extracted {idx + 1} metric(s) ("
                  f"{(idx + 1) * 100 // len(merged_dicts.keys())} %)")
        print("Delete s3 files...")
        for file_to_delete in glob.glob(current_local_path + "/*"):
            if os.path.exists(file_to_delete):
                os.remove(file_to_delete)
        # if len(merged_dicts.keys()) > 0:
        #     break


if __name__ == '__main__':
    my_bucket_name = "packetai.ingest.affluences"
    root_csv = "../relevance_score_GetMyUni/csv_reports"
    report_path = "../relevance_score_GetMyUni/report"
    make_directory(report_path)
    # get_relevance_scores(my_bucket_name)
    compose_report(root_csv, report_path)
