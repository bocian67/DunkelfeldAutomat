import math

# Source: https://wiki.openstreetmap.org/wiki/Slippy_map_tilenames
def num2deg(xtile, ytile, zoom):
    n = 1 << zoom
    lon_deg = xtile / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * ytile / n)))
    lat_deg = math.degrees(lat_rad)
    return lat_deg, lon_deg


def deg2num(lat_deg, lon_deg, zoom):
    lat_rad = math.radians(lat_deg)
    n = 1 << zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return xtile, ytile

# Experimental

def lonToX(lon, zoom):
    offset = 256 << (zoom - 1)
    return round(offset + (offset * lon / 180))

def latToY(lat, zoom):
    offset = 256 << (zoom - 1)
    return round(offset - (offset / math.pi) * math.log((1 + math.sin(lat * math.pi / 180)) / (1 - math.sin(lat * math.pi / 180)) / 2))

def xToLon(x, zoom):
    offset = 256 << (zoom - 1)
    return (x - offset) / offset * 180

def yToLat(y, zoom):
    offset = 256 << (zoom - 1)
    return (math.atan(math.exp(((offset - y) * math.pi) / offset) - math.pi / 4)) * 360 / math.pi