#!/usr/bin/python
import sys
import os
import logging
logging.basicConfig(stream=sys.stderr)
sys.path.insert(0, "/var/www/api_server")
os.chdir("/var/www/api_server")
from api_server import app as application
