# -*- coding: utf-8 -*-
import copy
import json
import multiprocessing
import os
import random
import sys
from time import sleep

import pandas as pd
from flask import Flask, request
from flask_cors import CORS, cross_origin
from joblib import Parallel, delayed
from termcolor import colored
import plotly.graph_objects as go
from dash import Dash, dcc, html, Output, Input, callback, State

from database import get_database
from models.ActorLog import ActorLog
from models.actors import *
from helpers import get_closest_intersection, get_closest_street_point_index
from models.navigation import NavigationRoute

mapbox_token = "pk.eyJ1IjoiYm9jaWFuNjciLCJhIjoiY2xuazV3YjB1MGsxNzJqczNjMjRnaXlqYiJ9.C2I3bmAseZVgWraJbHy3zA"

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


class Map:
    global board
    global c
    global iteration
    global is_running

    def __init__(self):
        self.db = get_database()
        #self.housenumber_df = gpd.read_file("tiles/mittweida.housenumber.geojson")
        with open("tiles/mittweida.transportation_name.geojson") as f:
            self.transportations = json.load(f)
        #self.transportations = gpd.read_file("tiles/mittweida.transportation.geojson")
        #self.transportation_names = gpd.read_file("tiles/mittweida.transportation_name.geojson")
        self.transportations_collection = self.db["transportations-name"]
        self.intersections_collection = self.db["intersections-name"]
        self.all_intersections = list(self.intersections_collection.find({}))
        self.navigation_collection = self.db["navigation"]
        self.change_road_possibility = 50
        self.grid_length = 4
        self.step_size_divider = 2
        self.seed = 123456789
        self.new_logs = []

    def get_actors(self):
        actors = []
        for row in board:
            actors.extend(row)
        return actors

    def terminate(self):
        global is_running
        is_running = False
        sleep(1)

    def init_board(self):
        global board
        global iteration
        iteration = 0
        board = []
        actor_index = 0
        for column_index in range(0, self.grid_length):
            column = []
            for row_index in range(0, self.grid_length):
                #coords = get_coordinate_for_field(row_index, column_index)
                coords = self.get_random_actor_coordinate()
                column.append(Criminal(actor_index, coords, 0))
                actor_index += 1
            board.append(column)

    def show_terminal_board(self):
        cls()
        row_nr = 0
        for r in board:
            col_nr = 0
            line = colored("|", 'black')
            for c in r:
                if isinstance(board[row_nr][col_nr], Criminal):
                    item = colored("x", "red")
                elif isinstance(board[row_nr][col_nr], Police):
                    item = colored("o", "green")
                else:
                    item = colored("-", "black")

                line = line + item + colored("|", 'black')
                col_nr += 1
            row_nr += 1
            print(line)

    def start_simulation(self):
        global board
        global c
        global iteration
        global is_running

        is_running = True
        try:
            iteration = 0
            no_change = False
            while (c >= 0 and is_running is True):
                if iteration > 1:
                    no_change = True
                new_board = copy.deepcopy(board)
                iteration += 1
                print("Iteration: " + str(iteration))
                self.show_terminal_board()
                for col in range(len(board)):
                    for row in range(len(board)):
                        value = board[row][col]
                        criminal_neighbor_count = self.count_criminal(row, col)
                        if (criminal_neighbor_count == 3) and isinstance(value, Actor):
                            value = Criminal(value.id, value.x, value.y, 1)
                            new_board[row][col] = value
                            c += 1
                            no_change = False
                        elif (((criminal_neighbor_count < 2) or (criminal_neighbor_count > 3)) and
                              isinstance(value, Criminal)):
                            value = Actor(value.id, value.x, value.y)
                            new_board[row][col] = value
                            c -= 1
                            no_change = False
                board = copy.deepcopy(new_board)
                sleep(1)
                if no_change:
                    self.random_fill()
                    self.start_simulation()
        except KeyboardInterrupt:
            exit(0)
        except:
            print("Unexpected error:", sys.exc_info()[0])
            raise

    def count_criminal(self, row, col):
        n = 0
        for i in range(-1, 2):
            for j in range(-1, 2):
                if (i != 0) or (j != 0):
                    r = row + i
                    c = col + j
                    if (r >= 0) & (r < len(board)) & (c >= 0) & (c < len(board)):
                        n += 1 if isinstance(board[r][c], Criminal) else 0
        return n

    def random_fill(self, criminal_probability=30, police_probability=20):
        global board
        global c
        c = 0
        actor_index = 0

        actors = Parallel(n_jobs=multiprocessing.cpu_count(), prefer="threads")(delayed(self.create_random_actor_with_path)(i, criminal_probability, police_probability) for i in range(0, len(board) * len(board)))

        for col in range(len(board)):
            for row in range(len(board)):
                #coords = self.get_random_actor_coordinate()
                actor = actors[((len(board) * row) + col)]
                if isinstance(actor, Criminal):
                    c += 1
                board[row][col] = actor
                actor_index += 1

        self.show_terminal_board()


    def create_random_actor_with_path(self, actor_index, criminal_probability, police_probability):
        path = None
        while path == None:
            path = self.get_random_actor_path()
        random.seed(map.seed)
        map.seed += 1
        random_probability = random.random()
        max_actors = self.grid_length * self.grid_length
        if actor_index < int((criminal_probability / 100) * max_actors):
            # actor = Criminal(coords, 1)
            actor = Criminal(actor_index, None, 1)
        elif actor_index < int(((criminal_probability / 100) + (police_probability / 100)) * max_actors):
            # actor = Police(coords, -1)
            actor = Police(actor_index, None, -1)
        else:
            # actor = Actor(coords)
            actor = Actor(actor_index, None)
        actor.set_navigation_route(path, False)
        return actor

    def start_sim_with_random(self):
        self.init_board()
        self.random_fill()
        self.start_simulation()

    def start_sim_with_data(self):
        self.start_simulation()

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



    def get_random_actor_path(self, origin_street_index = None, origin_coordinates = None):
        max_docs = self.transportations_collection.count_documents({})
        route = None

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
        random_destination_linestring_checkpoint = destination_geometry["coordinates"][random_destination_linestring_checkpoint_index]

        return actor_pathfinding_from_db(random_origin_street_index, random_origin_linestring_checkpoint, random_destination_street_index, random_destination_linestring_checkpoint)





