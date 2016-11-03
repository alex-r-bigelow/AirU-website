#!/bin/bash

WORKING_DIR=${1:-`pwd`}
echo "*** Using $WORKING_DIR as working directory"

echo "*** Installing the basics..."
apt-get install -y curl g++ git libssl-dev libffi-dev make python-dev python-pip libjpeg-dev zlib1g-dev
apt-get install -y python-pip python-dev build-essential
pip install pip --upgrade
pip install virtualenv --upgrade

echo "*** Installing mongodb..."
sudo apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv 7F0CEB10
echo 'deb http://downloads-distro.mongodb.org/repo/debian-sysvinit dist 10gen' | sudo tee /etc/apt/sources.list.d/mongodb.list
apt-get update
apt-get install -y mongodb-org-shell mongodb-org-server

if [ $1 = "/vagrant" ] ; then
  # Only apply our custom mongo.conf for vagrant installs (it allows
  # connections from outside the VM, but we want the more secure settings in
  # deployment)
  echo "*** Allow foreign mongo connections"
  cp $WORKING_DIR/config/mongod.conf /etc/mongod.conf
fi
cp $WORKING_DIR/config/mongod.service /lib/systemd/system/mongod.service
systemctl enable mongod


echo "*** Setting up REST server..."
pip install eve eve-swagger flask-sentinel --upgrade

# TODO: Set up OAuth
# if [ ! -d $WORKING_DIR/rest_server/lib ] ; then
#   mkdir $WORKING_DIR/rest_server/lib
#   git clone https://github.com/nicolaiarocci/eve-oauth2 $WORKING_DIR/rest_server/lib/eve-oauth2
# fi

cp $WORKING_DIR/config/restserver.service /lib/systemd/system/restserver.service
echo "WorkingDirectory=$WORKING_DIR/rest_server" >> /lib/systemd/system/restserver.service
echo "ExecStart=$WORKING_DIR/rest_server/run.py" >> /lib/systemd/system/restserver.service
systemctl enable restserver

# echo "*** Setting up web server..."
# apt-get install apache2 libapache2-mod-wsgi
# cp -TR $WORKING_DIR/web_server /var/www/html
# cp -R $WORKING_DIR/rest_server /var/www/rest_server
# cp $WORKING_DIR/config/restserver.conf /etc/apache2/sites-enabled
# echo "import sys"
