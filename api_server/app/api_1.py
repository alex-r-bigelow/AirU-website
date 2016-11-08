import logging

from flask import abort, Blueprint, make_response, request, jsonify
from flask_cors import CORS
from flask_httpauth import HTTPBasicAuth

from . import utils
from . import data_processing as dp


LOGGER = logging.getLogger(__name__)
api = Blueprint('api', __name__)
CORS(api)
auth = HTTPBasicAuth()


def make_json_response(data):
    resp = make_response(data)
    resp.mimetype = 'application/json'

    return resp


@auth.get_password
def get_password(username):
    if username == 'jimmy':
        return 'prisms'
    return None


@api.route("/data/")
@api.route("/event/")
def get_data_sites():
    return jsonify(list(dp.get_data_sites()))


@api.route("/data/<site>/<start>/<end>")
@auth.login_required
def get_data(site, start, end):
    try:
        # Get data
        data = dp.get_data(site, start, end)
        data = data.reset_index()

        # Send the result back
        data = utils.jsonify_df(data=data,
                                fields=list(data.columns),
                                time=utils.current_time())
        return make_json_response(data)

    except ValueError as e:
        LOGGER.exception(e)
        abort(400, str(e))


@api.route("/events/<site>/<start>/<end>")
@auth.login_required
def get_events(site, start, end):
    try:
        # Get data
        data = dp.get_events(site, start, end)

        # Send the result back
        data = utils.jsonify_df(events=data.reset_index(),
                                fields=['time', 'event'],
                                time=utils.current_time())

        return make_json_response(data)
    except ValueError as e:
        LOGGER.exception(e)
        abort(400, str(e))


@api.route("/vendors", methods=['GET'])
@auth.login_required
def get_all_vendors():
    return jsonify(dp.get_vendors())


@api.route("/vendors/<vendor>", methods=['GET'])
@auth.login_required
def get_vendor(vendor):
    vendors = dp.get_vendors()

    if vendor not in vendors:
        abort(400, "Invalid vendor")

    return jsonify(vendors[vendor])


@api.route("/floor_plan/<site>", methods=['GET', 'PUT'])
@auth.login_required
def get_floor_plan(site):
    site = utils.validate_data_site(site)
    return "Floor plan has not been implemented."


@api.route("/data/<site>/stream")
@auth.login_required
def stream(site):
    site = utils.validate_data_site(site)
    return "Stream has not been implemented."
