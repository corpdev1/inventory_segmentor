#!/usr/bin/env python
# coding: utf-8

# In[1]:


from pymongo import MongoClient, ASCENDING, DESCENDING
import pandas as pd
import numpy as np
import time
import random
from pprint import pprint
import sys


# In[2]:


# Create the client
client = MongoClient("localhost", 27017)


# In[3]:


# Connect to our database
db = client["SeriesDB"]

# Fetch our series collection
series_collection = db["series"]


# ## Inserting Documents

# In[4]:


# Imports truncated for brevity


def insert_document(collection, data):
    """ Function to insert a document into a collection and
    return the document's id.
    """
    if isinstance(data, list):
        series_collection.insert_many(data)
    else:
        return collection.insert_one(data).inserted_id


# In[5]:


new_show = {"name": "FRIENDS", "year": 1994}
# print(insert_document(series_collection, new_show))


# ## Retrieving Documents

# In[6]:


# Imports and previous code truncated for brevity


def find_document(collection, elements, multiple=False):
    """ Function to retrieve single or multiple documents from a provided
    Collection using a dictionary containing a document's elements.
    """
    if multiple:
        results = collection.find(elements)
        return [r for r in results]
    else:
        return collection.find_one(elements)


# In[7]:


# [r.get('_id') for r in series_collection.find({"release_year": {"$gt": 20}})]


# In[8]:


# result = find_document(series_collection, {'name': 'FRIENDS'})
# print(result)


# In[9]:


# result = find_document(series_collection, {"year": 1994}, multiple=True)
# print(result)


# In[10]:


# series_collection.count_documents({"year": {"$gt": 20}})


# ## Updating Documents

# In[11]:


# Imports and previous code truncated for brevity


def update_document(collection, query_elements, new_values):
    """ Function to update a single document in a collection.
    """
    collection.update_one(query_elements, {"$set": new_values})


# In[12]:


# new_show = {
#     "name": "FRIENDS",
#     "year": 1995
# }
# id_ = insert_document(series_collection, new_show)


# In[13]:


# update_document(series_collection, {'_id': id_}, {'name': 'F.R.I.E.N.D.S'})


# In[14]:


# result = find_document(series_collection, {'_id': id_})
# print(result)


# In[15]:


# find_document(series_collection, {'name': 'F.R.I.E.N.D.S', 'year': '1994'}, multiple=True)


# ## Deleting Documents


def delete_document(collection, query):
    """ Function to delete a single document from a collection.
    """
    collection.delete_one(query)


# # Load helpers

# ### Generate data


netflix = pd.read_csv("netflix_titles.csv")


netflix_dict = netflix.fillna(method="ffill").to_dict(orient="index")
total_movies = len(netflix)
# for i in range(1, 6):
#     pprint(i)
#     pprint(netflix_dict[i])


def generate_data(n):
    idx_list = []
    for _ in range(n):
        idx = random.randint(1, total_movies - 1)
        if idx not in set(idx_list):
            idx_list.append(idx)
        output = list(map(netflix_dict.get, idx_list))
        for movie in output:
            movie["show_id"] = random.randint(1, 10000000)
    return output


def generate_data_det(n):
    idx_list = [idx for idx in range(1, n + 1)]
    output = list(map(netflix_dict.get, idx_list))
    for movie in output:
        movie["show_id"] = random.randint(1, 10000000)
    return output


# ### Insert data


import string


def get_random_string(length):
    letters = string.ascii_lowercase
    result_str = "".join(random.choice(letters) for i in range(length))
    #     print("Random string of length", length, "is:", result_str)
    return result_str


# get_random_string(5)


def insert_data(data, load_type):
    try:
        for current_data in data:
            current_data["_id"] = get_random_string(5) + str(random.randint(1, 1e15))
            insert_document(series_collection, current_data)
            time.sleep(0.2)
        print(f"Inserted ids : {len(data)}")
        time.sleep(load_type)
    except Exception as e:
        pprint(f"Error occured while inserting to the db: {e}")


def insert_data_det(data, sleep_between_queries):
    try:
        for current_data in data:
            current_data["_id"] = get_random_string(5) + str(random.randint(1, 1e15))
            insert_document(series_collection, current_data)
            time.sleep(sleep_between_queries)
        print(f"Inserted ids : {len(data)}")
        # time.sleep(load_type)
    except Exception as e:
        print(f"Error occured while inserting to the db: {e}")


# In[49]:


# data = generate_data(20)
# insert_data(data, load_type=1)


# ### Delete data

# In[53]:


def delete_data(n, load_type):
    year = random.randint(netflix.release_year.min(), netflix.release_year.max())
    _ids = [
        r.get("_id") for r in series_collection.find({"release_year": {"$gt": year}})
    ][:n]
    for current_id in _ids:
        series_collection.delete_one({"_id": current_id})
        time.sleep(0.1)
    print(f"Deleted ids : {len(_ids)}")
    time.sleep(load_type)


