# -*- coding: utf-8 -*-
import json
import math
import multiprocessing
import os
import random
from enum import Enum, auto
from time import sleep
from dotenv import load_dotenv

import pandas as pd
import plotly.graph_objects as go
from dash import Dash, dcc, html, Output, Input, callback, State
from flask import Flask
from flask_cors import CORS
from joblib import Parallel, delayed
import plotly.express as px

from database import get_database
from helpers import get_closest_intersection, get_closest_street_point_index, reverse_route
from initial_spawn_places import InitialSpawnPlaces
from models.ActorLog import ActorLog, ActorLogAction, ActorEventLog
from models.actors import *
from models.navigation import NavigationRoute
from statictics_writer import StatisticsWriter

load_dotenv()
mapbox_token = os.getenv('MAPBOX_TOKEN')

app = Flask(__name__)
CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'
# Configure the count of pixels:
CELL_COUNT = 144

color = (0, 0, 255)  # Blau

bounds_mittweida = {"lat_min": 50.979491, "lat_max": 50.995568, "lon_min": 12.951120, "lon_max": 12.991011}

global thread
global map
global fig
global infochart

class Events(Enum):
    ROBBING=auto(),
    PRISON=auto()

class Map:
    global c
    global iteration
    global is_running

    def __init__(self):
        self.db = get_database()
        self.actors = []
        # Collections
        # self.housenumber_df = gpd.read_file("tiles/mittweida.housenumber.geojson")
        with open("tiles/mittweida.transportation_name.geojson") as f:
            self.transportations = json.load(f)
        self.transportations_collection = self.db["transportations-name"]
        self.intersections_collection = self.db["intersections-name"]
        self.all_intersections = list(self.intersections_collection.find({}))
        self.navigation_collection = self.db["navigation"]

        # Changeable properties
        self.change_road_possibility = 50
        self.step_size_divider = 2
        self.seed = 2463647679
        self.actor_count = 60
        self.penalty = 12
        self.penalty_boundaries = [0, 60]
        self.default_speed = 30
        self.police_extra_speed = 20
        self.police_percent = 20
        self.criminal_percent = 30
        self.starting_location = "ALL"

        # Logging
        self.new_logs = []
        self.dashboard = {
            str(Events.ROBBING): 0,
            str(Events.PRISON): 0,
        }
        self.additionals = []
        self.criminal_count = 0
        self.police_count = 0
        self.civil_count = 0
        self.logger = StatisticsWriter()

        self.criminal_to_remove = []

    def terminate(self):
        global is_running
        is_running = False
        sleep(1)

    def init_board(self):
        global iteration
        iteration = 0
        self.actors.clear()
        for i in range(0, self.actor_count):
            # coords = get_coordinate_for_field(row_index, column_index)
            coords = self.get_random_actor_coordinate()
            self.actors.append(Criminal(i, coords, 0))

    def random_fill(self, criminal_probability=30, police_probability=20):
        init_seed = self.seed
        global c
        c = 0

        self.actors = Parallel(n_jobs=multiprocessing.cpu_count(), prefer="threads")(
            delayed(self.create_random_actor_with_path)(i, criminal_probability, police_probability) for i in range(0, self.actor_count))

        for actor_index, actor in enumerate(self.actors):
            # coords = self.get_random_actor_coordinate()
            if isinstance(actor, Criminal):
                c += 1
        self.logger.init_parameter(self.actor_count, self.criminal_percent, self.police_percent, self.penalty, self.default_speed, self.police_extra_speed, init_seed)

    def create_random_actor_with_path(self, actor_index, criminal_probability, police_probability):
        path = None
        possible_street_ids = InitialSpawnPlaces.get_street_ids_for_location(map.starting_location)
        while path is None:
            if possible_street_ids is None:
                origin_street_id = None
                random_origin_linestring_checkpoint = None
            else:
                random.seed(map.seed)
                map.seed += 1
                origin_street_id = random.choice(possible_street_ids)
                street = self.transportations_collection.find_one({"id": origin_street_id})
                origin_geometry = street["geometry"]
                random.seed(map.seed)
                map.seed += 1
                random_origin_linestring_checkpoint_index = random.randint(0, len(origin_geometry["coordinates"]) - 1)
                random_origin_linestring_checkpoint = origin_geometry["coordinates"][
                    random_origin_linestring_checkpoint_index]
            path = self.get_random_actor_path(origin_street_index=origin_street_id, origin_coordinates=random_origin_linestring_checkpoint)

        if actor_index < int((criminal_probability / 100) * self.actor_count):
            # actor = Criminal(coords, 1)
            actor = Criminal(actor_index, None, 1)
        elif actor_index < int(((criminal_probability / 100) + (police_probability / 100)) * self.actor_count):
            # actor = Police(coords, -1)
            actor = Police(actor_index, None, -1)
        else:
            # actor = Actor(coords)
            actor = Civilian(actor_index, None)
        actor.set_navigation_route(path, False)
        return actor

    def get_random_actor_coordinate(self):
        max_docs = self.transportations_collection.count_documents({})
        while True:
            random.seed(map.seed)
            map.seed += 1
            random_street_index = random.randint(1, max_docs - 1)
            street = self.transportations_collection.find_one({"id": random_street_index})
            geometry = street["geometry"]
            if geometry["type"] == "LineString":
                break

        random.seed(map.seed)
        map.seed += 1
        random_linestring_checkpoint_index = random.randint(0, len(geometry["coordinates"]) - 1)
        random_linestring_checkpoint = geometry["coordinates"][random_linestring_checkpoint_index]
        if random_linestring_checkpoint_index > 0:
            previous_linestring_checkpoint = geometry["coordinates"][random_linestring_checkpoint_index - 1]
            positive_direction = True
        else:
            previous_linestring_checkpoint = geometry["coordinates"][random_linestring_checkpoint_index + 1]
            positive_direction = False
        return ActorCoordinate(random_street_index,
                               positive_direction,
                               float(random_linestring_checkpoint[0]),
                               float(random_linestring_checkpoint[1]),
                               float(random_linestring_checkpoint[0]),
                               float(random_linestring_checkpoint[1]),
                               float(previous_linestring_checkpoint[0]),
                               float(previous_linestring_checkpoint[1]))

    def get_random_actor_path(self, origin_street_index=None, origin_coordinates=None):
        max_docs = self.transportations_collection.count_documents({})
        route = None
        random_origin_linestring_checkpoint = None
        while True:
            if origin_street_index is not None and origin_coordinates is not None:
                random_origin_street_index = origin_street_index
                random_origin_linestring_checkpoint = origin_coordinates
            else:
                random.seed(map.seed)
                map.seed += 1
                random_origin_street_index = random.randint(1, max_docs - 1)
            street = self.transportations_collection.find_one({"id": random_origin_street_index})
            origin_geometry = street["geometry"]
            random.seed(map.seed)
            map.seed += 1
            random_origin_linestring_checkpoint_index = random.randint(0, len(origin_geometry["coordinates"]) - 1)
            if random_origin_linestring_checkpoint is None:
                random_origin_linestring_checkpoint = origin_geometry["coordinates"][random_origin_linestring_checkpoint_index]
            routes = list(self.navigation_collection.find({"start": random_origin_street_index}))
            if routes is not None and len(routes) > 0:
                random.seed(map.seed)
                map.seed += 1
                route = routes[random.randint(0, len(routes) - 1)]
                break

        random_destination_street_index = route["streets"][-1]
        street = self.transportations_collection.find_one({"id": random_destination_street_index})
        destination_geometry = street["geometry"]
        random.seed(map.seed)
        map.seed += 1
        random_destination_linestring_checkpoint_index = random.randint(0, len(destination_geometry["coordinates"]) - 1)
        random_destination_linestring_checkpoint = destination_geometry["coordinates"][
            random_destination_linestring_checkpoint_index]

        return actor_pathfinding_from_db(random_origin_street_index, random_origin_linestring_checkpoint,
                                         random_destination_street_index, random_destination_linestring_checkpoint)

    def generate_info_table(self):
        civilian = 0
        police = 0
        criminal = 0
        for value in self.actors:
            if isinstance(value, Criminal):
                criminal += 1
            elif isinstance(value, Police):
                police += 1
            elif isinstance(value, Civilian):
                civilian += 1
        self.criminal_count = criminal
        self.police_count = police
        self.civil_count = civilian
        return html.Div(children=[
            html.Div(children=["Civilian: " + str(civilian)]),
            html.Div(children=["Police: " + str(police)]),
            html.Div(children=["Criminals: " + str(criminal)]),
            html.Div(children=["Civilians Robbed: " + str(self.dashboard[str(Events.ROBBING)])])
        ])


