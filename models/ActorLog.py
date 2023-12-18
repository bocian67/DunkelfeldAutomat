from dash import Dash, dcc, html
class ActorLog:
    def __init__(self, actor_id, actor_color, action, location):
        self.actor_id = actor_id
        self.action = action
        self.location = location
        self.actor_color = actor_color

    def __str__(self):
        return f"Actor {self.actor_id} {self.action} on {self.location}"

    def log_to_div(self):
        return html.Div(style={"background": self.actor_color}, children=[
            html.P(str(self))
        ])