#!/bin/bash

echo "Installing mongodb..."
echo "====================="
apt-get install curl g++ git libffi-dev make python-dev python-pip libjpeg-dev zlib1g-dev > /dev/null
sudo apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv 7F0CEB10 > /dev/null
echo 'deb http://downloads-distro.mongodb.org/repo/debian-sysvinit dist 10gen' | sudo tee /etc/apt/sources.list.d/mongodb.list > /dev/null
apt-get update > /dev/null
apt-get install mongodb-org mongodb-org-server > /dev/null
cp /vagrant/config/mongod.conf /etc/mongod.conf
cp /vagrant/config/mongod.service /lib/systemd/system/mongod.service
service mongod restart

echo "Installing pip..."
echo "================="
apt-get install -y python-pip python-dev build-essential > /dev/null
pip install pip --upgrade > /dev/null
pip install virtualenv --upgrade > /dev/null

echo "Installing eve..."
echo "================="
pip install eve --upgrade > /dev/null
