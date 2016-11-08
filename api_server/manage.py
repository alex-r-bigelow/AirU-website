#!/usr/bin/env python
import logging
import os
import sys

from flask_script import Manager, Server as _Server, Option

from app import create_app

logging.basicConfig(level=logging.DEBUG)

manager = Manager(create_app)

if __name__ == '__main__':
    print(len(sys.argv))
    if len(sys.argv) > 1 and (sys.argv[1] == 'test' or sys.argv[1] == 'lint'):
        # small hack, to ensure that Flask-Script uses the testing
        # configuration if we are going to run the tests
        os.environ['FLACK_CONFIG'] = 'testing'
    manager.run()
