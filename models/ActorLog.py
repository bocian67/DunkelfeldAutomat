from enum import Enum

from dash import Dash, dcc, html
class ActorLog:
    def __init__(self, actor_id, actor_color, action, location):
        self.actor_id = actor_id
        self.action = action
        self.location = location
        self.actor_color = actor_color

    def __str__(self):
        if self.action is ActorLogAction.SEND_TO_PRISON:
            return f"Actor {self.actor_id} {self.action.value} by Police {self.location}"
        else:
            return f"Actor {self.actor_id} {self.action.value} on {self.location}"

    def log_to_div(self):
        if self.action in [ActorLogAction.NEW_PATH, ActorLogAction.NEXT_NAVIGATION_POINT]:
            return
        return html.Div(style={"background": self.actor_color}, children=[
            html.P(str(self))
        ])


class ActorEventLog(ActorLog):
    def __init__(self, actor_id, action, location, other_actor_id):
        super().__init__(actor_id, None, action, location)
        self.other_actor_id = other_actor_id

    def __str__(self):
        return f"Actor {self.actor_id} {self.action.value} Actor {self.other_actor_id} on {self.location}"

    def log_to_div(self):
        return html.Div(style={"background": "yellow"}, children=[
            html.P(str(self))
        ])

class ActorLogAction(Enum):
    NEW_PATH = "uses new path"
    NEXT_NAVIGATION_POINT = "sets next navigation point"
    ROBBING = "robbed"
    GOES_LAST_SUSPECT_PLACE = "goes to suspects last location point"
    FLEES = "flees to"
    SEND_TO_PRISON = "was send to prison"
