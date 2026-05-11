#!/bin/bash

./oltpbenchmark -b tpcc -c config/tpcc_normal.xml --execute=true -s 5 -o outputfile &
sleep 10m
# mysqladmin -u root -pMySQL create restore_tpcc
mysql -u root -pMySQL restore_tpcc < backup_tpcc.sql
mysqldump -u root -pMySQL restore_tpcc CUSTOMER > backup_customer.sql
mysql -u root -pMySQL tpcc < backup_customer.sql
mysqldump -u root -pMySQL restore_tpcc NEW_ORDER > backup_neworder.sql
mysql -u root -pMySQL tpcc < backup_neworder.sql
mysqldump -u root -pMySQL restore_tpcc DISTRICT > backup_district.sql
mysql -u root -pMySQL tpcc < backup_district.sql
