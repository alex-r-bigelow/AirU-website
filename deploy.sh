#!/bin/bash

WORKING_DIR=${1:-`pwd`}
echo "*** Using $WORKING_DIR as working directory"

echo "*** Installing the basics..."
apt-get install -y curl wget python3-pip python3-dev build-essential apt-transport-https
pip3 install pip --upgrade
pip3 install virtualenv --upgrade

echo "*** Installing and Setting Up InfluxDB..."
curl -sL https://repos.influxdata.com/influxdb.key | apt-key add -
source /etc/os-release
test $VERSION_ID = "7" && echo "deb https://repos.influxdata.com/debian wheezy stable" | sudo tee /etc/apt/sources.list.d/influxdb.list
test $VERSION_ID = "8" && echo "deb https://repos.influxdata.com/debian jessie stable" | sudo tee /etc/apt/sources.list.d/influxdb.list

apt-get update
apt-get install -y influxdb
systemctl start influxdb

echo "*** Setting up API server..."
apt-get install -y apache2 libapache2-mod-wsgi-py3
pip3 install -r $WORKING_DIR/api_server/requirements.txt --upgrade

if [ `id -u api 2>/dev/null || echo -1` -eq -1 ]
then
  # quietly add the api user without password
  adduser --quiet --disabled-password --shell /bin/bash --home /home/api --gecos "User" api
  addgroup apache
fi

if [ ! -e /var/www/api_server ]
then
  # add symlink for the server
  ln -s $WORKING_DIR/api_server /var/www/
fi

if [ ! -e /etc/apache2/sites-available/api_server.conf ]
then
  # add symlink for the server config file
  ln -s $WORKING_DIR/config/api_server.conf /etc/apache2/sites-available/api_server.conf
fi

if ! grep 'Listen 8001' /etc/apache2/ports.conf
then
  # listen to port 8001
  sed -i '/Listen 80/aListen 8001\n' /etc/apache2/ports.conf
fi

a2ensite api_server.conf
apachectl restart