def count_criminal(data):
    global c
    c = 0
    for row in range(len(data)):
        for col in range(len(data)):
            if isinstance(data[col][row], Criminal):
                c += 1


def get_coordinate_for_field(row, column) -> (float, float):
    x_step = (bounds_mittweida["lat_max"] - bounds_mittweida["lat_min"]) / 12
    y_step = (bounds_mittweida["lon_max"] - bounds_mittweida["lon_min"]) / 12
    x = bounds_mittweida["lat_min"] + row * x_step
    y = bounds_mittweida["lon_min"] + column * y_step
    return x, y


def actor_pathfinding_from_db(origin_street_id, origin_coordinates, destination_street_id, destination_coordinates):
    # search for path with intersections
    best_connection = None
    origin_road_navigation = NavigationRoute()
    destination_road_navigation = NavigationRoute()
    origin_road_navigation.add_street({"id": origin_street_id, "coordinates": origin_coordinates})
    destination_road_navigation.add_street({"id": destination_street_id, "coordinates": destination_coordinates})
    connections_from_origin = [origin_road_navigation]
    if origin_street_id == destination_street_id:
        connections_from_origin[0].add_street({"id": destination_street_id, "coordinates": destination_coordinates})
        best_connection = connections_from_origin[0]
    else:
        route = map.navigation_collection.find_one({"start": origin_street_id, "end": destination_street_id})
        if route is not None:
            best_connection = NavigationRoute()
            best_connection.route = route["route"]
            best_connection.streets = route["streets"]
        else:
            route = map.navigation_collection.find_one({"end": origin_street_id, "start": destination_street_id})
            if route is not None:
                best_connection = NavigationRoute()
                best_connection.route = reverse_route(route["route"])
                best_connection.streets = list(reversed(route["streets"]))

    return best_connection


