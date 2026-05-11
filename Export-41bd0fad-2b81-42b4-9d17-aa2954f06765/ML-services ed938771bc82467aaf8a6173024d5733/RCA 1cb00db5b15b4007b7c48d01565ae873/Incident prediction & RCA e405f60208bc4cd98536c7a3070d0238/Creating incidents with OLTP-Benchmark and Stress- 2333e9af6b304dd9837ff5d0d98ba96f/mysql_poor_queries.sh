#!/bin/bash

./oltpbenchmark -b tpcc -c config/tpcc_normal.xml --execute=true -s 5 -o outputfile
python mysql_poor_queries.py
