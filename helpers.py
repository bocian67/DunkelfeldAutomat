import math
import numpy as np
from shapely import LineString, MultiLineString

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