@cross_origin()
@app.route('/board/random', methods=['GET', 'POST'])
def start_sim_with_random():
    global thread
    global map
    global is_running
    if is_running:
        map.terminate()
    #thread = Thread(target=map.start_sim_with_random)
    #thread.start()
    return 'Done!'


@cross_origin()
@app.route('/board/terminate', methods=['GET', 'POST'])
def terminate():
    global thread
    global map
    map.terminate()
    return 'Terminated!'


@cross_origin()
@app.route('/board/new', methods=['POST'])
def get_data_from_ui():
    global map
    global thread
    global is_running
    global board
    data = request.get_json()
    if is_running:
        map.terminate()
    board = data
    count_criminal(data)
    #thread = Thread(target=map.start_sim_with_data)
    #thread.start()
    return "Got Data"


def count_criminal(data):
    global c
    c = 0
    for row in range(len(data)):
        for col in range(len(data)):
            if isinstance(data[col][row], Criminal):
                c += 1


def cls():
    os.system('cls' if os.name == 'nt' else 'clear')


def get_coordinate_for_field(row, column) -> (float, float):
    x_step = (bounds_mittweida["lat_max"] - bounds_mittweida["lat_min"]) / 12
    y_step = (bounds_mittweida["lon_max"] - bounds_mittweida["lon_min"]) / 12
    x = bounds_mittweida["lat_min"] + row * x_step
    y = bounds_mittweida["lon_min"] + column * y_step
    return x, y


# background=True,
# manager=background_callback_manager)
@callback(Output('graph', 'figure'),
          Output('info', 'children'),
          Output('log-container', 'children'),
          Input('interval-component', 'n_intervals'),
          Input("next-button", "n_clicks"),
          State('log-container', 'children'))
def update_graph_live(n, n_button, old_log_children):
    global fig
    data_map = fig.data[0]
    data = map.get_actors()
    #data = Parallel(n_jobs=multiprocessing.cpu_count(), prefer="threads")(delayed(actor_run_street)(actor) for actor in data)
    data = Parallel(n_jobs=multiprocessing.cpu_count(), prefer="threads")(delayed(actor_run_path)(actor) for actor in data)
    data_df = data_to_df(data)

    data_map.lat = data_df.y.values
    data_map.lon = data_df.x.values
    data_map.marker.color = data_df.color.values
    fig['layout']['uirevision'] = "foo"
    children = generate_info_table()
    new_log_children = list(reversed([i.log_to_div() for i in map.new_logs])) + old_log_children
    map.new_logs.clear()
    return fig, children, new_log_children


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

    return best_connection


