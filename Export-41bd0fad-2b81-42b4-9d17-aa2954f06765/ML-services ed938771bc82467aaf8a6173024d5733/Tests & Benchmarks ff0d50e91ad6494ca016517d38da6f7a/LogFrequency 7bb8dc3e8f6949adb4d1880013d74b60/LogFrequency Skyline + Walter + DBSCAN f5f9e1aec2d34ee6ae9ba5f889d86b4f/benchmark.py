import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output
import plotly.express as px
import pandas as pd
import glob
import os
import dash_daq as daq
import plotly.graph_objects as go
from datetime import timedelta
from sklearn.cluster import KMeans, DBSCAN
from sklearn.preprocessing import MinMaxScaler
import numpy as np
import dash_bootstrap_components as dbc
from time import time
import json


app = dash.Dash(__name__)


paths = {}
for a, b, c in os.walk("data/"):
    if c:
        for file in c:
            if file.endswith(".csv"):
                name = "-".join(a.split("/")[1:3])
                path = os.path.join(a, file)
                # print(a, b, c, name)
                paths.update({name: path})

dropdown_options = [
    {"label": name, "value": value} for name, value in paths.items()
]
dropdown_options = sorted(dropdown_options, key=lambda x: x["label"])

detector_names = [
    "median_absolute_deviation",
    "first_hour_average",
    "mean_subtraction_cumulation",
    "stddev_from_average",
    "stddev_from_moving_average",
    "least_squares",
    "histogram_bins",
    "walter",
]


@app.callback(
    Output("intermediate-df", "data"), [Input("data_path-dropdown", "value")],
)
def data_generation(df_path):
    if df_path is None:
        return None
    # some expensive clean data step
    df_plot = pd.read_csv(df_path)
    df_plot["datetime"] = pd.to_datetime(df_plot["timestamp"], unit="s")
    df_plot["avg_score"] = df_plot[detector_names].mean(axis=1)
    df_plot["hour"] = df_plot["datetime"].apply(lambda x: x.hour)
    df_plot["minute"] = df_plot["datetime"].apply(lambda x: x.minute)
    for v in ["hour", "minute"]:
        df_plot["sin_" + v] = (
            df_plot[v].apply(lambda x: np.sin(x / 24 * 2 * np.pi))
            if v == "hour"
            else df_plot[v].apply(lambda x: np.sin(x / 60 * 2 * np.pi))
        )
        df_plot["cos_" + v] = (
            df_plot[v].apply(lambda x: np.cos(x / 24 * 2 * np.pi))
            if v == "hour"
            else df_plot[v].apply(lambda x: np.cos(x / 60 * 2 * np.pi))
        )
    return df_plot.to_json(date_format="iso", orient="split")


def ispositivefloat(value):
    if value is None:
        return False
    try:
        float(value)
        return True if float(value) > 0 else False
    except ValueError:
        return


@app.callback(
    Output("intermediate-clusters", "data"),
    [
        Input("intermediate-df", "data"),
        Input("threshold-slider", "value"),
        Input("n_clusters-input-kmeans", "value"),
        Input("submit-kmeans", "n_clicks"),
        Input("eps-dbscan", "value"),
        Input("min_samples-dbscan", "value"),
        Input("submit-dbscan", "n_clicks"),
        Input("checklist_id", "value"),
    ],
)
def get_clusters(
    jsonified_data,
    df_threshold,
    submit_n_clusters,
    btn_kmeans,
    eps_dbscan,
    min_samples_dbscan,
    submit_dbscan,
    show_dbscan_clusters,
):
    if jsonified_data is None:
        return json.dumps({"value": []}, indent=2)
    changed_id = [p["prop_id"] for p in dash.callback_context.triggered][0]
    anomaly_colors = []
    if any(id in changed_id for id in ["submit-kmeans", "submit-dbscan"]):
        df_plot = pd.read_json(jsonified_data, orient="split")
        scale = True
        anomalies = df_plot[df_plot["avg_score"] > df_threshold]
        if "submit-kmeans" in changed_id:
            n_clusters = (
                int(submit_n_clusters)
                if str(submit_n_clusters).isnumeric()
                else 0
            )
            if anomalies.shape[0] > n_clusters and n_clusters > 0:
                X = anomalies[
                    [
                        "value",
                        "sin_hour",
                        "cos_hour",
                        "sin_minute",
                        "cos_minute",
                    ]
                ].values
                if scale:
                    X = MinMaxScaler().fit_transform(X)
                kmeans = KMeans(n_clusters=n_clusters, random_state=0).fit(X)
                anomaly_colors = [int(i) for i in kmeans.labels_]
        elif "submit-dbscan" in changed_id:
            if (
                ispositivefloat(eps_dbscan)
                and str(min_samples_dbscan).isnumeric()
                and anomalies.shape[0] > int(min_samples_dbscan)
            ):
                X = anomalies[
                    [
                        "value",
                        "sin_hour",
                        "cos_hour",
                        "sin_minute",
                        "cos_minute",
                    ]
                ].values
                if scale:
                    X = MinMaxScaler().fit_transform(X)
                dbscan = DBSCAN(
                    eps=float(eps_dbscan), min_samples=int(min_samples_dbscan)
                ).fit(X)
                if show_dbscan_clusters and (2 in show_dbscan_clusters):
                    anomaly_colors = [int(i) for i in dbscan.labels_]
                else:
                    anomaly_colors = [
                        "red" if i == -1 else "green" for i in dbscan.labels_
                    ]
    return json.dumps({"value": list(anomaly_colors)}, indent=2)