def actor_run_path(actor, distance=None):
    if actor.coordinates.direction_checkmark_x == actor.coordinates.x and actor.coordinates.direction_checkmark_y == actor.coordinates.y:
        navigation_route = actor.navigation_route.get_route()
        if actor.coordinates.x == navigation_route[0] and actor.coordinates.y == navigation_route[1]:
            if actor.navigation_route.step + 1 >= len(actor.navigation_route.streets):
                # set other route
                path = None
                while path is None:
                    path = map.get_random_actor_path(actor.navigation_route.streets[-1],
                                                     [actor.coordinates.x, actor.coordinates.y])
                actor.set_navigation_route(path, True)
                actor.set_navigation_step(0)
                map.new_logs.append(
                    ActorLog(actor.id, actor.color, ActorLogAction.NEW_PATH, f"{actor.coordinates.x}, {actor.coordinates.y}"))
                return actor
            else:
                actor.navigation_route.step += 1
                actor.set_navigation_step(actor.navigation_route.step)
                try:
                    street_id = actor.navigation_route.streets[actor.navigation_route.step]
                    street_name = map.transportations_collection.find_one({"id": street_id})["properties"]["name"]
                    map.new_logs.append(ActorLog(actor.id, actor.color, ActorLogAction.NEXT_NAVIGATION_POINT, street_name))
                except:
                    pass

        street = map.transportations_collection.find_one(
            {"id": actor.navigation_route.streets[actor.navigation_route.step - 1]})
        linestrings = street["geometry"]["coordinates"]
        linestring_index = get_closest_street_point_index([actor.coordinates.x, actor.coordinates.y], linestrings)
        if linestring_index == 0:
            next_linestring = linestrings[1]
        elif linestring_index == len(linestrings) - 1:
            next_linestring = linestrings[-2]
        else:
            direction_linestrings = [linestrings[linestring_index + 1], linestrings[linestring_index - 1]]
            next_linestring = direction_linestrings[
                get_closest_street_point_index(actor.navigation_route.get_route(), direction_linestrings)]

        follow_linestring_or_destination = [next_linestring, actor.navigation_route.get_route()]
        next_linestring = follow_linestring_or_destination[get_closest_street_point_index(
            [actor.coordinates.x, actor.coordinates.y], follow_linestring_or_destination)
        ]

        actor.coordinates.previous_checkmark_x = actor.coordinates.x
        actor.coordinates.previous_checkmark_y = actor.coordinates.y
        actor.coordinates.direction_checkmark_x = next_linestring[0]
        actor.coordinates.direction_checkmark_y = next_linestring[1]

    # Walking speed
    coordinate_gap_x = abs(actor.coordinates.x - actor.coordinates.direction_checkmark_x)
    coordinate_gap_y = abs(actor.coordinates.y - actor.coordinates.direction_checkmark_y)

    route_length = math.sqrt(math.pow(coordinate_gap_x, 2) + math.pow(coordinate_gap_y, 2))
    if distance is not None:
        max_distance_per_step = distance
    elif isinstance(actor, Police):
        max_distance_per_step = (map.default_speed + map.police_extra_speed) / 100000
    else:
        max_distance_per_step = map.default_speed / 100000

    if route_length < max_distance_per_step:
        actor.coordinates.x = actor.coordinates.direction_checkmark_x
        actor.coordinates.y = actor.coordinates.direction_checkmark_y
        distance_left = max_distance_per_step - route_length
        actor_run_path(actor, distance_left)
    elif route_length >= max_distance_per_step:
        scale_factor = max_distance_per_step / route_length
        coordinate_step_x = scale_factor * coordinate_gap_x
        coordinate_step_y = scale_factor * coordinate_gap_y

        if actor.coordinates.x < actor.coordinates.direction_checkmark_x:
            actor.coordinates.x += coordinate_step_x
        else:
            actor.coordinates.x -= coordinate_step_x

        if actor.coordinates.y < actor.coordinates.direction_checkmark_y:
            actor.coordinates.y += coordinate_step_y
        else:
            actor.coordinates.y -= coordinate_step_y
    else:
        actor.coordinates.x = actor.coordinates.direction_checkmark_x
        actor.coordinates.y = actor.coordinates.direction_checkmark_y

    return actor


