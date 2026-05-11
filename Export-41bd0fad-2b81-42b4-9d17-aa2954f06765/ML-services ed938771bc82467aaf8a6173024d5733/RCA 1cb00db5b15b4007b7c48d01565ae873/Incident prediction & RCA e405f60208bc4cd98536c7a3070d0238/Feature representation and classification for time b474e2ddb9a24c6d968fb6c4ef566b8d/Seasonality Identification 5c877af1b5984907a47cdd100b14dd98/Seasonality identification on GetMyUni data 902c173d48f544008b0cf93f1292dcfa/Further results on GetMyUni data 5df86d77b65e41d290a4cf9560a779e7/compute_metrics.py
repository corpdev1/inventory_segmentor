import os
import pickle
import time

# folder_name = '/home/hari/work/grok_time_series/mad/scripts/gmu_linux/results_602f799fad3c6f00114c1fb4-linux602f87ccad3c6f00114c1fc3_linux602f87ccad3c6f00114c1fc3/'
# folder_name = '/home/hari/work/grok_time_series/mad/scripts/gmu_linux/results_602f799fad3c6f00114c1fb4-linux602f88cdad3c6f00114c1fc5_linux602f88cdad3c6f00114c1fc5/'
# folder_name = '/home/hari/work/grok_time_series/mad/scripts/gmu_apache/results_602f799fad3c6f00114c1fb4-linux602f87ccad3c6f00114c1fc3_apache2305b637e1714119/'
# folder_name = '/home/hari/work/grok_time_series/mad/scripts/gmu_mysql/results_602f799fad3c6f00114c1fb4-linux60377277ad3c6f00114cd4de_mysql731599c045855161/'
folder_name = '/home/hari/work/grok_time_series/mad/scripts/gmu_mysql/results_602f799fad3c6f00114c1fb4-linux602f88cdad3c6f00114c1fc5_mysql8f8fd6c89154d836/'

filename_list = [folder_name + each for each in os.listdir(folder_name) if each.endswith('.pickle')]

op_dict = {}

for cur_filename in filename_list:
    with open(cur_filename, 'rb') as pickle_file:
        cur_dict = pickle.load(pickle_file)
        for key, value in cur_dict.items():
            op_dict[key] = value

gt_dict = {}

with open(folder_name + 'time_period_label.txt') as gt_file:
    metric_list = gt_file.read().splitlines()

    for cur_metric in metric_list:
        metric_name, time_period = cur_metric.split()

        time_period_list = time_period.split(',')

        time_period_list = [int(x) for x in time_period_list]

        gt_dict[metric_name] = time_period_list

fn_cnt = 0
fn_cases = []
fp_cnt_list = []
total_instances_cnt = len(gt_dict)
nonperiodic_instances_cnt = 0

for metric_name, op_time_periods in op_dict.items():
    if metric_name in gt_dict:
        gt_time_periods = gt_dict[metric_name]

        for gt_time_period in gt_time_periods:
            if gt_time_period > 0:
                hit_flag = False

                for op_time_period in op_time_periods:
                    if abs(op_time_period - gt_time_period)/gt_time_period < 0.1:
                        hit_flag = True

                if not hit_flag:
                    fn_cases.append(metric_name)
                    fn_cnt += 1
            else:
                nonperiodic_instances_cnt += 1

        fp_cnt = 0

        for op_time_period in op_time_periods:
            fp_flag = True

            for gt_time_period in gt_time_periods:
                if abs(op_time_period - gt_time_period)/op_time_period < 0.1:
                    fp_flag = False

            if fp_flag:
                fp_cnt += 1

        fp_cnt_list.append(fp_cnt)

fp_instances_cnt = sum([fp_cnt > 0 for fp_cnt in fp_cnt_list])

print(folder_name)
print('Total instances: {}. Periodic instances: {}, Nonperiodic instances: {}, False negatives (misses): {}. Total false'
      ' positives: {}. Instances with false positives: {}'.format(total_instances_cnt, total_instances_cnt - nonperiodic_instances_cnt,
      nonperiodic_instances_cnt, fn_cnt, sum(fp_cnt_list), fp_instances_cnt))
print('False negatives')
for fn_case in fn_cases:
    print(fn_case)

time.sleep(1)