#!/bin/bash

set -e

function tellUser {
  printf "\e[0;1;36m""$1""\e[0;0m\n"
}

WORKING_DIR=${1:-`pwd`}
tellUser "Using $WORKING_DIR as working directory"

tellUser "Installing the basics..."
apt-get install -y curl apt-transport-https

chmod a+x $WORKING_DIR

tellUser "Setting up web server..."
apt-get install -y apache2
if [ ! -L /var/www/html ]
then
  # Add the symlink for the api server
  if [ -e /var/www/html ]
  then
    rm -rf /var/www/html
  fi
  ln -s $WORKING_DIR/web_server /var/www/html
  chmod a+x $WORKING_DIR/web_server
fi

tellUser "Installing InfluxDB..."
curl -sL https://repos.influxdata.com/influxdb.key | apt-key add -
source /etc/os-release
test $VERSION_ID = "7" && echo "deb https://repos.influxdata.com/debian wheezy stable" | sudo tee /etc/apt/sources.list.d/influxdb.list
test $VERSION_ID = "8" && echo "deb https://repos.influxdata.com/debian jessie stable" | sudo tee /etc/apt/sources.list.d/influxdb.list

apt-get update
apt-get install -y influxdb
systemctl start influxdb

# Uncomment this line if you want to start with a fresh database every time you provision
# (or if you want a one-off)
# rm /etc/influxdb/influxdb.conf

tellUser "Setting Up InfluxDB..."
if [ ! -L /etc/influxdb/influxdb.conf ]
then
  tellUser "First time admin account setup..."
  apt-get install -y jq
  INFLUXDBUSERNAME=`cat $WORKING_DIR/config/config.json | jq -r '.influxdbUsername'`
  INFLUXDBPASSWORD=`cat $WORKING_DIR/config/config.json | jq -r '.influxdbPassword'`
  cat $WORKING_DIR/config/dbSetup.influxql > temp.influxql
  echo "CREATE USER \"$INFLUXDBUSERNAME\" WITH PASSWORD '$INFLUXDBPASSWORD' WITH ALL PRIVILEGES" >> temp.influxql
  influx -execute "`cat temp.influxql`"
  rm temp.influxql
  if [ -e /etc/influxdb/influxdb.conf ]
  then
    rm /etc/influxdb/influxdb.conf
  fi
  ln -s $WORKING_DIR/config/influxdb.conf /etc/influxdb/influxdb.conf
  systemctl restart influxdb

  tellUser "Populating with sample data..."
  apt-get install -y python python-dev python-pip
  pip install pip --upgrade
  pip install influxdb --upgrade

  python $WORKING_DIR/config/populateSampleData.py
fi

tellUser "Installing mongodb..."
sudo apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv 7F0CEB10
echo 'deb http://downloads-distro.mongodb.org/repo/debian-sysvinit dist 10gen' | sudo tee /etc/apt/sources.list.d/mongodb.list
apt-get update
apt-get install -y mongodb-org-shell mongodb-org-server

if [ $1 = "/vagrant" ] ; then
  # Only apply our custom mongo.conf for vagrant installs (it allows
  # connections from outside the VM, but we want the more secure settings in
  # deployment)
  tellUser "Allowing foreign mongo connections"
  cp $WORKING_DIR/config/mongod.conf /etc/mongod.conf
fi
cp $WORKING_DIR/config/mongod.service /lib/systemd/system/mongod.service
systemctl enable mongod

tellUser "Setting up the authentication server..."
curl -sL https://deb.nodesource.com/setup_7.x | sudo -E bash -
sudo apt-get install -y nodejs build-essential

npm --prefix $WORKING_DIR/authentication install $WORKING_DIR/authentication

if [ `id -u authapi 2>/dev/null || echo -1` -eq -1 ]
then
  # quietly add the authapi user without password
  adduser --quiet --disabled-password --shell /bin/bash --home /home/authapi --gecos "User" authapi
fi

if [ ! -L /var/www/authentication ]
then
  # Add the symlink for the authentication server
  rm -rf /var/www/authentication
  ln -s $WORKING_DIR/authentication /var/www/authentication
  chgrp -R authapi $WORKING_DIR/authentication
  chown -R authapi $WORKING_DIR/authentication
  chmod a+x $WORKING_DIR/authentication $WORKING_DIR/authentication/app.js
fi

cp $WORKING_DIR/config/authentication.service /lib/systemd/system/authentication.service
echo "WorkingDirectory=$WORKING_DIR/authentication" >> /lib/systemd/system/authentication.service
echo "ExecStart=$WORKING_DIR/authentication/app.js" >> /lib/systemd/system/authentication.service
systemctl enable authentication
systemctl start authentication

tellUser "Successfully finished deployment script"