def actor_run_path(actor):
    if actor.coordinates.direction_checkmark_x == actor.coordinates.x and actor.coordinates.direction_checkmark_y == actor.coordinates.y:
        navigation_route = actor.navigation_route.get_route()
        if actor.coordinates.x == navigation_route[0] and actor.coordinates.y == navigation_route[1]:
            actor.navigation_route.step += 1
            if actor.navigation_route.step >= len(actor.navigation_route.streets):
                # set other route
                path = None
                while path == None:
                    path = map.get_random_actor_path(actor.navigation_route.streets[-1],
                                                     [actor.coordinates.x, actor.coordinates.y])
                actor.set_navigation_route(path, True)
                actor.set_navigation_step(0)
                map.new_logs.append(ActorLog(actor.id, actor.color, "New Path", f"{actor.coordinates.x}, {actor.coordinates.y}"))
                return actor
            else:
                actor.set_navigation_step(actor.navigation_route.step)
                street_id = actor.navigation_route.streets[actor.navigation_route.step]
                street_name = map.transportations_collection.find_one({"id": street_id})["properties"]["name"]
                map.new_logs.append(ActorLog(actor.id, actor.color, "Next Navigation Point", f"{street_name}"))

        street = map.transportations_collection.find_one({"id": actor.navigation_route.streets[actor.navigation_route.step - 1]})
        linestrings = street["geometry"]["coordinates"]
        linestring_index = get_closest_street_point_index([actor.coordinates.x, actor.coordinates.y], linestrings)
        if linestring_index == 0:
            next_linestring = linestrings[1]
        elif linestring_index == len(linestrings) - 1:
            next_linestring = linestrings[-2]
        else:
            direction_linestrings = [linestrings[linestring_index + 1], linestrings[linestring_index - 1]]
            next_linestring = direction_linestrings[get_closest_street_point_index(actor.navigation_route.get_route(), direction_linestrings)]

        follow_linestring_or_destination = [next_linestring, actor.navigation_route.get_route()]
        next_linestring = follow_linestring_or_destination[get_closest_street_point_index(
            [actor.coordinates.x, actor.coordinates.y], follow_linestring_or_destination)
        ]

        actor.coordinates.previous_checkmark_x = actor.coordinates.x
        actor.coordinates.previous_checkmark_y = actor.coordinates.y
        actor.coordinates.direction_checkmark_x = next_linestring[0]
        actor.coordinates.direction_checkmark_y = next_linestring[1]

    # Walking speed
    coordinate_gap_x = abs(actor.coordinates.previous_checkmark_x - actor.coordinates.direction_checkmark_x)
    coordinate_step_x = coordinate_gap_x / map.step_size_divider
    coordinate_gap_y = abs(actor.coordinates.previous_checkmark_y - actor.coordinates.direction_checkmark_y)
    coordinate_step_y = coordinate_gap_y / map.step_size_divider

    # Walk
    if actor.coordinates.x < actor.coordinates.direction_checkmark_x:
        actor.coordinates.x += coordinate_step_x
        if actor.coordinates.x > actor.coordinates.direction_checkmark_x:
            actor.coordinates.x = actor.coordinates.direction_checkmark_x
    else:
        actor.coordinates.x -= coordinate_step_x
        if actor.coordinates.x < actor.coordinates.direction_checkmark_x:
            actor.coordinates.x = actor.coordinates.direction_checkmark_x

    if actor.coordinates.y < actor.coordinates.direction_checkmark_y:
        actor.coordinates.y += coordinate_step_y
        if actor.coordinates.y > actor.coordinates.direction_checkmark_y:
            actor.coordinates.y = actor.coordinates.direction_checkmark_y
    else:
        actor.coordinates.y -= coordinate_step_y
        if actor.coordinates.y < actor.coordinates.direction_checkmark_y:
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