def find_all_connections(from_street_id):
    for i in map.all_intersections:
        if i["id"] == from_street_id:
            intersections = i["intersections"]
            result = []
            for r in intersections:
                result.append({"id": r["id"], "coordinates": [r["coordinates"][1], r["coordinates"][0]]})
            return result


def actor_run_street(actor, distance=None):
    street = map.transportations_collection.find_one({"id": actor.coordinates.street_id})
    linestrings = street["geometry"]["coordinates"]
    linestring_index = get_closest_street_point_index(
        [actor.coordinates.direction_checkmark_x, actor.coordinates.direction_checkmark_y], linestrings)
    if actor.coordinates.direction_checkmark_x == actor.coordinates.x and actor.coordinates.direction_checkmark_y == actor.coordinates.y:
        # Use intersection if possible
        intersections = map.intersections_collection.find_one({"id": actor.coordinates.street_id})
        cross_on_intersection = False
        if len(intersections["intersections"]) > 0:
            closest_intersection = get_closest_intersection([actor.coordinates.x, actor.coordinates.y], intersections)
            random.seed(map.seed)
            map.seed += 1
            if (abs(closest_intersection["coordinates"][1] - actor.coordinates.x) < 0.0001
                    and abs(closest_intersection["coordinates"][0] - actor.coordinates.y) < 0.0001
                    and random.randint(0, 100) <= map.change_road_possibility):
                actor.coordinates.street_id = closest_intersection["id"]
                cross_on_intersection = True
                # next point on new street (new coordinate 'to')
                next_street = map.transportations_collection.find_one({"id": closest_intersection["id"]})
                linestrings = next_street["geometry"]["coordinates"]
                linestring_index = get_closest_street_point_index(
                    [closest_intersection["coordinates"][1], closest_intersection["coordinates"][0]], linestrings)
                next_linestring = [0, 0]
                for linestring in linestrings:
                    if abs(linestring[0] - actor.coordinates.x) + abs(linestring[1] - actor.coordinates.y) < \
                            abs(next_linestring[0] - actor.coordinates.x) + abs(
                        next_linestring[1] - actor.coordinates.y):
                        next_linestring = linestring

                # nearest intersection starting point (new coordinate 'from')
                actor.coordinates.previous_checkmark_x = linestrings[linestring_index][1]
                actor.coordinates.previous_checkmark_y = linestrings[linestring_index][0]
                actor.coordinates.direction_checkmark_x = next_linestring[0]
                actor.coordinates.direction_checkmark_y = next_linestring[1]
                random.seed(map.seed)
                map.seed += 1
                actor.coordinates.direction_positive = random.randint(0, 1) == 0
                if next_linestring == [actor.coordinates.direction_checkmark_x,
                                       actor.coordinates.direction_checkmark_y]:
                    cross_on_intersection = False

        # Walk on street
        if not cross_on_intersection:
            if actor.coordinates.direction_positive and linestring_index < len(linestrings) - 1:
                next_linestring = linestrings[linestring_index + 1]
            elif actor.coordinates.direction_positive and linestring_index == len(linestrings) - 1:
                next_linestring = linestrings[linestring_index - 1]
                actor.coordinates.direction_positive = not actor.coordinates.direction_positive
            elif not actor.coordinates.direction_positive and linestring_index > 0:
                next_linestring = linestrings[linestring_index - 1]
            elif not actor.coordinates.direction_positive and linestring_index == 0:
                next_linestring = linestrings[linestring_index + 1]
                actor.coordinates.direction_positive = not actor.coordinates.direction_positive

            actor.coordinates.previous_checkmark_x = actor.coordinates.direction_checkmark_x
            actor.coordinates.previous_checkmark_y = actor.coordinates.direction_checkmark_y
            actor.coordinates.direction_checkmark_x = next_linestring[0]
            actor.coordinates.direction_checkmark_y = next_linestring[1]

        # Walking speed
        coordinate_gap_x = abs(actor.coordinates.x - actor.coordinates.direction_checkmark_x)
        coordinate_gap_y = abs(actor.coordinates.y - actor.coordinates.direction_checkmark_y)

        route_length = math.sqrt(math.pow(coordinate_gap_x, 2) + math.pow(coordinate_gap_y, 2))
        if distance is not None:
            max_distance_per_step = distance
        elif isinstance(actor, Police):
            max_distance_per_step = (map.default_speed + map.police_extra_speed) / 100000
        else:
            max_distance_per_step = map.default_speed / 100000

        if route_length < max_distance_per_step:
            actor.coordinates.x = actor.coordinates.direction_checkmark_x
            actor.coordinates.y = actor.coordinates.direction_checkmark_y
            distance_left = max_distance_per_step - route_length
            actor_run_path(actor, distance_left)
        elif route_length >= max_distance_per_step:
            scale_factor = max_distance_per_step / route_length
            coordinate_step_x = scale_factor * coordinate_gap_x
            coordinate_step_y = scale_factor * coordinate_gap_y

            if actor.coordinates.x < actor.coordinates.direction_checkmark_x:
                actor.coordinates.x += coordinate_step_x
            else:
                actor.coordinates.x -= coordinate_step_x

            if actor.coordinates.y < actor.coordinates.direction_checkmark_y:
                actor.coordinates.y += coordinate_step_y
            else:
                actor.coordinates.y -= coordinate_step_y
        else:
            actor.coordinates.x = actor.coordinates.direction_checkmark_x
            actor.coordinates.y = actor.coordinates.direction_checkmark_y

        return actor


