#!/bin/bash

set -e

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
# rm /etc/influxdb/influxdb.conf

echo "*** Setting Up InfluxDB..."
if [ ! -L /etc/influxdb/influxdb.conf ]
then
  echo "*** First time admin account setup (change the password!!!!)..."
  influx -execute "`cat $WORKING_DIR/dbSetup.influxql`"
  if [ -e /etc/influxdb/influxdb.conf ]
  then
    rm /etc/influxdb/influxdb.conf
  fi
  ln -s $WORKING_DIR/influxdb.conf /etc/influxdb/influxdb.conf
  systemctl restart influxdb

  echo "*** Populating with sample data..."
  apt-get install -y python python-dev python-pip
  pip install pip --upgrade
  pip install influxdb --upgrade

  python $WORKING_DIR/populateSampleData.py
fi

if ! grep 'Listen 8086' /etc/apache2/ports.conf
then
  # listen to port 8086
  sed -i '/Listen 80/aListen 8083\nListen 8086' /etc/apache2/ports.conf
fi

echo "*** Setting up web server..."
apt-get install -y apache2
if [ ! -L /var/www/html ]
then
  # Add the symlink for the api server
  if [ -e /var/www/html ]
  then
    rm -rf /var/www/html
  fi
  ln -s $WORKING_DIR/web_server /var/www/html
fi

echo "*** Setting up the api server..."
# Much of this setup was stolen from https://github.com/kerzner/flask_skeleton
apt-get install -y libapache2-mod-wsgi python-flask
pip install Flask-RESTful --upgrade
pip install Flask-Cors --upgrade

if [ `id -u api 2>/dev/null || echo -1` -eq -1 ]
then
  # quietly add the api user without password
  adduser --quiet --disabled-password --shell /bin/bash --home /home/api --gecos "User" api
  addgroup apache
fi

if [ ! -L /var/www/api_server ]
then
  # Add the symlink for the api server
  rm -rf /var/www/api_server
  ln -s $WORKING_DIR/api_server /var/www/api_server
fi

if [ ! -L /etc/apache2/sites-available/api_server.conf ]
then
  # Add the symlink for the server config file
  ln -s $WORKING_DIR/api_server.conf /etc/apache2/sites-available/api_server.conf
fi

if ! grep 'Listen 8001' /etc/apache2/ports.conf
then
  # listen to port 8001
  sed -i '/Listen 80/aListen 8001\n' /etc/apache2/ports.conf
fi
chmod o+x $WORKING_DIR/ $WORKING_DIR/web_server

a2ensite api_server.conf
apachectl restart

# To test, try this command (outside the VM; use port 8001 inside, or on the live server):
# curl -X POST -d {"query":"some shitty query"} http://localhost:7001/ --header Content-Type:application/json
