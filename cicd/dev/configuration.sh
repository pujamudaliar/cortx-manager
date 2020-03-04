#!/usr/bin/env bash
read -p "Enter Ip to be Replaced in Config: "  ip_name
ping $ip_name -c 2

if [ $? != 0 ]; then
    echo "Invalid IP"
    exit 1
fi
sed -i 's/localhost/'$ip_name'/g' /etc/csm/csm.conf
sed -i 's/127.0.0.1/'$ip_name'/g' /etc/csm/csm.conf
sed -i 's/localhost/'$ip_name'/g' /etc/csm/database.yaml
sed -i 's/127.0.0.1/'$ip_name'/g' /etc/csm/database.yaml