def actor_run_street(actor):
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
                actor.coordinates.direction_positive = random.randint(0,1) == 0
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
    coordinate_gap_x = abs(actor.coordinates.previous_checkmark_x - actor.coordinates.direction_checkmark_x)
    coordinate_step_x = coordinate_gap_x / map.step_size_divider
    coordinate_gap_y = abs(actor.coordinates.previous_checkmark_y - actor.coordinates.direction_checkmark_y)
    coordinate_step_y = coordinate_gap_y / map.step_size_divider

    # Walk
    if actor.coordinates.x < actor.coordinates.direction_checkmark_x:
        actor.coordinates.x += coordinate_step_x
        if actor.coordinates.x > actor.coordinates.direction_checkmark_x:
            actor.coordinates.x = actor.coordinates.direction_checkmark_x
    else:
        actor.coordinates.x -= coordinate_step_x
        if actor.coordinates.x < actor.coordinates.direction_checkmark_x:
            actor.coordinates.x = actor.coordinates.direction_checkmark_x

    if actor.coordinates.y < actor.coordinates.direction_checkmark_y:
        actor.coordinates.y += coordinate_step_y
        if actor.coordinates.y > actor.coordinates.direction_checkmark_y:
            actor.coordinates.y = actor.coordinates.direction_checkmark_y
    else:
        actor.coordinates.y -= coordinate_step_y
        if actor.coordinates.y < actor.coordinates.direction_checkmark_y:
            actor.coordinates.y = actor.coordinates.direction_checkmark_y

    return actor


@callback(Output('submit-button', 'n_clicks'),
          Input('submit-button', 'n_clicks'),
          Input('criminal-slider', 'value'),
          Input('police-slider', 'value'),
          Input('road-slider', 'value'),
          Input('seed_input', 'value'))
def init_random_using_slider(button_value, criminal_value, police_value, change_road_value, seed_value):
    global thread
    global map
    global is_running
    if button_value:
        if is_running:
            map.terminate()
        map.seed = seed_value
        map.init_board()
        map.change_road_possibility = change_road_value
        map.random_fill(criminal_value, police_value)
        #thread = Thread(target=map.start_simulation)
        #thread.start()
    return 0


def generate_info_table():
    actor = 0
    police = 0
    criminal = 0
    for row in board:
        for value in row:
            if isinstance(value, Criminal):
                criminal += 1
            elif isinstance(value, Actor):
                actor += 1
            elif isinstance(value, Police):
                police += 1
    return html.Div(children=[
        html.Div(children=["Actors: " + str(actor)]),
        html.Div(children=["Criminals: " + str(criminal)]),
        html.Div(children=["Police: " + str(police)])
    ])


def data_to_df(data):
    data_attrs = []
    for item in data:
        item_vars = {
                        "z": item.z,
                        "color": item.color,
                        "id": item.id
                    } | vars(item.coordinates)
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

    data = map.get_actors()
    data_df = data_to_df(data)
    fig = go.Figure(go.Scattermapbox(
        lat=data_df.y.values,
        lon=data_df.x.values,
        mode='markers',
        marker=go.scattermapbox.Marker(
            size=12,
            color=data_df.color.values
        ),
        hoverinfo="lat+lon+text",
        hovertext=data_df.id
    ))

    fig.update_layout(
        mapbox=dict(center=go.layout.mapbox.Center(lat=50.9872722, lon=12.9737849), zoom=14, accesstoken=mapbox_token),
        mapbox_style="satellite-streets",
        #mapbox_style="white-bg",
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
        html.Div(id='info'),
        html.Div(id='input-container', children=[
            html.Label("Criminals in %", htmlFor='criminal-slider'),
            dcc.Slider(
                0,
                100,
                step=1,
                value=30,
                id='criminal-slider'
            ),
            html.Label("Police in %", htmlFor='police-slider'),
            dcc.Slider(
                0,
                100,
                step=1,
                value=20,
                id='police-slider'
            ),
            html.Label("Possibility to change roads in %", htmlFor='road-slider'),
            dcc.Slider(
                0,
                100,
                step=1,
                value=map.change_road_possibility,
                id='road-slider'
            ),
            html.Label("Random seed", htmlFor='seed_input'),
            dcc.Input(
                id="seed_input",
                type="number",
                value=start_seed,
            ),

            html.Button(id='submit-button', children='Submit'),
        ]),
        html.Div(style={"display": "flex", "flex-direction": "row", "height": "100vh"}, children=[
            dcc.Graph(figure=fig, id='graph', style={"flex": "5"}),
            html.Div(id="log-container",
                     style={"padding":"10px",
                            "display": "flex",
                            "overflow": "scroll",
                            "flex": "1",
                            "flex-direction": "column-reverse"},
                     children=[html.P("Start of the logs")])
        ]),
        dcc.Interval(
            id='interval-component',
            interval=200 * 500,  # in milliseconds
            n_intervals=0
        ),
        html.Button("Next Step", id="next-button")
    ], style={"height": "100vh"})

    dash_app.run_server(debug=True, use_reloader=True)