def simulate_actor_actions(actor_index, actor):
    # Criminal action
    if isinstance(actor, Criminal):
        if actor.robbed is not None:
            return actor
        for other_actor_id, other_actor in enumerate(map.actors):
            if actor.id == other_actor.id or not isinstance(other_actor, Civilian):
                continue

            willing_to_rob = will_rob_actor(actor, other_actor)
            if actor.can_touch_actor(other_actor) and other_actor.event_by_id != actor.id and willing_to_rob:
                # criminal robs civilian
                actor.set_robbed_id(other_actor_id)
                other_actor.set_was_robbed_by(actor.id)
                street_id = actor.navigation_route.streets[actor.navigation_route.step]
                street_name = map.transportations_collection.find_one({"id": street_id})["properties"]["name"]
                map.new_logs.append(ActorEventLog(actor.id, ActorLogAction.ROBBING, street_name, other_actor_id))
                map.dashboard[str(Events.ROBBING)] += 1
                map.additionals.append([actor.coordinates.x, actor.coordinates.y, "yellow"])

                # criminal uses new route
                path = None
                while path is None:
                    path = map.get_random_actor_path(actor.navigation_route.streets[actor.navigation_route.step],
                                                     [actor.coordinates.x, actor.coordinates.y])
                actor.set_navigation_route(path, True)
                actor.set_navigation_step(0)
                try:
                    street_id = actor.navigation_route.streets[actor.navigation_route.step]
                    street_name = map.transportations_collection.find_one({"id": street_id})["properties"]["name"]
                    map.new_logs.append(
                        ActorLog(actor.id, actor.color, ActorLogAction.FLEES, street_name))
                except:
                    pass
        if actor.robbed_counter is not None:
            actor.robbed_counter += 1
            if actor.robbed_counter >= 60:
                actor.set_incognito()

            # police seeks criminal
            near_police_actors = get_near_police_actors(actor)
            for police_actor in near_police_actors:
                if police_actor.suspect_id is None:
                    path = actor_pathfinding_from_db(
                        police_actor.navigation_route.streets[police_actor.navigation_route.step],
                        [police_actor.coordinates.x, police_actor.coordinates.y],
                        actor.coordinates.street_id,
                        [actor.coordinates.x, actor.coordinates.y])
                    if path is not None:
                        police_actor.set_navigation_route(path, True)
                        police_actor.set_navigation_step(0)
                        map.new_logs.append(
                            ActorLog(police_actor.id, police_actor.color, ActorLogAction.GOES_LAST_SUSPECT_PLACE,
                                     f"{actor.coordinates.x}, {actor.coordinates.y}"))
                        police_actor.suspect_id = actor.id
                    else:
                        police_actor.suspect_id = None

        # Police action
    elif isinstance(actor, Police):
        for other_actor_id, other_actor in enumerate(map.actors):
            if actor.id == other_actor.id or not isinstance(other_actor, Criminal):
                continue

            if actor.can_touch_actor(other_actor) and other_actor.robbed is not None:
                # criminal is caught and goes to prison
                #map.criminal_to_remove.append(other_actor.id)
                map.actors.remove(other_actor)
                map.new_logs.append(
                    ActorLog(other_actor.id, "green", ActorLogAction.SEND_TO_PRISON,
                             f"{actor.id}"))
                map.dashboard[str(Events.PRISON)] += 1
                map.additionals.append([actor.coordinates.x, actor.coordinates.y, "blue"])

    return actor


