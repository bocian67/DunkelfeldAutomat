import math
import numpy as np
from shapely import LineString, MultiLineString

originShift = 2 * math.pi * 6378137 / 2.0
tileSize = 4096
initialResolution = 2 * math.pi * 6378137 / tileSize

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

def LatLonToMeters(lat, lon):
    "Converts given lat/lon in WGS84 Datum to XY in Spherical Mercator EPSG:900913"

    mx = lon * originShift / 180.0
    my = math.log(math.tan((90 + lat) * math.pi / 360.0)) / (math.pi / 180.0)

    my = my * originShift / 180.0
    return mx, my

def MetersToLatLon(mx, my):
    "Converts XY point from Spherical Mercator EPSG:900913 to lat/lon in WGS84 Datum"

    lon = (mx / originShift) * 180.0
    lat = (my / originShift) * 180.0

    lat = 180 / math.pi * (2 * math.atan(math.exp(lat * math.pi / 180.0)) - math.pi / 2.0)
    return lat, lon

def TileBounds(tx, ty, zoom):
    "Returns bounds of the given tile in EPSG:900913 coordinates"

    minx, miny = PixelsToMeters(tx * tileSize, ty * tileSize, zoom)
    maxx, maxy = PixelsToMeters((tx + 1) * tileSize, (ty + 1) * tileSize, zoom)
    return (minx, miny, maxx, maxy)

def PixelsToMeters(px, py, zoom):
    "Converts pixel coordinates in given zoom level of pyramid to EPSG:900913"

    res = Resolution(zoom)
    mx = px * res - originShift
    my = py * res - originShift
    return mx, my

def Resolution(zoom):
    "Resolution (meters/pixel) for given zoom level (measured at Equator)"

    # return (2 * math.pi * 6378137) / (self.tileSize * 2**zoom)
    return initialResolution / (2 ** zoom)

## LINESTRING

def format_to_coord_list(geometry):
    if isinstance(geometry, LineString):
        xy = geometry.xy
        longs = xy[0].tolist()
        lats = xy[1].tolist()
        return [list(z) for z in zip(lats, longs)]
    #elif isinstance(geometry, MultiLineString):
    #    intermediate = []
    #    for i in geometry.geoms:
    #        intermediate += format_to_coord_list(i)
    #    return intermediate
    #    #return [format_to_coord_list(i) for i in geometry.geoms]
    #

def closest_node(node, nodes):
    nodes = np.asarray(nodes)
    deltas = nodes - node
    dist_2 = np.einsum('ij,ij->i', deltas, deltas)
    return np.argmin(dist_2)

def get_closest_intersection(position, intersections):
    nearest = {"id": 0, "coordinates": [0,0]}
    for intersection in intersections["intersections"]:
        if abs(intersection["coordinates"][1] - position[0]) + abs(intersection["coordinates"][0] - position[1]) < \
                abs(nearest["coordinates"][1] - position[0]) + abs(nearest["coordinates"][0] - position[1]):
            nearest = intersection
    return nearest

def get_closest_street_point_index(point, street_elements):
    nearest = [0,0]
    index = 0
    for element_index, element in enumerate(street_elements):
        if abs(element[0] - point[0]) + abs(element[1] - point[1]) < \
                abs(nearest[0] - point[0]) + abs(nearest[1] - point[1]):
            nearest = element
            index = element_index
    return index