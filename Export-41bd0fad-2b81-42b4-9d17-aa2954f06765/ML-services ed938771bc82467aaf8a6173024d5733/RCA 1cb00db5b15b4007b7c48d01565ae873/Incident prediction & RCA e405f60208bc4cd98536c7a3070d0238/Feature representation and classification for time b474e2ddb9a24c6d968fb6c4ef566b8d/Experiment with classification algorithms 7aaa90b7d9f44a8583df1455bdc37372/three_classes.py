from datetime import datetime
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from random import randint
from random import random
from random import seed
from sklearn.linear_model import RidgeClassifierCV
from sktime.transformations.panel.rocket import Rocket
import time

seed(datetime.now())

num_class = 3

sparse_data = []
periodic_data = []
step_data = []
# noisy_step_data = []

ts_len = 300
num_samples = 100

# sparse model
noise_range = 0.5
sparse_low = 4
sparse_high = 10
sparse_prob = [0.01, 0.05]  # data with different percentage of sparsity

# periodic data
signal_period = [5, 13, 29]  # data with different time periods
signal_range_amp = 5
signal_min_amp = 1

# step data
step_prob = [0.1]  # data with different frequencies in step occurence
step_range = 10

train_test_ratio = 0.5

train_period_ind = []
test_period_ind = []

for ind_sample in range(num_samples):
    indices_ts = np.arange(0, ts_len)

    # sparse data
    cur_sample = [sparse_low + random()*(sparse_high - sparse_low) if random() < sparse_prob[0] else random()*noise_range \
                  for _ in range(ts_len)]

    sparse_data.append(cur_sample)

    # periodic data
    period_samp = randint(0, len(signal_period)-1)
    cur_sample = (signal_min_amp + random()*signal_range_amp)*np.sin((2 * np.pi / signal_period[period_samp]) * indices_ts + random()*np.pi)
    if period_samp == 1 or period_samp == 2:
        train_period_ind.append(ind_sample)
    else:
        test_period_ind.append(ind_sample)

    periodic_data.append(cur_sample)

    cur_sample = []

    # step_data
    for cur_ind in range(ts_len):
        if random() < step_prob[0]:
            cur_sample.append(randint(0, step_range))
        else:
            if not cur_sample:
                cur_sample.append(randint(0, step_range))
            else:
                cur_sample.append(cur_sample[-1])

    step_data.append(cur_sample)

train_ind = []
test_ind = []

for cur_ind in range(num_samples):
    if random() < train_test_ratio:
        train_ind.append(cur_ind)
    else:
        test_ind.append(cur_ind)

X_train_list = []
X_test_list = []
y_train = []
y_test = []

for cur_ind in train_ind:
    X_train_list.append([sparse_data[cur_ind]])
    y_train.append(0)
    X_train_list.append([periodic_data[cur_ind]])
    y_train.append(1)
    X_train_list.append([step_data[cur_ind]])
    y_train.append(2)

for cur_ind in test_ind:
    X_test_list.append([sparse_data[cur_ind]])
    y_test.append(0)
    X_test_list.append([periodic_data[cur_ind]])
    y_test.append(1)
    X_test_list.append([step_data[cur_ind]])
    y_test.append(2)

'''
for cur_ind in train_period_ind:
    X_train_list.append([periodic_data[cur_ind]])
    y_train.append(1)

for cur_ind in test_period_ind:
    X_test_list.append([periodic_data[cur_ind]])
    y_test.append(1)
'''

X_train = pd.DataFrame.from_records(X_train_list)
X_test = pd.DataFrame.from_records(X_test_list)

start_fit = time.time()
rocket = Rocket()  # by default, ROCKET uses 10,000 kernels
rocket.fit(X_train)
X_train_transform = rocket.transform(X_train)

classifier = RidgeClassifierCV(alphas=np.logspace(-3, 3, 10), normalize=True)
classifier.fit(X_train_transform, y_train)
fit_time = time.time() - start_fit

start_test = time.time()
X_test_transform = rocket.transform(X_test)

rocket_score = classifier.score(X_test_transform, y_test)
y_rocket = classifier.predict(X_test_transform)
conf_rocket = classifier.decision_function(X_test_transform)
test_time = time.time() - start_test

misclass_cases = {}

for index, (cur_test, cur_rocket) in enumerate(zip(y_test, y_rocket)):
    if cur_test != cur_rocket:
        if cur_test in misclass_cases:
            misclass_cases[cur_test].append((index, cur_rocket))
        else:
            misclass_cases[cur_test] = [(index, cur_rocket)]

for i_class in range(3):
    if i_class not in misclass_cases:
        misclass_cases[i_class] = []
    else:
        for j_class in range(3):
            if i_class != j_class:
                num_cases = 0
                for mis_case in misclass_cases[i_class]:
                    if mis_case[1] == j_class:
                        num_cases += 1
                print("Class {} classified as {}, {} times.".format(i_class, j_class, num_cases))

print("Score: {}, Number of misclassified sparse: {}, periodic: {}, step: {}, Total number of cases {}.".format(rocket_score, \
      len(misclass_cases[0]), len(misclass_cases[1]), len(misclass_cases[2]), len(y_test)))

fig = plt.figure()
ax = fig.add_subplot(111)

for cur_sample in range(num_samples):
    plt.plot(sparse_data[cur_sample])

plt.show()

fig = plt.figure()
ax = fig.add_subplot(111)

for cur_sample in range(num_samples):
    plt.plot(periodic_data[cur_sample])

plt.show()

fig = plt.figure()
ax = fig.add_subplot(111)

for cur_sample in range(num_samples):
    plt.plot(step_data[cur_sample])

plt.show()

time.sleep(1)