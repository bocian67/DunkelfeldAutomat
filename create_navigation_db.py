import copy
import multiprocessing
import random

from joblib import Parallel, delayed

from database import get_database
from models.navigation import NavigationRoute

"""
{
    "start":120,
    "stop": 783,
    "route": {0: [lat, lon, ...],
    "streets": [120, ..., 783]
}
"""

db = get_database()
transportations_collection = db["transportations-name"]
navigation_collection = db["navigation"]
intersections_collection = db["intersections-name"]
all_intersections = list(intersections_collection.find({}))

def find_all_connections(from_street_id):
    for i in all_intersections:
        if i["id"] == from_street_id:
            intersections = i["intersections"]
            result = []
            for r in intersections:
                result.append({"id": r["id"], "coordinates": [r["coordinates"][1], r["coordinates"][0]]})
            return result

def iterate_over_paths():
    max_docs = transportations_collection.count_documents({})
    for transportation_start_index in range(1, max_docs):
        start_street = transportations_collection.find_one({"id": transportation_start_index})
        origin_geometry = start_street["geometry"]
        if origin_geometry["type"] != "LineString":
            continue

        #foo = Parallel(n_jobs=multiprocessing.cpu_count(), prefer="threads")(delayed(find_destination_paths)(transportation_start_index, origin_geometry, transportation_end_index) for transportation_end_index in range(1, max_docs))
        for transportation_end_index in range(1, max_docs):
            find_destination_paths(transportation_start_index, origin_geometry, transportation_end_index)

def pathfinding(origin_street_id, origin_coordinates, destination_street_id, destination_coordinates):
    found_connections = False
    # search for path with intersections
    best_connection = None
    origin_road_navigation = NavigationRoute()
    destination_road_navigation = NavigationRoute()
    origin_road_navigation.add_street({"id": origin_street_id, "coordinates": origin_coordinates})
    destination_road_navigation.add_street({"id": destination_street_id, "coordinates": destination_coordinates})
    connections_from_origin = [origin_road_navigation]
    connections_from_destination = [destination_road_navigation]
    if origin_street_id == destination_street_id:
        found_connections = True
        connections_from_origin[0].add_street({"id": destination_street_id, "coordinates": destination_coordinates})
        best_connection = connections_from_origin[0]
    # add all roads if
    while not found_connections:
        if len(connections_from_origin) == 0 or len(connections_from_destination) == 0:
            break
        origin_no_endpoint_street_indexes = []
        origin_connections_to_append = []
        print(f"Origin: {origin_street_id} with {len(connections_from_origin)} connections from origin and {len(connections_from_destination)} from destination")
        for navigation_route_index, navigation_route in enumerate(connections_from_origin):
            print(f"FROM {navigation_route_index}/{len(connections_from_origin)}")
            last_road = navigation_route.streets[-1]
            all_connections_of_road = find_all_connections(last_road)
            if len(navigation_route.streets) > 1:
                all_connections_of_road = [i for i in all_connections_of_road if i["id"] != navigation_route.streets[-2]]
            for new_road in all_connections_of_road:
                new_path = copy.deepcopy(navigation_route)
                new_path.add_street(new_road)

                connection_already_in_db = navigation_collection.find_one({"start": new_path.streets[0], "end": new_path.streets[-1]})
                if connection_already_in_db is None:
                    origin_connections_to_append.append(new_path)
                    navigation_collection.insert_one({
                        "start": new_path.streets[0],
                        "end": new_path.streets[-1],
                        "route": new_path.route,
                        "streets": new_path.streets
                    })
                    print(f"Start: {new_path.streets[0]} & End: {new_path.streets[-1]}")

                if new_road["id"] == destination_street_id:
                    new_path.add_street({"id": new_road["id"], "coordinates": destination_coordinates})
                    best_connection = new_path
                    found_connections = True
                    break

            origin_no_endpoint_street_indexes.append(navigation_route_index)
            if found_connections:
                break

        destination_no_endpoint_street_indexes = []
        destination_connections_to_append = []
        for navigation_route_index, navigation_route in enumerate(connections_from_destination):
            print(f"TO {navigation_route_index}/{len(connections_from_destination)}")
            last_road = navigation_route.streets[-1]
            all_connections_of_road = find_all_connections(last_road)
            if len(navigation_route.streets) > 1:
                all_connections_of_road = [i for i in all_connections_of_road if i["id"] != navigation_route.streets[-2]]
            for new_road in all_connections_of_road:
                new_path = copy.deepcopy(navigation_route)
                new_path.add_street(new_road)

                connection_already_in_db = navigation_collection.find_one({"start": new_path.streets[0], "end": new_path.streets[-1]})
                if connection_already_in_db is None:
                    destination_connections_to_append.append(new_path)
                    navigation_collection.insert_one({
                        "start": new_path.streets[0],
                        "end": new_path.streets[-1],
                        "route": new_path.route,
                        "streets": new_path.streets
                    })
                    print(f"Start: {new_path.streets[0]} & End: {new_path.streets[-1]}")

                for new_origin_connection in origin_connections_to_append:
                    if new_road["id"] == new_origin_connection.streets[-1]:
                        for index in range(len(new_road) - 1, 0):
                            new_origin_connection.add_street({"id": new_path.streets[index], "coordinates": new_path.route[index]})
                        best_connection = new_origin_connection
                        found_connections = True
                        break

            destination_no_endpoint_street_indexes.append(navigation_route_index)
            if found_connections:
                break

        origin_no_endpoint_street_indexes.sort(reverse=True)
        for no_endpoint_street_index in origin_no_endpoint_street_indexes:
            connections_from_origin.pop(no_endpoint_street_index)
        connections_from_origin += origin_connections_to_append

        destination_no_endpoint_street_indexes.sort(reverse=True)
        for no_endpoint_street_index in destination_no_endpoint_street_indexes:
            connections_from_destination.pop(no_endpoint_street_index)
        connections_from_destination += destination_connections_to_append

    if best_connection is not None:
        navigation_collection.insert_one({
            "start": origin_street_id,
            "end": destination_street_id,
            "route": best_connection.route,
            "streets": best_connection.streets
        })
        print(f"Start: {origin_street_id} & End: {destination_street_id}")


def find_destination_paths(transportation_start_index, origin_geometry, transportation_end_index):
    if transportation_start_index == transportation_end_index:
        return

    end_street = transportations_collection.find_one({"id": transportation_end_index})
    destination_geometry = end_street["geometry"]
    if destination_geometry["type"] != "LineString":
        return

    existing_route = navigation_collection.find_one(
        {"start": transportation_start_index, "end": transportation_end_index})
    if existing_route is not None:
        return

    random_origin_linestring_checkpoint_index = random.randint(0, len(origin_geometry["coordinates"]) - 1)
    random_origin_linestring_checkpoint = origin_geometry["coordinates"][random_origin_linestring_checkpoint_index]

    random_destination_linestring_checkpoint_index = random.randint(0, len(destination_geometry["coordinates"]) - 1)
    random_destination_linestring_checkpoint = destination_geometry["coordinates"][
        random_destination_linestring_checkpoint_index]

    pathfinding(transportation_start_index, random_origin_linestring_checkpoint,
                                     transportation_end_index, random_destination_linestring_checkpoint)


if __name__ == "__main__":
    iterate_over_paths()