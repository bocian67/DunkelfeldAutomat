class Actor:
    def __init__(self, actor_coordinate):
        self.coordinates = actor_coordinate
        self.z = 0
        self.color = "white"


class Criminal(Actor):
    def __init__(self, actor_coordinate, z):
        super().__init__(actor_coordinate)
        self.z = z
        self.color = "red"

    def increase_criminal(self):
        self.z += 1

    def decrease_criminal(self):
        if self.z <= 1:
            self.z = 0
        else:
            self.z -= 1


class Police(Actor):
    def __init__(self, coordinates, z):
        super().__init__(coordinates)
        self.z = z
        self.color = "blue"


class ActorCoordinate:
    def __init__(self, street_id, direction_positive, x, y, direction_checkmark_x, direction_checkmark_y, previous_checkmark_x, previous_checkmark_y):
        # id of the transportations feature
        self.street_id = street_id
        # if the LineString coordinates will be read forward or backward
        self.direction_positive = direction_positive
        self.x = x
        self.y = y
        self.direction_checkmark_x = direction_checkmark_x
        self.direction_checkmark_y = direction_checkmark_y
        self.previous_checkmark_x = previous_checkmark_x
        self.previous_checkmark_y = previous_checkmark_y
