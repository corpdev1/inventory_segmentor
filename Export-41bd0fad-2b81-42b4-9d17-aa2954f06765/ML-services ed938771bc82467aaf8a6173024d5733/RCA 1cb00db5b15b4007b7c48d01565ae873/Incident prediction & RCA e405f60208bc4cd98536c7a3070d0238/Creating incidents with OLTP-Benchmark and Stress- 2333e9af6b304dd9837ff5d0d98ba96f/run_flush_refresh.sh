#!/bin/bash

./oltpbenchmark -b tpcc -c config/tpcc_normal.xml --execute=true -s 5 -o outputfile &
sleep 10m
mysqladmin -u root -pMySQL flush-logs
mysqladmin -u root -pMySQL refresh 
