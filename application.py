import os
import re
from flask import Flask, jsonify, render_template, request

from cs50 import SQL
from helpers import lookup

# Configure application
app = Flask(__name__)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///mashup.db")


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
def index():
    """Render map"""
    if not os.environ.get("API_KEY"):
        raise RuntimeError("API_KEY not set")
    return render_template("index.html", key=os.environ.get("API_KEY"))


@app.route("/articles")
def articles():
    """Look up articles for geo"""
    # Ensure geo location input is present
    if not request.args.get("geo"):
        raise RuntimeError("missing geo")

    # Look up news articles and save as array of dict (first five articles only)
    news = lookup(request.args.get("geo"))[0:5]

    return jsonify(news)


@app.route("/search")
def search():
    """Search for places that match query"""
    # Ensure query parameter is present
    if not request.args.get("q"):
        raise RuntimeError("missing q")

    # Get the query parameter
    q = request.args.get("q")

    # Handle query with comma
    if "," in q:
        # two fields separated by comma space: city, state or city, statecode
        if ", " in q:
            q1 = request.args.get("q").split(", ")
        # two fields separated by comma: city, state or city, statecode
        elif "," in q:
            q1 = request.args.get("q").split(",")
        # Lookup city/state/postal code in the database
        rows = db.execute("SELECT * FROM places WHERE (place_name LIKE :q1a1 AND admin_code1=:q1b) OR (place_name LIKE :q1a1 AND admin_name1 LIKE :q1b1) LIMIT 10",
                          q1a1=q1[0] + "%", q1b1=q1[1] + "%", q1b=q1[1])
    # Handle query with one or more spaces but without comma: city, state (1+1, 1+2, 2+1, 2+2) or city, statecode (1+1, 2+1) or state (2)
    elif " " in q:
        q1 = request.args.get("q").split(" ")
        # city(1) statecode(1) or city(1) state(1) or city(2) or state(2)
        if len(q1) == 2:
            rows = db.execute("SELECT * FROM places WHERE (place_name LIKE :q1a1 AND admin_code1=:q1b) OR (place_name LIKE :q1a1 AND admin_name1 LIKE :q1b1) OR place_name LIKE :q OR admin_name1 LIKE :q LIMIT 10",
                              q1a1=q1[0] + "%", q1b1=q1[1] + "%", q1b=q1[1], q=q + "%")
        # city(2) statecode(1) or city(2) state(1) or city(1) state(2)
        elif len(q1) == 3:
            rows = db.execute("SELECT * FROM places WHERE (place_name LIKE :q1a1 AND admin_code1=:q1b) OR (place_name LIKE :q1a1 AND admin_name1 LIKE :q1b1) OR (place_name LIKE :q1a2 AND admin_name1 LIKE :q1b2) LIMIT 10",
                              q1a1=q1[0] + " " + q1[1] + "%", q1b1=q1[2] + "%", q1b=q1[2], q1a2=q1[0] + "%", q1b2=q1[1] + " " + q1[2] + "%")
        # city(2) state(2)
        elif len(q1) == 4:
            rows = db.execute("SELECT * FROM places WHERE place_name LIKE :q1a1 AND admin_name1 LIKE :q1b1 LIMIT 10",
                              q1a1=q1[0] + " " + q1[1] + "%", q1b1=q1[2] + " " + q1[3] + "%")
    # for string without comma or spaces
    else:
        # Lookup city/state/postal code in the database
        rows = db.execute("SELECT * FROM places WHERE postal_code LIKE :q OR place_name LIKE :q OR admin_name1 LIKE :q LIMIT 10",
                          q=q + "%")

    return jsonify(rows)


@app.route("/update")
def update():
    """Find up to 10 places within view"""

    # Ensure parameters are present
    if not request.args.get("sw"):
        raise RuntimeError("missing sw")
    if not request.args.get("ne"):
        raise RuntimeError("missing ne")

    # Ensure parameters are in lat,lng format
    if not re.search("^-?\d+(?:\.\d+)?,-?\d+(?:\.\d+)?$", request.args.get("sw")):
        raise RuntimeError("invalid sw")
    if not re.search("^-?\d+(?:\.\d+)?,-?\d+(?:\.\d+)?$", request.args.get("ne")):
        raise RuntimeError("invalid ne")

    # Explode southwest corner into two variables
    sw_lat, sw_lng = map(float, request.args.get("sw").split(","))

    # Explode northeast corner into two variables
    ne_lat, ne_lng = map(float, request.args.get("ne").split(","))

    # Find 10 cities within view, pseudorandomly chosen if more within view
    if sw_lng <= ne_lng:

        # Doesn't cross the antimeridian
        rows = db.execute("""SELECT * FROM places
                          WHERE :sw_lat <= latitude AND latitude <= :ne_lat AND (:sw_lng <= longitude AND longitude <= :ne_lng)
                          GROUP BY country_code, place_name, admin_code1
                          ORDER BY RANDOM()
                          LIMIT 10""",
                          sw_lat=sw_lat, ne_lat=ne_lat, sw_lng=sw_lng, ne_lng=ne_lng)

    else:

        # Crosses the antimeridian
        rows = db.execute("""SELECT * FROM places
                          WHERE :sw_lat <= latitude AND latitude <= :ne_lat AND (:sw_lng <= longitude OR longitude <= :ne_lng)
                          GROUP BY country_code, place_name, admin_code1
                          ORDER BY RANDOM()
                          LIMIT 10""",
                          sw_lat=sw_lat, ne_lat=ne_lat, sw_lng=sw_lng, ne_lng=ne_lng)

    # Output places as JSON
    return jsonify(rows)
