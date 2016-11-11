#!/bin/bash

WORKING_DIR=${1:-`pwd`}
echo "*** Using $WORKING_DIR as working directory"

echo "*** Installing the basics..."
apt-get install -y curl wget apt-transport-https

echo "*** Installing InfluxDB..."
curl -sL https://repos.influxdata.com/influxdb.key | apt-key add -
source /etc/os-release
test $VERSION_ID = "7" && echo "deb https://repos.influxdata.com/debian wheezy stable" | sudo tee /etc/apt/sources.list.d/influxdb.list
test $VERSION_ID = "8" && echo "deb https://repos.influxdata.com/debian jessie stable" | sudo tee /etc/apt/sources.list.d/influxdb.list

apt-get update
apt-get install -y influxdb
systemctl start influxdb

# Comment out this line if you don't want to start with a fresh database every time you provision
rm /etc/influxdb/influxdb.conf

echo "*** Setting Up InfluxDB..."
if [ ! -L /etc/influxdb/influxdb.conf ]
then
  echo "*** First time admin account setup (change the password!!!!)..."
  influx -execute "`cat $WORKING_DIR/dbSetup.influxql`"
  rm /etc/influxdb/influxdb.conf
  ln -s $WORKING_DIR/influxdb.conf /etc/influxdb/influxdb.conf
  systemctl restart influxdb

  echo "*** Populating with sample data..."
  apt-get install python python-dev python-pip
  pip install pip --upgrade
  pip install influxdb --upgrade

  python $WORKING_DIR/populateSampleData.py
fi

echo "*** Setting up web server..."
apt-get install -y apache2
if [ ! -L /var/www/html ]
then
  rm -rf /var/www/html
  ln -s $WORKING_DIR/web_server /var/www/html
fi
apachectl restart
