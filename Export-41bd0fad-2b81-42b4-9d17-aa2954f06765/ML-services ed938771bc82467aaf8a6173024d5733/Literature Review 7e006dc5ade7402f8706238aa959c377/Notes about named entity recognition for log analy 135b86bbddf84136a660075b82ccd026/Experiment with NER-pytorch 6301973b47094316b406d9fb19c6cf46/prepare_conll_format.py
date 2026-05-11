import glob
import json
import random
import string
import tqdm
import zipfile


def unzip_file(path):
    archive = zipfile.ZipFile(path, 'r')
    result = []
    for fileset in archive.filelist:
        data = archive.read(fileset)
        lines = data.decode().splitlines()
        data = [json.loads(line) for line in lines]
        result.extend(data)
        data = None
    return result


path = ('/home/hari/data/affluences_s3/stashed_hourly/log/'
        '6040a96cdcc614001153fc55-docker/rabbitmqqueue_rabbitmq/2021/09/')

ne_list = ["@timestamp", "process_id", "loglevel"]

pick_list = ["timestamp_unix", "content"]
pick_list.extend(ne_list)

days_list = ['01']  # , '06', '07']

files = []

for cur_day in days_list:
    cur_files = glob.glob(path + cur_day + '/' + '/**/**/**.zip', recursive=True)

    print(f"Number of files {len(cur_files)}")

    files.extend(cur_files)

data = []
for file in tqdm.tqdm(files):
    data.extend(unzip_file(file))

log = []
error = []

train_file = open("train_iob2.txt", "w")
dev_file = open("dev_iob2.txt", "w")
test_file = open("test_iob2.txt", "w")

total_size = 40000
train_size = 0
dev_size = 0
test_size = 0

