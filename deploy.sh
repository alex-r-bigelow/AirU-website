#!/bin/bash

set -e

function tellUser {
  printf "\e[0;1;36m""$1""\e[0;0m\n"
}

WORKING_DIR=${1:-`pwd`}
ESCAPED_WORKING_DIR=$(printf '%s\n' "$WORKING_DIR" | sed 's/[[\.*^$/]/\\&/g')
tellUser "Using $WORKING_DIR as working directory"

tellUser "Installing the basics..."
apt-get install -y curl apt-transport-https

chmod -R a+x $WORKING_DIR

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
fi

tellUser "Setting up polling script for periodically populating the database..."
apt-get install -y cron python python-dev python-pip
pip install pip --upgrade
pip install influxdb --upgrade
pip install python-dateutil
pip install pytz
pip install bs4
pip install datetime

if [ `id -u poller 2>/dev/null || echo -1` -eq -1 ]
then
  # quietly add the poller user without password
  adduser --quiet --disabled-password --shell /bin/bash --home /home/poller --gecos "User" poller
  chgrp -R poller $WORKING_DIR/poll
  chown -R poller $WORKING_DIR/poll
  chmod -R a+x $WORKING_DIR/web

  # Append the job info to the crontab file
  sed "s/\$WORKING_DIR/$ESCAPED_WORKING_DIR/g" $WORKING_DIR/config/poll.cron >> /etc/crontab
  systemctl enable cron
  systemctl start cron
fi

# need to find an if here to not always reinstalling!!!
# tellUser "Installing grafana..."
# if [ ! -e /etc/grafana/grafana.ini ]
# then
#   wget https://s3-us-west-2.amazonaws.com/grafana-releases/release/grafana_4.4.1_amd64.deb
#   sudo apt-get install -y adduser libfontconfig
#   sudo dpkg -i grafana_4.4.1_amd64.deb
#
#   sudo apt-get update
#   sudo apt-get install grafana
#
#   systemctl daemon-reload
#   systemctl start grafana-server
#   systemctl status grafana-server
# fi

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

tellUser "Setting up the web server..."
curl -sL https://deb.nodesource.com/setup_7.x | sudo -E bash -
sudo apt-get install -y nodejs build-essential

# npm --prefix $WORKING_DIR/web install bower
npm --prefix $WORKING_DIR/web install $WORKING_DIR/web
# bower --prefix $WORKING_DIR/web install $WORKING_DIR/web

if [ `id -u authapi 2>/dev/null || echo -1` -eq -1 ]
then
  # quietly add the authapi user without password
  adduser --quiet --disabled-password --shell /bin/bash --home /home/authapi --gecos "User" authapi
  chgrp -R authapi $WORKING_DIR/web
  chown -R authapi $WORKING_DIR/web
  chmod -R a+x $WORKING_DIR/web
fi

# Create and start the web service
sed "s/\$WORKING_DIR/$ESCAPED_WORKING_DIR/g" $WORKING_DIR/config/web.service > /lib/systemd/system/web.service
systemctl enable web
systemctl start web

# Redirect port 80 to port 3000
iptables -t nat -A PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 3000
iptables -t nat -I OUTPUT -p tcp -d 127.0.0.1 --dport 80 -j REDIRECT --to-ports 3000

tellUser "Successfully finished deployment script"
