import os

from flask import Flask, jsonify

from config import config

# Import helpers to access database
from .database import InfluxDB

db = InfluxDB()


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLACK_CONFIG', 'development')

    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Allow for trailing slashes
    app.url_map.strict_slashes = False

    db.init_app(app)

    # Register API routes
    from .api_1 import api as api_1_blueprint
    app.register_blueprint(api_1_blueprint, url_prefix='/api/v1')

    @app.errorhandler(400)
    def custom_error(error):
        return jsonify({'message': error.description})

    return app
