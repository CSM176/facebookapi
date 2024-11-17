import requests
import json
import copy

GRAPHQL_URL = "https://www.facebook.com/api/graphql/"
GRAPHQL_HEADERS = {
    "sec-fetch-site": "same-origin",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.74 Safari/537.36"
}


def getLocations(locationQuery):
    data = {}

    requestPayload = {
        "variables": """{"params": {"caller": "MARKETPLACE", "page_category": ["CITY", "SUBCITY", "NEIGHBORHOOD","POSTAL_CODE"], "query": "%s"}}""" % (locationQuery),
        "doc_id": "5585904654783609"
    }

    status, error, facebookResponse = getFacebookResponse(requestPayload)

    if (status == "Success"):
        data["locations"] = []  # Create a locations object within data
        facebookResponseJSON = json.loads(facebookResponse.text)

        # Get location names and their ID from the facebook response
        for location in facebookResponseJSON["data"]["city_street_search"]["street_results"]["edges"]:
            locationName = location["node"]["subtitle"].split(" \u00b7")[0]

            # Refine location name if it is too general
            if (locationName == "City"):
                locationName = location["node"]["single_line_address"]

            locationLatitude = location["node"]["location"]["latitude"]
            locationLongitude = location["node"]["location"]["longitude"]

            # Add the location to the list of locations
            data["locations"].append({
                "name": locationName,
                "latitude": str(locationLatitude),
                "longitude": str(locationLongitude)
            })

    return (status, error, data)


def getListings(locationLatitude, locationLongitude, listingQuery, numPageResults=3):
    data = {}
    rawPageResults = []  # Un-parsed list of JSON results from each page

    requestPayload = {
        "variables": json.dumps({
            "count": 24,
            "params": {
                "bqf": {
                    "callsite": "COMMERCE_MKTPLACE_WWW",
                    "query": listingQuery
                },
                "browse_request_params": {
                    "commerce_enable_local_pickup": True,
                    "commerce_enable_shipping": True,
                    "commerce_search_and_rp_available": True,
                    "commerce_search_and_rp_condition": None,
                    "commerce_search_and_rp_ctime_days": None,
                    "filter_location_latitude": locationLatitude,
                    "filter_location_longitude": locationLongitude,
                    "filter_price_lower_bound": 0,
                    "filter_price_upper_bound": 214748364700,
                    "filter_radius_km": 16
                },
                "custom_request_params": {
                    "surface": "SEARCH"
                }
            }
        }),
        "doc_id": "7111939778879383"
    }

    status, error, facebookResponse = getFacebookResponse(requestPayload)

    if status == "Success":
        facebookResponseJSON = json.loads(facebookResponse.text)
        rawPageResults.append(facebookResponseJSON)

        # Retrieve subsequent page results if numPageResults > 1
        for _ in range(1, numPageResults):
            pageInfo = facebookResponseJSON["data"]["marketplace_search"]["feed_units"]["page_info"]

            # If a next page of results exists
            if pageInfo["has_next_page"]:
                cursor = pageInfo["end_cursor"]

                # Update request payload with cursor for the next page
                requestPayload["variables"] = json.dumps({
                    "count": 24,
                    "cursor": cursor,
                    "params": {
                        "bqf": {
                            "callsite": "COMMERCE_MKTPLACE_WWW",
                            "query": listingQuery
                        },
                        "browse_request_params": {
                            "commerce_enable_local_pickup": True,
                            "commerce_enable_shipping": True,
                            "commerce_search_and_rp_available": True,
                            "commerce_search_and_rp_condition": None,
                            "commerce_search_and_rp_ctime_days": None,
                            "filter_location_latitude": locationLatitude,
                            "filter_location_longitude": locationLongitude,
                            "filter_price_lower_bound": 0,
                            "filter_price_upper_bound": 214748364700,
                            "filter_radius_km": 16
                        },
                        "custom_request_params": {
                            "surface": "SEARCH"
                        }
                    }
                })

                status, error, facebookResponse = getFacebookResponse(requestPayload)

                if status == "Success":
                    facebookResponseJSON = json.loads(facebookResponse.text)
                    rawPageResults.append(facebookResponseJSON)
                else:
                    return (status, error, data)
    else:
        return (status, error, data)

    # Parse the raw page results and set as the value of listingPages
    parsed_results = parsePageResults(rawPageResults)

    # Limit the parsed results to the first 50 items
    data["listingPages"] = parsed_results[:50]
    return (status, error, data)


# Helper function
def getFacebookResponse(requestPayload):
    status = "Success"
    error = {}

    # Try making post request to Facebook, excpet return
    try:
        facebookResponse = requests.post(
            GRAPHQL_URL, headers=GRAPHQL_HEADERS, data=requestPayload)
    except requests.exceptions.RequestException as requestError:
        status = "Failure"
        error["source"] = "Request"
        error["message"] = str(requestError)
        facebookResponse = None
        return (status, error, facebookResponse)

    if (facebookResponse.status_code == 200):
        facebookResponseJSON = json.loads(facebookResponse.text)

        if (facebookResponseJSON.get("errors")):
            status = "Failure"
            error["source"] = "Facebook"
            error["message"] = facebookResponseJSON["errors"][0]["message"]
    else:
        status = "Failure"
        error["source"] = "Facebook"
        error["message"] = "Status code {}".format(
            facebookResponse.status_code)

    return (status, error, facebookResponse)


def parsePageResults(rawPageResults):
    listingPages = []

    pageIndex = 0
    for rawPageResult in rawPageResults:
        listingPages.append({"listings": []})  # Create a new listings object for each page

        for listing in rawPageResult["data"]["marketplace_search"]["feed_units"]["edges"]:
            if listing["node"]["__typename"] == "MarketplaceFeedListingStoryObject":
                listingID = listing["node"]["listing"]["id"]
                listingName = listing["node"]["listing"]["marketplace_listing_title"]
                listingCurrentPrice = listing["node"]["listing"]["listing_price"]["formatted_amount"]

                # Check if 'strikethrough_price' exists
                listingPreviousPrice = (
                    listing["node"]["listing"]["strikethrough_price"]["formatted_amount"]
                    if listing["node"]["listing"].get("strikethrough_price") else ""
                )

                listingSaleIsPending = listing["node"]["listing"]["is_pending"]
                listingPrimaryPhotoURL = listing["node"]["listing"]["primary_listing_photo"]["image"]["uri"]

                # Check if 'marketplace_listing_seller' exists and is not None
                seller = listing["node"]["listing"].get("marketplace_listing_seller")
                if seller:
                    sellerName = seller.get("name", "Unknown Seller")
                    sellerLocation = seller.get("location", {}).get("reverse_geocode", {}).get("city_page", {}).get("display_name", "Unknown Location")
                    sellerType = seller.get("__typename", "Unknown Type")
                else:
                    sellerName = "Unknown Seller"
                    sellerLocation = "Unknown Location"
                    sellerType = "Unknown Type"

                # Add the listing to its corresponding page
                listingPages[pageIndex]["listings"].append({
                    "id": listingID,
                    "name": listingName,
                    "currentPrice": listingCurrentPrice,
                    "previousPrice": listingPreviousPrice,
                    "saleIsPending": str(listingSaleIsPending).lower(),
                    "primaryPhotoURL": listingPrimaryPhotoURL,
                    "sellerName": sellerName,
                    "sellerLocation": sellerLocation,
                    "sellerType": sellerType
                })

        pageIndex += 1

    return listingPages
