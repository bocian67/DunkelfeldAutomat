# -*- coding: utf-8 -*-
import copy
import json
import os
import random
import sys
from os import system, name
from threading import Thread
from time import sleep

import numpy as np
from dash import dash_table
import pandas as pd
import plotly.express as px
from flask import Flask, request
from flask_cors import CORS, cross_origin
from termcolor import colored
import plotly.graph_objects as go
from random import randrange
from dash import Dash, dcc, html, Output, Input, callback

from database import get_database
from models import *
import geopandas as gpd
from helpers import format_to_coord_list

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
        with open("tiles/mittweida.transportation.geojson") as f:
            self.transportations = json.load(f)
        #self.transportations = gpd.read_file("tiles/mittweida.transportation.geojson")
        #self.transportation_names = gpd.read_file("tiles/mittweida.transportation_name.geojson")
        self.transportations_collection = self.db["transportations"]

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
        count = 8
        for column_index in range(0, count):
            column = []
            for row_index in range(0, count):
                # coords = get_coordinate_for_field(row_index, column_index)
                coords = self.get_random_actor_coordinate()
                column.append(Criminal(coords, 0))
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
                            value = Criminal(value.x, value.y, 1)
                            new_board[row][col] = value
                            c += 1
                            no_change = False
                        elif (((criminal_neighbor_count < 2) or (criminal_neighbor_count > 3)) and
                              isinstance(value, Criminal)):
                            value = Actor(value.x, value.y)
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

    def random_fill(self, criminal_probability=0.3, police_probability=0.2):
        global board
        global c
        c = 0
        for col in range(len(board)):
            for row in range(len(board)):
                #coords = get_coordinate_for_field(row, col)
                coords = self.get_random_actor_coordinate()
                random_probability = random.random()
                if random_probability < criminal_probability:
                    board[row][col] = Criminal(coords, 1)
                    c += 1
                elif random_probability < criminal_probability + police_probability:
                    board[row][col] = Police(coords, -1)
                else:
                    board[row][col] = Actor(coords)

        self.show_terminal_board()

    def start_sim_with_random(self):
        self.init_board()
        self.random_fill()
        self.start_simulation()

    def start_sim_with_data(self):
        self.start_simulation()

    def get_random_actor_coordinate(self):
        max_docs = self.transportations_collection.count_documents({})
        while True:
            random_street_index = random.randint(0, max_docs - 1)
            street = self.transportations_collection.find_one({"id": random_street_index})
            geometry = street["geometry"]
            if geometry["type"] == "LineString":
                break

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





@cross_origin()
@app.route('/board/random', methods=['GET', 'POST'])
def start_sim_with_random():
    global thread
    global map
    global is_running
    if is_running:
        map.terminate()
    thread = Thread(target=map.start_sim_with_random)
    thread.start()
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
    thread = Thread(target=map.start_sim_with_data)
    thread.start()
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
          Input('interval-component', 'n_intervals'))
def update_graph_live(n):
    global fig
    data_map = fig.data[0]
    data = map.get_actors()
    data = run_streets(data)
    data_df = data_to_df(data)

    data_map.lat = data_df.y.values
    data_map.lon = data_df.x.values
    #data.z = data_df.z
    fig['layout']['uirevision'] = "foo"
    children = generate_info_table()
    return fig, children

