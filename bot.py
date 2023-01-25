#!/usr/bin/python3

import sys
import time
import requests
import matplotlib as plt
import numpy as np
import pandas as pd
import geopandas
import contextily as cx
import telebot
import json
import traceback
from   collections import defaultdict


def print_obj(o, print_nones = False):
    d = o.__dict__.copy()
    if print_nones == False:
        for k, v in o.__dict__.items():
            if v == None:
                del d[k]
    print(d)


# max_user_spots = 100000
max_scale = 5.12
min_scale = 0.000625
max_wigle_scale = 0.09
max_lat = 80
max_lon = 180
zoom_factor = 2


user_coords = defaultdict(lambda: [37.97106, 34.67732, 0.025]) # latitude, longitude, scale for each user
# user_spots  = defaultdict(lambda: [])

with open('api_keys.json') as user_file:
    api_keys = json.load(user_file)
wigle_key = api_keys["wigle_key"]
telegram_key = api_keys["telegram_key"]


wigle_headers = {'Accept': 'application/json', 'Authorization': f'Basic {wigle_key}'}



def wigle_get_geocode(geoname):
    geocode_payload = {'first': '0', 'freenet': 'false', 'paynet': 'false', 'addresscode': geoname}
    r = requests.get(url='https://api.wigle.net/api/v2/network/geocode', params=geocode_payload, headers=wigle_headers)
    j = r.json()
    return j


def wigle_get_spots(bb):
    search_payload = {'latrange1': bb[0], 'latrange2':  bb[1], 'longrange1':  bb[2], 'longrange2':  bb[3], 'encryption': None, 'resultsPerPage': 100}
    r = requests.get(url='https://api.wigle.net/api/v2/network/search', params=search_payload, headers=wigle_headers)
    j = r.json()
    # print(j)
    spots_names = [a["ssid"] for a in j["results"]]
    spots_lat = [a["trilat"] for a in j["results"]]
    spots_lon = [a["trilong"] for a in j["results"]]
    df = pd.DataFrame({"name": spots_names, "lat": spots_lat, "lon": spots_lon})
    gdf = geopandas.GeoDataFrame(df, geometry=geopandas.points_from_xy(df.lon, df.lat))
    gdf.crs = 4326 # https://spatialreference.org/ref/epsg/4326/
    spots = gdf.to_crs(epsg=3857)
    return spots


def boundingbox_from_coords(p):
    """generates bounding boxes needed by wigle (EPSG:4326, degrees, list)
    and by geopandas/contextily (EPSG:3857, meters, GeoDataFrame)
    from user's coordinates (lat, lon, scale)"""
    yscale = p[2]
    xscale = p[2] / np.cos(p[0] * np.pi / 180)
    bb_deg = [p[0] - yscale, p[0] + yscale, p[1] - xscale, p[1] + xscale] # min_lat, max_lat, min_lon, max_lon
    # bb_square = [[bb_deg[0], bb_deg[2]], [bb_deg[1], bb_deg[2]], [bb_deg[1], bb_deg[3]], [bb_deg[0], bb_deg[3]]] # four points at the corners of the bounding box
    lats = [bb_deg[0], bb_deg[1], bb_deg[1], bb_deg[0]] #  latitudes of four points at the corners of the bounding box
    lons = [bb_deg[2], bb_deg[2], bb_deg[3], bb_deg[3]] # longitudes of four points at the corners of the bounding box
    df = pd.DataFrame({"lat": lats, "lon": lons})
    gdf = geopandas.GeoDataFrame(df, geometry=geopandas.points_from_xy(df.lon, df.lat))
    gdf.crs = 4326 # https://spatialreference.org/ref/epsg/4326/
    bb_m = gdf.to_crs(epsg=3857)
    return bb_deg, bb_m


def show_map(user_id):
    scale_by(user_id, 1)     # checking if coordinates are allowed
    move_by(user_id, (0, 0)) # checking if coordinates are allowed
    p = user_coords[user_id]
    # bot.send_message(user_id, "Please wait..\nYour position: " + str((p[0], p[1], p[2])))
    bot.send_message(user_id, "Please wait..\nYour position: " + " ".join(map(str, p)))
    bb_deg, bb_m = boundingbox_from_coords(p)
    # print(bb_m)
    
    # drawing blank map of desired region
    ax = bb_m.plot(figsize=(9.5, 9.5), alpha=0.)
    
    # obtaining and drawing wi-fi spot list
    if p[2] < max_wigle_scale:
        try:
            spots = wigle_get_spots(bb_deg)
        except Exception as e:
            traceback.print_stack()
            bot.send_message(user_id, "Failed to obtain wi-fi spot list for this location! The exception was:\n" + str(e))
        else:
            bot.send_message(user_id, "Found " + str(spots.shape[0]) + " spots")
            spots.plot(ax = ax, figsize=(10, 10), alpha=0.5, edgecolor='k')
            for s in spots.itertuples(): # drawing spot names
                ax.annotate(s.name, (s.geometry.x, s.geometry.y))
    else:
        bot.send_message(user_id, "Zoom level is too wide, zoom in to see wi-fi networks")
    
    # obtaining and drawing base map
    try:
        cx.add_basemap(ax, source=cx.providers.CyclOSM)
    except Exception as e:
        traceback.print_stack()
        bot.send_message(user_id, "Failed to obtain base map for this location! The exception was:\n" + str(e))
    
    sys.stderr.flush()    
    extent = ax.get_window_extent().transformed(ax.figure.dpi_scale_trans.inverted())
    # fname = "map.png"
    fname = str(user_id) + f"_{time.time()}_" + "_".join(map(str, p)) + ".png"
    plt.pyplot.savefig(fname, bbox_inches=extent)
    plt.pyplot.close(ax.figure)
    img = open(fname, 'rb')
    bot.send_photo(user_id, img)
    img.close()