def delete_data_det(n, sleep_between_queries):
    # year = random.randint(netflix.release_year.min(), netflix.release_year.max())
    _ids = [r.get("_id") for r in series_collection.find({"release_year": {"$gt": 0}})][
        :n
    ]
    for current_id in _ids:
        series_collection.delete_one({"_id": current_id})
        time.sleep(sleep_between_queries)
    print(f"Deleted ids : {len(_ids)}")
    # time.sleep(load_type)


# In[54]:


# delete_data(10, load_type=1)


# ### Modify data

# In[55]:


def modify_data(n, load_type):
    year = random.randint(netflix.release_year.min(), netflix.release_year.max())
    _ids = [
        r.get("_id") for r in series_collection.find({"release_year": {"$gt": year}})
    ][:n]
    for current_id in _ids:
        update_document(
            series_collection, {"_id": current_id}, {"show_id": random.randint(1, 1e5)}
        )
        time.sleep(0.1)
    print(f"Updated ids : {len(_ids)}")
    time.sleep(load_type)


def modify_data_det(n, sleep_between_queries):
    # year = random.randint(netflix.release_year.min(), netflix.release_year.max())
    _ids = [r.get("_id") for r in series_collection.find({"release_year": {"$gt": 0}})][
        :n
    ]
    for current_id in _ids:
        update_document(
            series_collection, {"_id": current_id}, {"show_id": random.randint(1, 1e5)}
        )
        time.sleep(sleep_between_queries)
    print(f"Updated ids : {len(_ids)}")
    # time.sleep(load_type)


# In[57]:


# modify_data(n=10, load_type=1)


# In[33]:


# result = find_document(series_collection, {"show_id": 777}, multiple=True)
# print([t.get("title") for t in result])


# ## Sort data

# In[34]:


def gentle_sort(load_type):
    start_year = random.randint(1925, 1975)
    end_year = random.randint(1975, 2020)

    cursor = series_collection.find(
        {"release_year": {"$gte": start_year, "$lt": end_year}}
    ).sort([("release_year", ASCENDING), ("title", DESCENDING)])

    res = [(r["release_year"], r["title"]) for r in cursor]
    print(f"Sorted {len(res)} elements")
    time.sleep(load_type)


# In[35]:


def big_sort(load_type):
    cursor = series_collection.find({"release_year": {"$gt": 0}}).sort(
        [("release_year", ASCENDING), ("title", DESCENDING)]
    )
    res = [(r["release_year"], r["title"]) for r in cursor]
    print(f"Sorted {len(res)} elements")
    time.sleep(load_type)


def generate():

    normal_load = 0.5
    iteration = 0
    switch = True
    current_load = normal_load
    period_switch = 10

    # In[39]:

    # while True:
    # print("\nIteration: ", iteration)
    if iteration % period_switch == 0:
        current_load = normal_load if switch else normal_load / 10
        switch = not switch
    iter_load = current_load + random.random() / 10
    # print(f"Current load = {current_load}, switch = {switch}, iter_load = {iter_load}")
    num_doc = series_collection.count_documents({"release_year": {"$gt": 0}})
    # print("Total rows: ", num_doc)
    if num_doc < 10:
        new_data = random.randint(100, 300)
        data = generate_data(new_data)
        insert_data(data)
    elif num_doc > 6000:
        delete_data(n=4000, load_type=0)
    else:
        flip_coin = random.randint(1, 5)
        if flip_coin == 1:
            print(f"Insert")
            new_data = random.randint(1, 200)
            data = generate_data(new_data)
            insert_data(data, load_type=iter_load)
        elif flip_coin == 2:
            print(f"Delete")
            num_data = random.randint(10, 100)
            delete_data(n=num_data, load_type=iter_load)
        elif flip_coin == 3:
            print(f"Gentle sort")
            gentle_sort(load_type=iter_load)
        elif flip_coin == 4:
            print(f"Big sort")
            big_sort(load_type=iter_load)
        else:
            print(f"Modify")
            num_data = random.randint(5, 50)
            modify_data(n=num_data, load_type=iter_load)
    iteration += 1


import threading
import time


class Job(threading.Thread):
    def __init__(self, n, *args, **kwargs):
        super(Job, self).__init__(*args, **kwargs)
        self.__flag = threading.Event()  # The flag used to pause the thread
        self.__flag.set()  # Set to True
        self.__running = threading.Event()  # Used to stop the thread identification
        self.__running.set()  # Set running to True
        self.n = n

    def run(self):
        while self.__running.isSet():
            self.__flag.wait()  # return immediately when it is True, block until the internal flag is True when it is False
            # print(time.time())
            print("\nWorker ", self.n)
            generate()
            time.sleep(1)

    def pause(self):
        self.__flag.clear()  # Set to False to block the thread

    def resume(self):
        self.__flag.set()  # Set to True, let the thread stop blocking

    def stop(self):
        self.__flag.set()  # Resume the thread from the suspended state, if it is already suspended
        self.__running.clear()  # Set to False


