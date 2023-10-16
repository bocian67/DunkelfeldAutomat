# -*- coding: utf-8 -*-
import copy
import os
import random
import sys
from os import system, name
from threading import Thread
from time import sleep

import pandas as pd
import plotly.express as px
from flask import Flask, request
from flask_cors import CORS, cross_origin
from termcolor import colored
import plotly.graph_objects as go
from random import randrange
from dash import Dash, dcc, html, Output, Input, callback

mapbox_token = "pk.eyJ1IjoiYm9jaWFuNjciLCJhIjoiY2xuazV3YjB1MGsxNzJqczNjMjRnaXlqYiJ9.C2I3bmAseZVgWraJbHy3zA"

app = Flask(__name__)
CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'
# Configure the count of pixels:
PIXEL_COUNT = 144

color = (0, 0, 255)  # Blau

bounds_mittweida = {"lat_min": 50.979491, "lat_max":  50.995568, "lon_min": 12.951120, "lon_max": 12.991011}

global thread
global led
global fig


class Actor():
    def __init__(self, x, y, is_criminal):
        self.x = x
        self.y = y
        self.is_criminal = is_criminal
        self.z = 1 if is_criminal else 0


class LED:
    global board
    global c
    global iteration
    global is_running

    def get_actors(self):
        actors = []
        for row in board:
            actors.extend(row)
        return actors

    def terminate(self):
        global is_running
        is_running = False
        sleep(1)

    def main(self):
        self.init_board()
        self.show_board()
        self.init_user_choice()
        #self.start_simulation()

    def init_board(self):
        global board
        global iteration
        iteration = 0
        board = []
        count = 12
        for column_index in range(0, count):
            column = []
            for row_index in range(0, count):
                coords = get_coordinate_for_field(row_index, column_index)
                column.append(Actor(coords[0], coords[1], False))
            board.append(column)

    def show_board(self):
        row_nr = 0
        for r in board:
            col_nr = 0
            for c in r:
                col = (0, 0, 0)
                if board[row_nr][col_nr].is_criminal:
                    col = self.wheel(((256 // PIXEL_COUNT + ((iteration * 10) % 256))) % 256)
                else:
                    col = (0, 0, 0)
                pos = 0
                if row_nr % 2 == 0:
                    pos = (row_nr * 12) + col_nr
                else:
                    pos = (row_nr * 12) + 11 - col_nr
                col_nr += 1
            row_nr += 1

    def show_terminal_board(self):
        cls()
        row_nr = 0
        for r in board:
            col_nr = 0
            line = colored("|", 'black')
            for c in r:
                item_color = 'red' if board[row_nr][col_nr].is_criminal else 'green'
                line = line + colored("x" if board[row_nr][col_nr].is_criminal else "o", item_color) + colored("|", 'black')
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
                print("Iterationen: " + str(iteration))
                self.show_board()
                self.show_terminal_board()
                for col in range(len(board)):
                    for row in range(len(board)):
                        value = board[row][col]
                        count = self.count_neighbours(row, col)
                        if (count == 3) and (not value.is_criminal):
                            value.is_criminal = True
                            value.z = 1
                            new_board[row][col] = value
                            c += 1
                            no_change = False
                        elif ((count < 2) or (count > 3)) & value.is_criminal:
                            value.is_criminal = False
                            value.z = 0
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

    def count_neighbours(self, row, col):
        n = 0
        for i in range(-1, 2):
            for j in range(-1, 2):
                if (i != 0) or (j != 0):
                    r = row + i
                    c = col + j
                    if (r >= 0) & (r < len(board)) & (c >= 0) & (c < len(board)):
                        n += 1 if board[r][c].is_criminal else 0
        return n

    def wheel(self, pos):
        if pos < 85:
            return (pos * 3, 255 - pos * 3, 0)
        elif pos < 170:
            pos -= 85
            return (255 - pos * 3, 0, pos * 3)
        else:
            pos -= 170
            return (0, pos * 3, 255 - pos * 3)

    def random_fill(self, probability=0.2):
        global board
        global c
        c = 0
        for col in range(len(board)):
            for row in range(len(board)):
                coords = get_coordinate_for_field(row, col)
                if random.random() < probability:
                    board[row][col] = Actor(coords[0], coords[1], True)
                    c += 1
                else:
                    board[row][col] = Actor(coords[0], coords[1], False)

        self.show_terminal_board()

    def start_sim_with_random(self):
        self.init_board()
        self.random_fill()
        self.start_simulation()

    def start_sim_with_data(self):
        self.start_simulation()


@cross_origin()
@app.route('/board/random', methods=['GET', 'POST'])
def start_sim_with_random():
    global thread
    global led
    global is_running
    if is_running:
        led.terminate()
    thread = Thread(target=led.start_sim_with_random)
    thread.start()
    return 'Done!'


@cross_origin()
@app.route('/board/terminate', methods=['GET', 'POST'])
def terminate():
    global thread
    global led
    led.terminate()
    return 'Terminated!'


@cross_origin()
@app.route('/board/new', methods=['POST'])
def get_data_from_ui():
    global led
    global thread
    global is_running
    global board
    data = request.get_json()
    if is_running:
        led.terminate()
    board = data
    count_living(data)
    thread = Thread(target=led.start_sim_with_data)
    thread.start()
    return "Got Data"


def count_living(data):
    global c
    c = 0
    for row in range(len(data)):
        for col in range(len(data)):
            if data[col][row].is_criminal:
                c += 1


def cls():
    os.system('cls' if os.name == 'nt' else 'clear')


def get_coordinate_for_field(row, column) -> (float, float):
    x_step = (bounds_mittweida["lat_max"] - bounds_mittweida["lat_min"]) / 12
    y_step = (bounds_mittweida["lon_max"] - bounds_mittweida["lon_min"]) / 12
    x = bounds_mittweida["lat_min"] + row * x_step
    y = bounds_mittweida["lon_min"] + column * y_step
    return x, y

@callback(Output('graph', 'figure'),
              Input('interval-component', 'n_intervals'))
def update_graph_live(n):
    global fig
    data = led.get_actors()
    data_df = pd.DataFrame([vars(f) for f in data])
    data = fig.data[0]
    data.lat = data_df.x
    data.lon = data_df.y
    data.z = data_df.z
    fig['layout']['uirevision'] = "foo"
    return fig


if __name__ == "__main__":
    global led
    global is_running
    global fig
    os.system('color')
    is_running = False
    led = LED()
    led.init_board()
    led.random_fill()
    led.show_board()

    data = led.get_actors()
    data_df = pd.DataFrame([vars(f) for f in data])

    fig = go.Figure(go.Densitymapbox(
        lat=data_df.x,
        lon=data_df.y,
        z=data_df.z
    ))

    """
        fig = go.Figure(go.Scattermapbox(
            lat=data_df.x,
            lon=data_df.y,
            mode='markers',
            marker=go.scattermapbox.Marker(
                size=14,
            )
        ))
    """
    fig.update_layout(
        hovermode='closest',
        mapbox=dict(
            accesstoken=mapbox_token,
            bearing=0,
            center=go.layout.mapbox.Center(
                lat=50.9872722,
                lon=12.9737849
            ),
            pitch=0,
            zoom=16
        )
    )
    fig['layout']['uirevision'] = "foo"

    #fig.show()
    #fig_widget = go.FigureWidget(fig)

    dash_app = Dash(__name__, server=app)
    dash_app.layout = html.Div([
        dcc.Graph(figure=fig, id='graph', style={"height":"100vh"}),
        dcc.Interval(
            id='interval-component',
            interval=1 * 500,  # in milliseconds
            n_intervals=0
        )
    ], style={"height":"100vh"})

    dash_app.run_server(debug=True, use_reloader=True)

    # Flask app
    #app.run(debug=True, host='0.0.0.0', port=5000)
