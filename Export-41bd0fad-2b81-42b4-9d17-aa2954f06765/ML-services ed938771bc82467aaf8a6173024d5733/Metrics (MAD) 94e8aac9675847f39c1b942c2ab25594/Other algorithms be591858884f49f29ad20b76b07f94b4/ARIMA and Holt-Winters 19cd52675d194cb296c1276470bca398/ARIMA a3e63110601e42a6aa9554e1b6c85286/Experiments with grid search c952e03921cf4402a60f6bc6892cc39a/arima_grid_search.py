import csv
import numpy as np
from math import sqrt
import matplotlib.pyplot as plt
import pandas as pd
from sklearn.metrics import mean_squared_error
from statsmodels.tsa.arima.model import ARIMA
import time
import warnings
warnings.filterwarnings("ignore")


# evaluate an ARIMA model for a given order (p,d,q)
# approach where model is fit for each new sample
def evaluate_arima_model(value_list, arima_order):
    # prepare training dataset
    train_size = int(len(value_list) * 0.66)
    train, test = value_list[0:train_size], value_list[train_size:]
    history = [x for x in train]
    # make predictions
    predictions = list()
    for t in range(len(test)):
        model = ARIMA(history, order=arima_order)
        model_fit = model.fit()
        yhat = model_fit.forecast()[0]
        predictions.append(yhat)
        history.append(test[t])
    # calculate out of sample error
    error = mean_squared_error(test, predictions)
    return error


# evaluate an ARIMA model for a given order (p,d,q)
# approach where model based on training data is reused
def evaluate_arima_model_filter(value_list, arima_order):
    # prepare training dataset
    train_size = int(len(value_list) * 0.33)
    train, test = value_list[0:train_size], value_list[train_size:]

    # make predictions
    start_time = time.perf_counter()
    training_mod = ARIMA(train, order=arima_order)
    training_res = training_mod.fit()
    fit_time = time.perf_counter() - start_time

    start_time = time.perf_counter()
    mod = ARIMA(value_list, order=arima_order)
    res = mod.filter(training_res.params)
    predictions = res.predict()
    predictions = predictions[train_size:len(value_list)]
    prediction_time = time.perf_counter() - start_time

    print("Fit time {} seconds. Prediction time {} seconds".format(fit_time, prediction_time))

    # calculate out of sample error
    error = mean_squared_error(test, predictions)
    return error


# evaluate combinations of p, d and q values for an ARIMA model
def evaluate_models(value_list, p_values, d_values, q_values):
    best_score, best_cfg = float("inf"), None
    for p in p_values:
        for d in d_values:
            for q in q_values:
                order = (p, d, q)
                try:
                    mse = evaluate_arima_model_filter(value_list, order)
                    if mse < best_score:
                        best_score, best_cfg = mse, order
                    print('ARIMA%s MSE=%.8f' % (order, mse))
                except:
                    continue
    print('Best ARIMA%s MSE=%.8f' % (best_cfg, best_score))


with open('mysql_questions.csv') as csv_file:
    csv_reader = csv.reader(csv_file, delimiter=',')
    line_count = 0

    for row in csv_reader:
        if line_count == 0:
            value_list = [float(x) for x in row]
        elif line_count == 1:
            timestamp_list = [int(x) for x in row]
        elif line_count == 2:
            anom_list = row
        line_count += 1

value_list = value_list[:30240]  # 1 day = 1440, 1 week = 10080, 3 weeks = 30240

max_value = max(value_list)
min_value = min(value_list)

value_list = [(x - min_value)/(max_value - min_value) for x in value_list]

value_series = pd.Series(value_list)

pd.plotting.autocorrelation_plot(value_series)
plt.savefig('acf.png')
plt.close()

# evaluate parameters
arima_p = [0, 5, 10, 15, 20, 25, 30]
arima_d = range(0, 6)
arima_q = range(0, 6)

# fit model on entire data
'''
model = ARIMA(value_series, order=(arima_p, arima_d, arima_q))
model_fit = model.fit()
# summary of fit model
print(model_fit.summary())
# line plot of residuals
residuals = pd.DataFrame(model_fit.resid)
residuals.plot()
plt.savefig('residuals.png')
# density plot of residuals
residuals.plot(kind='kde')
plt.savefig('residuals_kde.png')
# summary stats of residuals
print(residuals.describe())
'''

evaluate_models(value_list, arima_p, arima_d, arima_q)
