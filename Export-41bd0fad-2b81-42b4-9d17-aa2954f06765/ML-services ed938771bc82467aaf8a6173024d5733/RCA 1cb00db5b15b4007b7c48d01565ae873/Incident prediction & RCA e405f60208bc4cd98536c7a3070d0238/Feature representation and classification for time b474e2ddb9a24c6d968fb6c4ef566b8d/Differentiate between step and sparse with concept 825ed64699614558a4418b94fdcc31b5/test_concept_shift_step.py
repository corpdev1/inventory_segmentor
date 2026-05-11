from datetime import datetime
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from random import randint
from random import random
from random import seed
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import RidgeClassifierCV
from sktime.transformations.panel.rocket import Rocket
from sktime.transformations.panel.shapelets import ContractedShapeletTransform
import time

seed(datetime.now())

num_class = 2

sparse_data = []
step_data = []

ts_len = 300
num_samples = 400

# sparse model
noise_range = 0.5
sparse_low = 4
sparse_high = 10
sparse_prob = [0.01, 0.05]  # data with different percentage of sparsity

# step data
step_prob = [0.1]  # data with different frequencies in step occurence
step_range = 10

train_test_ratio = 0.5

for ind_sample in range(num_samples):
    indices_ts = np.arange(0, ts_len)

    # sparse data
    sparse_sample = np.array([sparse_low + random()*(sparse_high - sparse_low) if random() < sparse_prob[0] \
                           else random()*noise_range for _ in range(ts_len)])

    concept_shift_pt = int(random()*ts_len)
    concept_shift_level = random()*(sparse_high - sparse_low)
    cur_sample = []

    # TODO: More Pythonic way to do it?
    if random() < 0.5:
        for ind, sparse_val in enumerate(sparse_sample):
            if ind > concept_shift_pt:
                cur_sample.append(sparse_val + concept_shift_level)
            else:
                cur_sample.append(sparse_val)
    else:
        for ind, sparse_val in enumerate(sparse_sample):
            if ind < concept_shift_pt:
                cur_sample.append(sparse_val + concept_shift_level)
            else:
                cur_sample.append(sparse_val)

    sparse_data.append(np.array(cur_sample))

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

    step_data.append(np.array(cur_sample))

train_ind = []
test_ind = []

for cur_ind in range(num_samples):
    if random() < train_test_ratio:
        train_ind.append(cur_ind)
    else:
        test_ind.append(cur_ind)

X_train_list = []
X_test_list = []
y_train_list = []
y_test_list = []

for cur_ind in train_ind:
    X_train_list.append([sparse_data[cur_ind]])
    y_train_list.append(0)
    X_train_list.append([step_data[cur_ind]])
    y_train_list.append(1)

for cur_ind in test_ind:
    X_test_list.append([sparse_data[cur_ind]])
    y_test_list.append(0)
    X_test_list.append([step_data[cur_ind]])
    y_test_list.append(1)

X_train = pd.DataFrame.from_records(X_train_list)
X_test = pd.DataFrame.from_records(X_test_list)

y_train = np.array(y_train_list)
y_test = np.array(y_test_list)

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

for i_class in range(num_class):
    if i_class not in misclass_cases:
        misclass_cases[i_class] = []
    else:
        for j_class in range(num_class):
            if i_class != j_class:
                num_cases = 0
                for mis_case in misclass_cases[i_class]:
                    if mis_case[1] == j_class:
                        num_cases += 1
                print("Class {} classified as {}, {} times.".format(i_class, j_class, num_cases))

print("Score: {}, Number of misclassified sparse + concept shift: {}, step: {}, Total number of cases {}.".format(rocket_score, \
      len(misclass_cases[0]), len(misclass_cases[1]), len(y_test)))

'''
fig = plt.figure()
ax = fig.add_subplot(111)

for cur_sample in range(num_samples):
    plt.plot(sparse_data[cur_sample])

plt.show()

fig = plt.figure()
ax = fig.add_subplot(111)

for cur_sample in range(num_samples):
    plt.plot(step_data[cur_sample])

plt.show()
'''
# Using Shapelet Transform

# How long (in minutes) to extract shapelets for.
# This is a simple lower-bound initially;
# once time is up, no further shapelets will be assessed.
time_contract_in_mins = 1

# The initial number of shapelet candidates to assess per training series.
# If all series are visited and time remains on the contract then another
# pass of the data will occur.
initial_num_shapelets_per_case = 10

output_list_shapelet = []

pipeline = Pipeline(
    [
        (
            "st",
            ContractedShapeletTransform(
                time_contract_in_mins=time_contract_in_mins,
                num_candidates_to_sample_per_case=initial_num_shapelets_per_case,
                verbose=False,
            ),
        ),
        ("rf", RandomForestClassifier(n_estimators=100)),
    ]
)

pipeline.fit(X_train, y_train)

shapelet_score = pipeline.score(X_test, y_test)
y_shapelet = pipeline.predict(X_test)
test_time = time.time() - start_test

misclassified_cases = {}

for index, (cur_test, cur_shapelet) in enumerate(zip(y_test, y_shapelet)):
    if cur_test != cur_shapelet:
        if cur_test in misclass_cases:
            misclass_cases[cur_test].append((index, cur_shapelet))
        else:
            misclass_cases[cur_test] = [(index, cur_shapelet)]

for i_class in range(num_class):
    if i_class not in misclass_cases:
        misclass_cases[i_class] = []
    else:
        for j_class in range(num_class):
            if i_class != j_class:
                num_cases = 0
                for mis_case in misclass_cases[i_class]:
                    if mis_case[1] == j_class:
                        num_cases += 1
                        fig = plt.figure()
                        ax = fig.add_subplot(111)

                        plt.plot(X_test.iloc[mis_case[0]][0])

                        plt.savefig(str(i_class) + 'as' + str(j_class) + '_' + str(num_cases) + '.png')

                        plt.close(fig=fig)
                print("Class {} classified as {}, {} times.".format(i_class, j_class, num_cases))

print("Score: {}, Number of misclassified sparse + concept shift: {}, step: {}, Total number of cases {}.".format(shapelet_score, \
      len(misclass_cases[0]), len(misclass_cases[1]), len(y_test)))

time.sleep(1)