def bad_script():
    ps = [Job(i) for i in range(1, 101)]

    # duration of light mode in seconds
    time_light = 10

    # launch/pause time between processes in the loop in seconds
    launch_pause = 0.01

    # duration of heavy mode in seconds
    time_heavy = 5

    print("\n=== We start Process #1 now ===\n")
    ps[0].start()
    time.sleep(time_light)

    print(f"\n=== We start other {len(ps) - 1} processes now ===\n")
    for p in ps[1:]:
        p.start()
        time.sleep(launch_pause)

    print("\n=== All processes are working now ===\n")
    time.sleep(time_heavy)

    print(f"\n=== We pause {len(ps) - 1} processes now ===\n")
    for p in ps[1:]:
        p.pause()
        time.sleep(launch_pause)

    print(f"\n=== We leave only Process #1 now for {time_light} sec. ===\n")
    time.sleep(time_light)

    print("\n=== We stop Process #1 now ===\n")
    ps[0].pause()
    print("\n=== Everything is stopped now ===\n")
    sys.exit()


def good_script():
    ps = [Job(i) for i in range(1)]

    # duration of light mode in seconds
    time_light = 10

    # launch/pause time between processes in the loop in seconds
    launch_pause = 0.01

    # duration of heavy mode in seconds
    time_heavy = 5

    print("\n=== We start Process #1 now ===\n")
    ps[0].start()
    time.sleep(time_light)


from datetime import datetime


def normal_behavior(sleep_btwn_qrs):
    data = generate_data_det(5)
    insert_data_det(data, sleep_between_queries=sleep_btwn_qrs)
    delete_data_det(n=5, sleep_between_queries=sleep_btwn_qrs)
    modify_data_det(n=5, sleep_between_queries=sleep_btwn_qrs)
    time.sleep(2)


def abnormal_behavior(sleep_btwn_qrs):
    data = generate_data_det(150)
    # modify_data_det(n=1, sleep_between_queries=sleep_btwn_qrs)
    # delete_data_det(n=1, sleep_between_queries=sleep_btwn_qrs)
    insert_data_det(data, sleep_between_queries=sleep_btwn_qrs)
    time.sleep(0.5)

def heavy_behavior(sleep_btwn_qrs):
    data = generate_data_det(1250)
    modify_data_det(n=1000, sleep_between_queries=sleep_btwn_qrs)
    delete_data_det(n=1250, sleep_between_queries=sleep_btwn_qrs)
    insert_data_det(data, sleep_between_queries=sleep_btwn_qrs)
    # time.sleep(2)


if __name__ == "__main__":
    # duration of normal behavior (in seconds)
    normal_duration = 30*60

    # duration of abnormal behavior (in seconds)
    abnormal_duration = 10*60

    # duration of heavy load (in seconds)
    heavy_duration = 10*60

    normal_iter = int(normal_duration / 10)
    abnormal_iter = int(abnormal_duration / 60)
    heavy_iter = int(heavy_duration / 11)

    print(f"\nNumber of iterations for each state:\n"
        f"Normal state: {normal_iter} iteration(s)\n"
        f"Abnormal state: {abnormal_iter} iteration(s)\n"
        f"Heavy load state: {heavy_iter} iteration(s)\n")

    sleep_normal = 0.5
    sleep_abnormal = 0.4
    sleep_heavy = 0.001

    i = 0
    print("\n=== Start normal behavior ===\n")
    normal_start_time = datetime.now()
    while True:
        start_time = datetime.now()
        normal_behavior(sleep_normal)
        i += 1
        # print("i = ", i)
        print(f"\nLoop {i} is done. [Time taken: {datetime.now() - start_time}]\n")
        if i == normal_iter:
            break
    normal_time = datetime.now() - normal_start_time

    print("\n=== Start abnormal behavior ===\n")
    abnormal_start_time = datetime.now()

    i = 0
    while True:
        start_time = datetime.now()
        abnormal_behavior(sleep_abnormal)
        i += 1
        # print("i = ", i)
        print(f"\nLoop {i} is done. [Time taken: {datetime.now() - start_time}]\n")
        if i >= abnormal_iter:
            break
    abnormal_time = datetime.now() - abnormal_start_time

    i = 0
    print("\n=== Start normal behavior again ===\n")
    normal_start_time = datetime.now()
    while True:
        start_time = datetime.now()
        normal_behavior(sleep_normal)
        i += 1
        # print("i = ", i)
        print(f"\nLoop {i} is done. [Time taken: {datetime.now() - start_time}]\n")
        if i >= normal_iter:
            break
    normal_time2 = datetime.now() - normal_start_time

    i = 0
    print("\n=== Start heavy load ===\n")
    heavy_start_time = datetime.now()
    while True:
        start_time = datetime.now()
        heavy_behavior(sleep_heavy)
        i += 1
        # print("i = ", i)
        print(f"\nLoop {i} is done. [Time taken: {datetime.now() - start_time}]\n")
        if i >= heavy_iter:
            break
    heavy_time = datetime.now() - heavy_start_time

    print(
        f"\nDone.\n[Time normal behavior (stage 1): {normal_time}]\n"
        f"[Time abnormal behavior: {abnormal_time}]\n"
        f"[Time normal behavior (stage 2): {normal_time2}]\n"
        f"[Time heavy load behavior: {heavy_time}]"
    )