def will_rob_actor(actor, other_actor):
    random.seed(map.seed)
    map.seed += 1
    random_penalty_month_score = random.randint(map.penalty_boundaries[0], map.penalty_boundaries[1])
    if random_penalty_month_score >= map.penalty:
        return True
    return False


def get_near_police_actors(actor, count=3):
    distances = []
    for other_actor in map.actors:
        if other_actor.id != actor.id and isinstance(other_actor, Police):
            distance = abs(actor.coordinates.x - other_actor.coordinates.x) + abs(actor.coordinates.y - other_actor.coordinates.y)
            distances.append({"actor": other_actor, "distance": distance})
    distances = sorted(distances, key=lambda d: d["distance"])
    return [item["actor"] for item in distances[:count]]




# background=True,
# manager=background_callback_manager)
@callback(Output('graph', 'figure'),
          #Output('info', 'children'),
          Output('log-container', 'children'),
          Output('infochart', 'figure'),
          Input('interval-component', 'n_intervals'),
          Input("next-button", "n_clicks"),
          State('log-container', 'children'))
def update_graph_live(n, n_button, old_log_children):
    global fig
    global infochart
    map.additionals.clear()
    data_map = fig.data[0]
    # data = Parallel(n_jobs=multiprocessing.cpu_count(), prefer="threads")(delayed(actor_run_street)(actor) for actor in data)
    actors = map.actors
    actors = Parallel(n_jobs=multiprocessing.cpu_count(), prefer="threads")(
        delayed(actor_run_path)(actor) for actor in actors)
    actors = Parallel(n_jobs=multiprocessing.cpu_count(), prefer="threads")(
        delayed(simulate_actor_actions)(actor_index, actor) for actor_index, actor in enumerate(actors))
    #map.actors = actors
    #for i in map.actors:
    #    if i.id in map.criminal_to_remove:
    #        map.actors.remove(i)
    #        map.criminal_to_remove.remove(i.id)
    data_df = actors_to_df(actors)
    additional_data = additionals_to_df(map.additionals)
    children = map.generate_info_table()
    map.logger.write_csv(map.police_count, map.criminal_count, map.civil_count,
                         map.dashboard[str(Events.ROBBING)], map.dashboard[str(Events.PRISON)])

    data_map.lat = data_df.y.values
    data_map.lon = data_df.x.values
    data_map.text = data_df.id.values
    data_map.marker.color = data_df.color.values

    additional_map = fig.data[1]
    if len(map.additionals) > 0:
        additional_map.lat = additional_data.y.values
        additional_map.lon = additional_data.x.values
        additional_map.marker.color = additional_data.color.values
    else:
        additional_map.lat = []
        additional_map.lon = []
    fig['layout']['uirevision'] = "foo"

    infochart_data = map.logger.data_to_df()
    infochart = px.line(infochart_data, x="iteration", y="y", color="category")
    infochart['data'][0]['line']['dash'] = "dot"
    infochart['data'][1]['line']['dash'] = "dot"
    infochart['data'][2]['line']['dash'] = "dot"
    infochart['data'][3]['line']['dash'] = "solid"
    infochart['data'][4]['line']['dash'] = "longdash"

    infochart['layout']['uirevision'] = "foo"

    new_log_children = list(reversed([i.log_to_div() for i in map.new_logs])) + old_log_children
    map.new_logs.clear()
    return fig, new_log_children, infochart