@app.callback(
    Output("funnel-graph", "figure"),
    [
        Input("intermediate-df", "data"),
        Input("data_path-dropdown", "value"),
        Input("threshold-slider", "value"),
        Input("checklist_id", "value"),
        Input("intermediate-clusters", "data"),
    ],
)
def update_graph(
    jsonified_data,
    df_path,
    df_threshold,
    include_detectors,
    intermediate_clusters,
):
    fig = go.Figure()
    if df_path is None or jsonified_data is None:
        print("No path selected")
        return fig
    changed_id = [p["prop_id"] for p in dash.callback_context.triggered][0]
    df_plot = pd.read_json(jsonified_data, orient="split")
    # print("include_detectors", include_detectors)
    start_train_dt = df_plot["datetime"][0]
    end_train_dt = start_train_dt + timedelta(days=3)
    source = "-".join(df_path.split("/")[1:3])

    anomalies = df_plot[df_plot["avg_score"] > df_threshold]
    clusters = json.loads(intermediate_clusters)["value"]
    anomaly_colors = clusters if clusters else [1] * anomalies.shape[0]

    train_point_annotation = [
        f"score = {score:.2f}"
        for score in df_plot[df_plot["datetime"] <= end_train_dt][
            "avg_score"
        ].values
    ]
    fig.add_trace(
        go.Scatter(
            x=df_plot[df_plot["datetime"] <= end_train_dt]["datetime"],
            y=df_plot[df_plot["datetime"] <= end_train_dt]["value"],
            mode="lines",
            name="train period",
            marker=dict(size=10, color="rgba(255, 128, 0, 0.7)"),
            text=train_point_annotation,
        )
    )
    point_annotation = [
        f"score = {score:.2f}"
        for score in df_plot[df_plot["datetime"] > end_train_dt][
            "avg_score"
        ].values
    ]
    fig.add_trace(
        go.Scatter(
            x=df_plot[df_plot["datetime"] > end_train_dt]["datetime"],
            y=df_plot[df_plot["datetime"] > end_train_dt]["value"],
            mode="lines",
            name="values",
            marker=dict(size=10, color="rgba(0, 102, 205, 0.8)"),
            text=point_annotation,
        )
    )
    anomaly_annotation = [
        f"score = {score:.2f}, cluster = {label}"
        for score, label in zip(
            df_plot[df_plot["avg_score"] > df_threshold]["avg_score"].values,
            anomaly_colors,
        )
    ]
    fig.add_trace(
        go.Scatter(
            x=df_plot[df_plot["avg_score"] > df_threshold]["datetime"],
            y=df_plot[df_plot["avg_score"] > df_threshold]["value"],
            mode="markers",
            name="avg score",
            marker=dict(size=6, color="rgba(155, 0, 0, 0.8)"),
            text=anomaly_annotation,
            marker_color=anomaly_colors,
        )
    )
    # print(include_detectors)
    if include_detectors and (1 in include_detectors):
        for detector in detector_names:
            current_trace = go.Scatter(
                x=df_plot[df_plot[detector] > df_threshold]["datetime"],
                y=df_plot[df_plot[detector] > df_threshold]["value"],
                mode="markers",
                marker_symbol="square",
                name=detector,
                marker=dict(size=6, color="rgba(0, 250, 70, 0.7)"),
                visible="legendonly",
            )
            fig.add_trace(current_trace)
    fig.update_layout(
        title=f"{source} (threshold = {df_threshold})",
        xaxis_title="Date",
        yaxis_title="Log count",
        width=1600,
        height=500,
    )
    return fig


