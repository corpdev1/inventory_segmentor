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
  database="tpcc",
  auth_plugin='mysql_native_password'
)

mydb.autocommit = True

mycursor = mydb.cursor(buffered=True)

"""
CREATE TABLE result AS 
  (SELECT first.*, 
          second.f1, 
          second.f2, 
          second.f3 
   FROM   first 
          INNER JOIN second 
                  ON first.id = second.id);
"""

slow_query_one = ("""CREATE TABLE CUSTOMER_DISTRICT AS """ 
                  """(SELECT CUSTOMER.*, """ 
                  """DISTRICT.* """ 
                  """FROM CUSTOMER """ 
                  """INNER JOIN DISTRICT """ 
                  """ON CUSTOMER.C_ZIP = DISTRICT.D_ZIP)""")

mycursor.execute(slow_query_one)

"""
SELECT uid,fid
FROM profile_values
WHERE uid NOT IN
  (SELECT uid FROM profile_values WHERE fid = 13 AND value = 'no')
  AND value REGEXP 'ert' AND uid != 4145
  AND uid NOT IN
    (SELECT uid FROM users WHERE status = 0)
ORDER BY RAND()
LIMIT 1;
"""

slow_query_two = ("""SELECT C_ID,D_ID """
                  """FROM CUSTOMER_DISTRICT """
                  """WHERE C_ID NOT IN """
                  """(SELECT C_ID FROM CUSTOMER_DISTRICT WHERE D_ID = 13 AND C_DELIVERY_CNT > 10)"""
                  """AND D_CITY REGEXP 'sem' AND D_ID != 4145 """
                  """AND D_ID NOT IN """
                  """(SELECT D_ID FROM DISTRICT WHERE D_STATE = 'CA') """
                  """ORDER BY RAND() """
                  """LIMIT 1""")

mycursor.execute(slow_query_two)