@callback(Output('submit-button', 'n_clicks'),
          Input('submit-button', 'n_clicks'),
          Input('criminal-slider', 'value'),
          Input('police-slider', 'value'),
          Input('seed_input', 'value'),
          Input('speed-slider', 'value'),
          Input('penalty-slider', 'value'),
          Input('police-mobility-slider', 'value'),
          Input('starting-locations-radio', 'value'))
def init_random_using_slider(button_value, criminal_value, police_value, seed_value, speed_value, penalty_months, police_mobility_value, starting_location_value):
    global thread
    global map
    global is_running
    if button_value:
        if is_running:
            map.terminate()
        map = Map()
        map.seed = seed_value
        map.default_speed = speed_value
        map.penalty = penalty_months
        map.police_extra_speed = police_mobility_value
        map.police_percent = police_value
        map.criminal_percent = criminal_value
        map.starting_location = starting_location_value
        map.init_board()
        map.random_fill(map.criminal_percent, map.police_percent)
    return 0


def actors_to_df(data):
    data_attrs = []
    for item in data:
        item_vars = {
            "z": item.z,
            "color": item.color,
            "id": str(item.id)
        } | vars(item.coordinates)
        data_attrs.append(item_vars)
    return pd.DataFrame(data_attrs)


def additionals_to_df(data):
    data_attrs = []
    for item in data:
        item_vars = {"x": item[0], "y": item[1], "color": item[2]}
        data_attrs.append(item_vars)
    return pd.DataFrame(data_attrs)


