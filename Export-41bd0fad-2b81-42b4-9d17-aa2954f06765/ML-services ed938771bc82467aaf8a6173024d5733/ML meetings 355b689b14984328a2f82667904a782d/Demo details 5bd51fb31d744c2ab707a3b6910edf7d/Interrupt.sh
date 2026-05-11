#!/bin/bash

python Cluster.py &                    # This does not check if the command
echo $! > /tmp/Cluster.py.pid          #+has already been executed. But,
                                    #+would have problems if more than 1
sleep 3000

echo packetai | sudo -S kill -9 `cat /tmp/Cluster.py.pid`
# rm /tmp/Peak.py.pid

if [[ -e /tmp/Cluster.py.pid ]]; then
    kill `cat /tmp/Cluster.py.pid`
    rm /tmp/Cluster.py.pid
else
    echo "Cluster.py script is not running"
fi
