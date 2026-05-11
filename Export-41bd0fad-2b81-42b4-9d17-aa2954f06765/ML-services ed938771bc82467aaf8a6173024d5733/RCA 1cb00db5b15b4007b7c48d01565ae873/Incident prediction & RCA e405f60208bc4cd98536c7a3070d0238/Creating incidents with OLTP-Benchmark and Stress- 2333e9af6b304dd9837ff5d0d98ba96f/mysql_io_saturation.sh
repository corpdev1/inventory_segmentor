#!/bin/bash

./oltpbenchmark -b tpcc -c config/tpcc_normal.xml --execute=true -s 5 -o outputfile &
sleep 5m
stress-ng --class io --all 20 --timeout 300s