@app.callback(
    Output("container-button-kmeans", "children"),
    [
        Input("n_clusters-input-kmeans", "value"),
        Input("submit-kmeans", "n_clicks"),
        Input("data_path-dropdown", "value"),
    ],
)
def displayKMeans(n_clusters, btn, df_path):
    changed_id = [p["prop_id"] for p in dash.callback_context.triggered][0]
    # print(changed_id)
    if "submit-kmeans" in changed_id:
        if str(n_clusters).isnumeric() and int(n_clusters) > 0:
            msg = f"Selected {n_clusters} clusters"
        else:
            msg = "The number of clusters should be greater than 0 but less than the total number of anomalies"
    else:
        msg = ""
    return html.Div(msg)


@app.callback(
    Output("container-button-dbscan", "children"),
    [
        Input("eps-dbscan", "value"),
        Input("min_samples-dbscan", "value"),
        Input("submit-dbscan", "n_clicks"),
        Input("data_path-dropdown", "value"),
    ],
)
def displayDBSCAN(eps_dbscan, min_samples, btn, df_path):
    changed_id = [p["prop_id"] for p in dash.callback_context.triggered][0]
    # print(changed_id)
    if "submit-dbscan" in changed_id:
        if ispositivefloat(eps_dbscan) and str(min_samples).isnumeric():
            msg = (
                f"Selected eps = {eps_dbscan} and min_samples = {min_samples}"
            )
        else:
            msg = (
                "eps should be a positive float and min_samples should be int"
            )
    else:
        msg = ""
    return html.Div(msg)


app.layout = html.Div(
    children=[
        html.H1(children="Skyline and Walter benchmark with LogCount data"),
        html.Div(
            [
                dcc.Dropdown(
                    id="data_path-dropdown", options=dropdown_options
                ),
                dcc.Checklist(
                    options=[
                        {"label": "Include detectors", "value": 1},
                        {"label": "Show DBSCAN clusters", "value": 2},
                    ],
                    id="checklist_id",
                ),
                html.Div(id="slider_annotation", style={"margin-top": 20}),
                dcc.Slider(
                    id="threshold-slider",
                    min=0,
                    max=1,
                    step=0.05,
                    value=0.9,
                    marks={
                        0: "0.0",
                        0.5: "0.5",
                        0.75: "0.75",
                        0.9: "0.9",
                        1: "1.0",
                    },
                ),
                # KMeans related objects
                html.Div(
                    dcc.Input(
                        id="n_clusters-input-kmeans",
                        type="number",
                        # value=0,
                        placeholder="n_clusters",
                        min=1,
                    )
                ),
                html.Button("K-Means", id="submit-kmeans", n_clicks=0),
                html.Div(id="container-button-kmeans",),
                # DBSCAN related objects
                html.Div(
                    dcc.Input(
                        id="eps-dbscan",
                        type="number",
                        # value=0,
                        placeholder="eps",
                        step=0.1,
                        min=0,
                    )
                ),
                html.Div(
                    dcc.Input(
                        id="min_samples-dbscan",
                        type="number",
                        # value=0,
                        placeholder="min_samples",
                        min=1,
                    )
                ),
                html.Button("DBSCAN", id="submit-dbscan", n_clicks=0),
                html.Div(id="container-button-dbscan"),
            ],
            style={"width": "50%"},
        ),
        dcc.Loading(type="default", children=[dcc.Graph(id="funnel-graph")]),
        dcc.Store(id="intermediate-df"),
        dcc.Store(id="intermediate-clusters"),
    ]
)


@app.callback(
    Output("slider_annotation", "children"),
    [Input("threshold-slider", "value")],
)
def display_value(value):
    return f"Threshold: {value}"


if __name__ == "__main__":
    app.run_server(host="localhost", port="9999", debug=True)
