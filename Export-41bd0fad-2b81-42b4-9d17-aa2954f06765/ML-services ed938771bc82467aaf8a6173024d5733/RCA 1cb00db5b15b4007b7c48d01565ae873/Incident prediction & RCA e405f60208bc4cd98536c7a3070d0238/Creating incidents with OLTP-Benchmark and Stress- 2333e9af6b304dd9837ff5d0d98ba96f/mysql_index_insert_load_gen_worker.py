#!/usr/bin/env python
# coding: utf-8

import mysql.connector as connector
from mysql.connector.pooling import MySQLConnectionPool
import sys

import pandas as pd
import numpy as np
import time
import random
from pprint import pprint
import string
import threading
import time
import sys

mydb = connector.connect(
  host="localhost",
  user="root",
  password="MySQL",
  database="series",
  auth_plugin='mysql_native_password'
)

mydb.autocommit = True

mycursor = mydb.cursor(buffered=True)

netflix = pd.read_csv("netflix_titles.csv")

netflix_dict = netflix.fillna(method='ffill').to_dict(orient="index")
total_movies = len(netflix)

time_period = 600

def insert_record(mycursor, record_dict):
    add_record = ("""INSERT INTO movies """
                  """(show_id, type, title, director, cast, country, date_added, release_year, rating, duration, listed_in, description, _id) """
                  """VALUES ({}, "{}", "{}", "{}", "{}", "{}", "{}", {}, "{}", "{}", "{}", "{}", "{}")""")

    record_dict['title'] = record_dict.get('title', 'Pup Star: Better 2Gether').replace('"', '')
    record_dict['director'] = record_dict.get('director', 'Robert Vince').replace('"', '')
    record_dict['cast'] = record_dict.get('cast', 'Kaitlyn Maher, Obba Babatundé, Lombardo Boyar, Molly Burnett, Chris Coppola, Reggie De Leon, David DeLuise, Matty Finochio, Josh Flitter, Benjamin Flores Jr.').replace('"', '')
    record_dict['listed_in'] = record_dict.get('listed_in', 'Children & Family Movies, Comedies').replace('"', '')
    record_dict['description'] = record_dict.get('description', 'Returning Pup Star champ Tiny has her Yorkie paws full after an evil rival replaces her with street dog Scrappy during the national competition.').replace('"', '')
    data_record = (record_dict.get('show_id'), record_dict.get('type', 'Movie'), record_dict['title'],
                   record_dict['director'], record_dict['cast'], record_dict.get('country', 'Canada'),
                   record_dict.get('date_added', 'October 28, 2017'), record_dict.get('release_year', 2017), record_dict.get('rating', 'PG'),
                   record_dict.get('duration', '93 min'), record_dict['listed_in'], record_dict['description'],
                   record_dict.get('_id', get_random_string(5) + str(random.randint(1, 1e15))))

    # Insert new record
    insert_query = add_record.format(*data_record)
    mycursor.execute(insert_query)


def insert_data(mycursor, data, load_type=0.5):
    try:
        for current_data in data:
            insert_record(mycursor, current_data)
            time.sleep(0.2)
        print(f"Inserted ids : {len(data)}")
        time.sleep(load_type)
    except Exception as e:
        pprint(f"Error occurred while inserting to the db: {e}")


def delete_data(mycursor, n, load_type):
    year = random.randint(netflix.release_year.min(), netflix.release_year.max())
    select_records = "SELECT _id FROM movies WHERE release_year > {}".format(year)
    mycursor.execute(select_records)
    _ids = mycursor.fetchall()[:n]

    for current_id in _ids:
        # mycursor.execute("START TRANSACTION")
        delete_query = "DELETE FROM movies WHERE _id = '{}'".format(current_id[0])
        mycursor.execute(delete_query)
        # mycursor.execute("COMMIT")

        time.sleep(0.1)
    print(f"Deleted ids : {len(_ids)}")
    time.sleep(load_type)


def get_random_string(length):
    letters = string.ascii_lowercase
    result_str = ''.join(random.choice(letters) for i in range(length))
#     print("Random string of length", length, "is:", result_str)
    return result_str


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


def generate(mycursor):
    new_data = random.randint(1, 200)
    data = generate_data(new_data)
    insert_data(mycursor, data)


if __name__ == "__main__":

    start_time = time.time()
    # create_index = True

    while True:
        generate(mycursor)
        time_elapsed = time.time() - start_time

        if time_elapsed < time_period:
            time.sleep(1)
        else:
            mycursor.execute("SELECT COUNT(*) FROM movies FOR UPDATE")
            num_row = mycursor.fetchone()[0]
            print("Total rows at time {} = {}".format(time_elapsed, num_row))

            num_to_remove = min(5000, num_row)
            del_start_time = time.time()
            delete_data(mycursor, n=num_to_remove, load_type=0)
            print("Deleting {} rows took {} seconds.".format(num_to_remove, time.time() - del_start_time))

            check_index_query = ("""SELECT COUNT(1) FROM INFORMATION_SCHEMA.STATISTICS """
                                 """WHERE TABLE_SCHEMA = 'series' AND TABLE_NAME = 'movies' AND INDEX_NAME = 'idx_director'""")
            mycursor.execute(check_index_query)
            index_is_there = mycursor.fetchone()[0]

            if index_is_there:
                print("\nDropping additional index.")
                mycursor.execute("ALTER TABLE movies DROP INDEX idx_director")
            else:
                print("\nCreating additional index.")
                mycursor.execute("CREATE INDEX idx_director ON movies (director)")

            # create_index = not create_index

            time.sleep(1)
            start_time = time.time()
