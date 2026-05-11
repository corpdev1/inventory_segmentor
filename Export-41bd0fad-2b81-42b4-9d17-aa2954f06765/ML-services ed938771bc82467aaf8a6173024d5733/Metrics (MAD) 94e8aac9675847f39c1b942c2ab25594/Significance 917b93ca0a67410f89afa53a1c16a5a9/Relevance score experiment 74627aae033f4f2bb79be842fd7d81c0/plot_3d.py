import matplotlib
import pickle
import matplotlib.pyplot as plt

with open('plot_3d.pickle', 'rb') as op_file:
    data_dict = pickle.load(op_file)
    dur_test_vec = data_dict[0]
    dev_test_vec = data_dict[1]
    op_prob_array = data_dict[2]

    min_op_prob = min(op_prob_array)
    max_op_prob = max(op_prob_array)

    num_intervals = 4

    marker_list = [".", "+", "x", "o"]

    interval_size = (max_op_prob - min_op_prob)/num_intervals

    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')

    interval_min = min_op_prob
    interval_max = min_op_prob + interval_size

    for cur_interval in range(num_intervals):
        select_inds = (interval_min < op_prob_array) & (op_prob_array < interval_max)
    
        plot_dur = dur_test_vec[select_inds]
        plot_dev = dev_test_vec[select_inds]
        plot_op_prob = op_prob_array[select_inds]
 
        ax.scatter(plot_dur, plot_dev, plot_op_prob, marker=marker_list[cur_interval])

        interval_min = interval_max
        interval_max = interval_min + interval_size

    plt.show()
