from flask import Flask, request, jsonify
import MarketplaceScraper

API = Flask(__name__)

@API.route("/locations", methods=["GET"])
def locations():
    response = {"status": "", "error": {}, "data": {}}
    locationQuery = request.args.get("locationQuery")

    if locationQuery:
        status, error, data = MarketplaceScraper.getLocations(locationQuery=locationQuery)
    else:
        status = "Failure"
        error = {"source": "User", "message": "Missing required parameter"}
        data = {}

    response.update({"status": status, "error": error, "data": data})
    return jsonify(response)

@API.route("/search", methods=["GET"])
def search():
    response = {"status": "", "error": {}, "data": {}}
    locationLatitude = request.args.get("locationLatitude")
    locationLongitude = request.args.get("locationLongitude")
    listingQuery = request.args.get("listingQuery")

    if locationLatitude and locationLongitude and listingQuery:
        status, error, data = MarketplaceScraper.getListings(
            locationLatitude=locationLatitude, 
            locationLongitude=locationLongitude, 
            listingQuery=listingQuery
        )
    else:
        status = "Failure"
        error = {"source": "User", "message": "Missing required parameter(s)"}
        data = {}

    response.update({"status": status, "error": error, "data": data})
    return jsonify(response)

if __name__ == "__main__":
    API.run(port=5000)