if __name__ == "__main__":
    global map
    global is_running
    global fig

    os.system('color')
    is_running = False
    map = Map()
    start_seed = map.seed
    map.init_board()
    map.random_fill()

    data = map.actors
    additional_data = additionals_to_df(map.additionals)
    data_df = actors_to_df(data)

    fig = go.Figure(go.Scattermapbox(
        lat=data_df.y.values,
        lon=data_df.x.values,
        mode="markers+text",
        marker=go.scattermapbox.Marker(
            size=12,
            color=data_df.color.values
        ),
        text=data_df.id.values,
        textposition="top center",
        textfont={
            "size": 18,
            "color": "white"
    },
        hoverinfo="lat+lon",
    ))

    fig.add_trace(go.Scattermapbox(
        lat=[],
        lon=[],
        mode="markers",
        marker=go.scattermapbox.Marker(
            size=36,
            color="yellow"
        ),
        hoverinfo="none",
        opacity=0.5
    ))

    fig.update_layout(
        mapbox=dict(center=go.layout.mapbox.Center(lat=50.9872722, lon=12.9737849), zoom=14, accesstoken=mapbox_token),
        mapbox_style="satellite-streets",
        # mapbox_style="white-bg",
        mapbox_layers=[
            {
                "below": 'traces',
                "sourcetype": "geojson",
                "source": map.transportations,
                "type": "line",
                "color": "#2e1900",
                "opacity": 1
            }
        ],
        hovermode="closest"
    )
    fig['layout']['uirevision'] = "foo"
    fig.layout.hovermode = "closest"

    dash_app = Dash(__name__, server=app)
    dash_app.layout = html.Div([
        html.Div(id='input-container', style={"padding": "20px"}, children=[
            html.Div(style={"display": "flex", "flex-direction": "row", "width": "100%"}, children=[
                html.Div(style={"width": "50%"}, children=[
                    html.Label("Criminals in %", htmlFor='criminal-slider'),
                    dcc.Slider(
                        0,
                        100,
                        step=5,
                        value=map.criminal_percent,
                        id='criminal-slider'
                    ),
                    html.Label("Police in %", htmlFor='police-slider'),
                    dcc.Slider(
                        0,
                        100,
                        step=5,
                        value=map.police_percent,
                        id='police-slider'
                    ),
                    html.Label("Penalty in Months", htmlFor='penalty-slider'),
                    dcc.Slider(
                        map.penalty_boundaries[0],
                        map.penalty_boundaries[1],
                        step=1,
                        value=map.penalty,
                        id='penalty-slider'
                    ),
                    html.Label("Starting locations", htmlFor='starting-locations-radio'),
                    dcc.RadioItems(
                        options=InitialSpawnPlaces.possible_starting_locations,
                        inline=True,
                        value=map.starting_location,
                        id="starting-locations-radio"
                    )
                ]),
                html.Div(style={"width": "50%"}, children=[
                    html.Label("General Speed", htmlFor='speed-slider'),
                    dcc.Slider(
                        1,
                        100,
                        step=10,
                        value=map.default_speed,
                        id='speed-slider'
                    ),
                    html.Label("Police Mobility Factor", htmlFor='police-mobility-slider'),
                    dcc.Slider(
                        0,
                        100,
                        step=10,
                        value=map.police_extra_speed,
                        id='police-mobility-slider'
                    ),

                    html.Label("Random seed", htmlFor='seed_input'),
                    dcc.Input(
                        id="seed_input",
                        type="number",
                        value=start_seed,
                    ),
                ])
            ]),

            html.Button(id='submit-button', children='Submit'),
        ]),
        html.Div(style={"display": "flex", "flex-direction": "row", "height": "100vh"}, children=[
            dcc.Graph(figure=fig, id='graph', style={"flex": "5"}),
            html.Div(style={"display": "flex", "flex-direction": "column", "flex": "1"}, children=[
                html.Div(id="log-container",
                         style={"padding": "10px",
                                "display": "flex",
                                "overflow": "scroll",
                                "flex": "1",
                                "flex-direction": "column-reverse"},
                         children=[html.P("Start of the logs")])
            ])

        ]),
        dcc.Interval(
            id='interval-component',
            interval=1 * 1000,  # in milliseconds
            n_intervals=0
        ),
        html.Button("Next Step", id="next-button"),
        dcc.Graph(id='infochart', style={"flex": "1", "padding": "1ßpx"}),
    ], style={"height": "100vh"})

    dash_app.run_server(debug=True, use_reloader=True)
