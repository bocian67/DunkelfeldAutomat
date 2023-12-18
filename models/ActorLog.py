from enum import Enum

from dash import Dash, dcc, html
class ActorLog:
    def __init__(self, actor_id, actor_color, action, location):
        self.actor_id = actor_id
        self.action = action
        self.location = location
        self.actor_color = actor_color

    def __str__(self):
        if self.action is ActorLogAction.NEW_PATH:
            return f"Actor {self.actor_id} {self.action.value} from {self.location}"
        elif self.action is ActorLogAction.NEXT_NAVIGATION_POINT:
            return f"Actor {self.actor_id} {self.action.value} on {self.location}"

    def log_to_div(self):
        return html.Div(style={"background": self.actor_color}, children=[
            html.P(str(self))
        ])


class ActorLogAction(Enum):
    NEW_PATH = "New Path"
    NEXT_NAVIGATION_POINT = "Next Navigation Point"
