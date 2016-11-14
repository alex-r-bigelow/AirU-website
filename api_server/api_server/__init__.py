from flask import Flask
from flask import request
from flask.ext.cors import CORS  # for cross origin requests
import json

app = Flask(__name__)
CORS(app)


@app.route("/", methods=["GET", "POST"])
def default_resource():
    if request.method == "POST":
        # to accesss data fields of the request use:
        # query = request.get_json()[u'query']
        # this is where to run queries
        return json.dumps({"data": [1, 2, 3, 4, 5, 6, 7]})
    elif request.method == "GET":
        return "Please send a POST request here! See _example_requests folder for details."
