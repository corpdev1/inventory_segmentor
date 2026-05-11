import subprocess

# This is to dump (copy) one database into another database.
# subprocess.Popen('mysqldump -h localhost -P 3306 -u root -pMySQL tpcc | mysql -h localhost -P 3306 -u root -pMySQL tpcc2', shell=True)

# This is to dump a database into a zip file. 
# subprocess.Popen('mysqldump -h localhost -P 3306 -u root -pMySQL tpcc | gzip -c > tpcc.gz', shell=True)

subprocess.Popen('mysqldump -u root -pMySQL --single-transaction --routines --triggers tpcc > backup_tpcc.sql', shell=True)
# subprocess.Popen('mysqldump -u root -pMySQL --single-transaction --routines --triggers --all-databases > backup_db.sql', shell=True)