def run_streets(data):
    for actor in data:
        street = map.transportations_collection.find_one({"id": actor.coordinates.street_id})
        linestrings = street["geometry"]["coordinates"]
        linestring_index = linestrings.index([actor.coordinates.direction_checkmark_x, actor.coordinates.direction_checkmark_y])

        if actor.coordinates.direction_checkmark_x == actor.coordinates.x and actor.coordinates.direction_checkmark_y == actor.coordinates.y:
            if actor.coordinates.direction_positive and linestring_index < len(linestrings) - 1:
                next_linestring = linestrings[linestring_index+1]
            elif actor.coordinates.direction_positive and linestring_index == len(linestrings) - 1:
                next_linestring = linestrings[linestring_index-1]
                actor.coordinates.direction_positive = not actor.coordinates.direction_positive
            elif not actor.coordinates.direction_positive and linestring_index > 0:
                next_linestring = linestrings[linestring_index-1]
            elif not actor.coordinates.direction_positive and linestring_index == 0:
                next_linestring = linestrings[linestring_index + 1]
                actor.coordinates.direction_positive = not actor.coordinates.direction_positive
            actor.coordinates.previous_checkpoint_x = actor.coordinates.direction_checkmark_x
            actor.coordinates.previous_checkpoint_y = actor.coordinates.direction_checkmark_y
            actor.coordinates.direction_checkmark_x = next_linestring[0]
            actor.coordinates.direction_checkmark_y = next_linestring[1]

        coordinate_gap_x = abs(actor.coordinates.previous_checkpoint_x - actor.coordinates.direction_checkmark_x)
        coordinate_gap_y = abs(actor.coordinates.previous_checkpoint_y - actor.coordinates.direction_checkmark_y)

        if actor.coordinates.x < actor.coordinates.direction_checkmark_x:
            actor.coordinates.x += (coordinate_gap_x / 5)
            if actor.coordinates.x > actor.coordinates.direction_checkmark_x:
                actor.coordinates.x = actor.coordinates.direction_checkmark_x
        else:
            actor.coordinates.x -= (coordinate_gap_x / 5)
            if actor.coordinates.x < actor.coordinates.direction_checkmark_x:
                actor.coordinates.x = actor.coordinates.direction_checkmark_x

        if actor.coordinates.y < actor.coordinates.direction_checkmark_y:
            actor.coordinates.y += (coordinate_gap_y / 5)
            if actor.coordinates.y > actor.coordinates.direction_checkmark_y:
                actor.coordinates.y = actor.coordinates.direction_checkmark_y
        else:
            actor.coordinates.y -= (coordinate_gap_y / 5)
            if actor.coordinates.y < actor.coordinates.direction_checkmark_y:
                actor.coordinates.y = actor.coordinates.direction_checkmark_y

    return data


@callback(Output('submit-button', 'n_clicks'),
          Input('submit-button', 'n_clicks'),
          Input('criminal-slider', 'value'),
          Input('police-slider', 'value'))
def init_random_using_slider(button_value, criminal_value, police_value):
    global thread
    global map
    global is_running
    if button_value:
        if is_running:
            map.terminate()
        map.init_board()
        map.random_fill(criminal_value, police_value)
        thread = Thread(target=map.start_simulation)
        thread.start()
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
        item_vars = {"z": item.z} | vars(item.coordinates)
        data_attrs.append(item_vars)
    return pd.DataFrame(data_attrs)


if __name__ == "__main__":
    global map
    global is_running
    global fig
    os.system('color')
    is_running = False
    map = Map()
    map.init_board()
    map.random_fill()

    data = map.get_actors()
    data_df = data_to_df(data)
    # data_df = pd.DataFrame([vars(f) for f in data if f.z != 100])
    """
        fig = go.Figure(go.Densitymapbox(
            lat=data_df.x,
            lon=data_df.y,
            z=data_df.z,
            radius=15,
            # colorscale=[[0, 'rgb(0,0,255)'],[1, 'rgb(255,0,0)']]
        ))
    """
    fig = go.Figure(go.Scattermapbox(
        lat=data_df.y.values,
        lon=data_df.x.values,
        mode='markers',
        marker=go.scattermapbox.Marker(
            size=12,
            color="red"
        )
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
            },
        ],
        hovermode="closest"
    )
    fig['layout']['uirevision'] = "foo"
    fig.layout.hovermode = "closest"



    # fig.show()
    # fig_widget = go.FigureWidget(fig)

    dash_app = Dash(__name__, server=app)
    dash_app.layout = html.Div([
        html.Div(id='info'),
        html.Div(id='input-container', children=[
            html.Label("Criminals in %", htmlFor='criminal-slider'),
            dcc.Slider(
                0,
                50,
                step=None,
                value=6.5,
                id='criminal-slider'
            ),
            html.Label("Police in %", htmlFor='police-slider'),
            dcc.Slider(
                0,
                50,
                step=None,
                value=6.5,
                id='police-slider'
            ),
            html.Button(id='submit-button', children='Submit'),
        ]),
        dcc.Graph(figure=fig, id='graph', style={"height": "100vh"}),
        dcc.Interval(
            id='interval-component',
            interval=1 * 1000,  # in milliseconds
            n_intervals=0
        )
    ], style={"height": "100vh"})

    dash_app.run_server(debug=True, use_reloader=True)

    # Flask app
    # app.run(debug=True, host='0.0.0.0', port=5000)
