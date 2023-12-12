#!/bin/bash

# The name of the network interface to change the bandwidth of.
INTERFACE=$1
trace=$2

while true
do
    while IFS= read -r line
    do
        IFS=' ' read -ra ADDR <<< "$line"
        TS=${ADDR[0]}
        BANDWIDTH=${ADDR[1]}
        tc class change dev ${INTERFACE} classid 5:1 htb rate ${BANDWIDTH}Mbit 
        # echo ${INTERFACE} ${BANDWIDTH}
        sleep 1
    done < "${trace}"
done