def move_by(user_id, d):
    c = user_coords[user_id]
    s = c[2] # scale
    c[0] += d[0] * s #  latitude (y)
    c[1] += d[1] * s / np.cos(c[0] * np.pi / 180) # longitude (x)
    if c[0] < -max_lat:
        c[0] = -max_lat
    if c[0] > max_lat:
        c[0] = max_lat
    if c[1] < -max_lon:
        c[1] = -max_lon
    if c[1] > max_lon:
        c[1] = max_lon
    user_coords[user_id][0] = c[0] #  latitude (y)
    user_coords[user_id][1] = c[1] # longitude (x)

def scale_by(user_id, k):
    c = user_coords[user_id]
    s = c[2] * k # scale
    if s < min_scale:
        s = min_scale
    if s > max_scale:
        s = max_scale
    user_coords[user_id][2] = s #  scale

def move_up(user_id, message):
    move_by(user_id, (1, 0))
    show_map(user_id)

def move_left(user_id, message):
    move_by(user_id, (0, -1))
    show_map(user_id)

def move_down(user_id, message):
    move_by(user_id, (-1, 0))
    show_map(user_id)

def move_right(user_id, message):
    move_by(user_id, (0, 1))
    show_map(user_id)

def zoom(user_id, message):
    scale_by(user_id, 1 / zoom_factor)
    show_map(user_id)

def unzoom(user_id, message):
    scale_by(user_id, zoom_factor)
    show_map(user_id)

def go_to(user_id, message):
    try:
        p = [float(a) for a in message.text.replace(",", " ").split()[1:4]]
    except Exception as e:
        bot.send_message(user_id, "Bad coordinates! The exception was:\n" + str(e))
        return
    if len(p) < 2:
        bot.send_message(user_id, "Specify at least two coordinates!")
        return
    elif len(p) < 3:
        p += [user_coords[user_id][2]]
    user_coords[user_id] = p
    # move_by(user_id, (0, 0))
    show_map(user_id)

def find_place(user_id, message):
    q = message.text[2:]
    try:
        g = wigle_get_geocode(q)
    except Exception as e:
        bot.send_message(user_id, "Failed to find this place! The exception was:\n" + str(e))
        return
    if len(g["results"]) < 1:
        bot.send_message(user_id, "Requested place not found!")
        return
    bb = g["results"][0]["boundingbox"]
    scale = 0.5 * (((bb[1] - bb[0]) ** 2 + (bb[3] - bb[2]) ** 2) ** 0.5)
    user_coords[user_id] = [g["results"][0]["lat"], g["results"][0]["lon"], scale]
    show_map(user_id)

def show_help(user_id, message):
    bot.send_message(message.from_user.id, """I can show you free wi-fi networks around some place!

Commands:

/help - show this help
f smth. - find a place by its name, e. g. f Prijepolje
w, a, s, d - move north/west/south/east
e, + - zoom
q, - - unzoom
g lat lon [scale] - go to some geographic coordinates, e. g. g 55.5153754 36.98217 0.009

Also you can send me your geoposition.

Map data (c) OpenStreetMap.org contributors
Wi-fi spot coordinates (c) wigle.net
""")
# r - return to last position found by "f"


command_handlers = {
    "/start": show_help,
    "/help": show_help,
    "?": show_help,
    "f": find_place,
    "w": move_up,
    "a": move_left,
    "s": move_down,
    "d": move_right,
    "e": zoom,
    "+": zoom,
    "q": unzoom,
    "-": unzoom,
    "g": go_to,
#    "": ,
}


def print_name(message):
    j = defaultdict(lambda: "", message.json)
    d = defaultdict(lambda: "", message.json["from"])
    print("User:", d["id"], d["first_name"], d["last_name"], "Date:",  j["date"], time.ctime(), file = sys.stderr)
    # print("User:", message.json["from"]["id"], message.json["from"]["first_name"], message.json["from"]["last_name"], "Date:",  message.json["date"])


bot = telebot.TeleBot(telegram_key)

@bot.message_handler(content_types=['text'])
def get_text_messages(message):
    print_name(message)
    print("Text:", message.text, file = sys.stderr, flush=True)
    command = message.text.split()[0].lower()
    if command in command_handlers:
        command_handlers[command](message.from_user.id, message)
    else:
        show_help(message.from_user.id, message)


@bot.message_handler(content_types=['location'])
def handle_location(message):
    print_name(message)
    print("Location: {0}, {1}".format(message.location.latitude, message.location.longitude), file = sys.stderr)
    user_id = message.from_user.id
    user_coords[user_id] = [message.location.latitude, message.location.longitude, user_coords[user_id][2]]
    show_map(user_id)


if __name__ == "__main__":
    plt.use("Agg")
    # print("{time.ctime()} {time.time()} Starting polling..")
    print(f"{time.ctime()} {time.time()} Starting polling..", file = sys.stderr)
    try:
        bot.polling(none_stop=True, interval=0)
    except Exception as e:
        traceback.print_stack()
        raise e
    # print("{time.ctime()} {time.time()} Polling stopped")
    print(f"{time.ctime()} {time.time()} Polling stopped", file = sys.stderr)