for value in tqdm.tqdm(data[:total_size]):
    try:
        value_list = []
        '''
        for pick_key in pick_list:
            pick_value = value[pick_key]
            # special processing for 6040a96cdcc614001153fc55-docker/rabbitmqqueue_rabbitmq/
            # transform "2021-09-01T00:00:00.023Z" to "2021-09-01 00:00:00.023"
            if pick_key == "@timestamp":
                pick_value.replace("T", " ")
                pick_value.replace("Z", "")
            value_list.append(pick_value)
        '''
        value_tuple = tuple(value_list)
        token_list = value["message"].split(" ")

        ts_token_list = ['dummy-date', 'dummy-time']
        if "@timestamp" in value:
            ts_value = value["@timestamp"]
            ts_value = ts_value.replace("T", " ")
            ts_value = ts_value.replace("Z", "")
            ts_token_list = ts_value.split(" ")
            if len(ts_token_list) != 2:
                print("Number of tokens in time stamp entity is not as expected.")
                print(value["message"])
                continue
            if ts_token_list[0] in token_list:
                ts_pos_list = [i for i, x in enumerate(token_list) if token_list[i] == ts_token_list[0]
                               and token_list[i+1] == ts_token_list[1]]  # token_list.index(ts_token_list[0])
                ts_sec_pos_list = [i for i, x in enumerate(token_list) if token_list[i] == ts_token_list[1]]
                if len(ts_pos_list) == len(ts_sec_pos_list):
                    diff_pos = [j - i for i, j in zip(ts_pos_list, ts_sec_pos_list)]
                    if sum(diff_pos) != len(ts_pos_list):
                        print("Not all date and time strings are present next to each other.")
                        continue
                else:
                    print("Not all date and time strings are present as pairs.")
                    continue
            else:
                ts_pos_list = [-1]
                ts_sec_pos_list = [-1]

        pid_token_str = "my_dummy_pid_token_str"
        if "process_id" in value:
            pid_token_list = value["process_id"].split(" ")
            if len(pid_token_list) != 1:
                print("Number of tokens in process id entity is not as expected.")
                print(value["message"])
                continue
            else:
                pid_token_str = "<" + pid_token_list[0] + ">"

        loglevel_token_str = "my_dummy_loglevel_token_str"
        if "loglevel" in value:
            loglevel_token_list = value["loglevel"].split(" ")
            if len(loglevel_token_list) != 1:
                print("Number of tokens in log level entity is not as expected.")
                print(value["message"])
                continue
            else:
                loglevel_token_str = "[" + loglevel_token_list[0] + "]"

        log.append(0)
        ts_pos = -1
        ts_second = -1
        pid_pos = -1
        loglevel_pos = -1

        if pid_token_str in token_list:
            pid_pos_list = [i for i, x in enumerate(token_list) if token_list[i] == pid_token_str]  # token_list.index(pid_token_str)
        else:
            pid_pos_list = [-1]

        if loglevel_token_str in token_list:
            loglevel_pos_list = [i for i, x in enumerate(token_list) if token_list[i] == loglevel_token_str]  # token_list.index(loglevel_token_str)
        else:
            loglevel_pos_list = [-1]

        op_pick = random.uniform(0, 1)

        if op_pick <= 0.8:
            op_file = train_file
            train_size += 1
        elif 0.8 < op_pick < 0.9:
            op_file = dev_file
            dev_size += 1
        else:
            op_file = test_file
            random.shuffle(token_list)
            if ts_token_list[0] in token_list and ts_token_list[1] in token_list:
                ts_ent_1_pos = token_list.index(ts_token_list[0])
                ts_ent_2_pos = token_list.index(ts_token_list[1])
                if ts_ent_2_pos != ts_ent_1_pos + 1:
                    if ts_ent_1_pos != len(token_list) - 1:
                        token_temp = token_list[ts_ent_1_pos + 1]
                        token_list[ts_ent_1_pos + 1] = ts_token_list[1]
                        token_list[ts_ent_2_pos] = token_temp
                    else:
                        token_temp = token_list[ts_ent_1_pos-1]
                        token_list[ts_ent_1_pos-1] = ts_token_list[0]
                        token_list[ts_ent_1_pos] = ts_token_list[1]
                        token_list[ts_ent_2_pos] = token_temp
                ts_pos_list = [i for i, x in enumerate(token_list) if token_list[i] == ts_token_list[0]
                               and token_list[i+1] == ts_token_list[1]]  # token_list.index(ts_token_list[0])
                ts_sec_pos_list = [i for i, x in enumerate(token_list) if token_list[i] == ts_token_list[1]]
            if pid_token_str in token_list:
                pid_pos_list = [i for i, x in enumerate(token_list) if token_list[i] == pid_token_str]
            if loglevel_token_str in token_list:
                loglevel_pos_list = [i for i, x in enumerate(token_list) if token_list[i] == loglevel_token_str]
            '''
            orichar = "0123456789"
            newchar = "packetqwry"
            # num_char_dict = {'0': 'p', '1': 'a', '2': 'c', '3': 'k', '4': 'e', '5': 't', '6': 'q', '7': 'w', '8': 'r', '9': 'y'}
            for i, token in enumerate(token_list):
                if i in ts_pos_list:
                    token_list[i] = token.translate({ord(x): y for (x, y) in zip(orichar, newchar)})
                    ts_second = i + 1
                elif i == ts_second:
                    token_list[i] = token.translate({ord(x): y for (x, y) in zip(orichar, newchar)})
            '''
            test_size += 1

        # IOBES
        '''
        for i, token in enumerate(token_list):
            if i in ts_pos_list:
                op_file.write(f"{token} B-TS\n")
                ts_second = i + 1
            elif i == ts_second:
                op_file.write(f"{token} E-TS\n")
            elif i in pid_pos_list:
                op_file.write(f"{token} S-PID\n")
            elif i in loglevel_pos_list:
                op_file.write(f"{token} S-LL\n")
            else:
                op_file.write(f"{token} O\n")
        '''
        # IOB2
        for i, token in enumerate(token_list):
            if i in ts_pos_list:
                op_file.write(f"{token} B-TS\n")
                # ts_second = i + 1
            elif i in ts_sec_pos_list:
                op_file.write(f"{token} I-TS\n")
            elif i in pid_pos_list:
                op_file.write(f"{token} B-PID\n")
            elif i in loglevel_pos_list:
                op_file.write(f"{token} B-LL\n")
            else:
                op_file.write(f"{token} O\n")

        op_file.write("\n")

    except KeyError:
        error.append(value)
print(f"Number of log lines: {len(log)}. Train: {train_size}. Dev: {dev_size}. Test: {test_size}")
train_file.close()
dev_file.close()
test_file.close()

# log = sorted(log, key=lambda x: float(x[0]))
# timestamp, logs = zip(*log)
