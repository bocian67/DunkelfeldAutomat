class Actor:
    def __init__(self, id, actor_coordinate):
        self.id = id
        self.coordinates = actor_coordinate
        self.z = 0
        self.color = "white"
        self.navigation_route = None

    def set_navigation_route(self, navigation_route, start_from_position):
        self.navigation_route = navigation_route
        self.navigation_route.step = 0

        if not start_from_position:
            destination_route = self.navigation_route.get_route()
            self.coordinates = ActorCoordinate(self.navigation_route.streets[self.navigation_route.step], True,
                                               destination_route[0], destination_route[1], destination_route[0],
                                               destination_route[1], destination_route[0], destination_route[1])
        else:
            self.navigation_route.route[str(0)] = [self.coordinates.x, self.coordinates.y]
            destination_route = self.navigation_route.get_route()
            self.coordinates = ActorCoordinate(self.navigation_route.streets[self.navigation_route.step], True,
                                               self.coordinates.x, self.coordinates.y, destination_route[0],
                                               destination_route[1], destination_route[0], destination_route[1])

    def set_navigation_step(self, navigation_step):
            self.navigation_route.step = navigation_step
            destination_route = self.navigation_route.get_route()
            self.coordinates = ActorCoordinate(
                self.navigation_route.streets[self.navigation_route.step],
                True,
                self.coordinates.x,
                self.coordinates.y,
                destination_route[0],
                destination_route[1],
                self.coordinates.x,
                self.coordinates.y
            )

    def can_touch_actor(self, destination_actor):
        distance = abs(self.coordinates.x - destination_actor.coordinates.x) + abs(self.coordinates.y - destination_actor.coordinates.y)
        if distance <= 0.00004:
            return True
        return False

    def is_actor_near(self, destination_actor):
        distance = abs(self.coordinates.x - destination_actor.coordinates.x) + abs(self.coordinates.y - destination_actor.coordinates.y)
        if distance <= 0.0004:
            return True
        return False


class Criminal(Actor):
    def __init__(self, id, actor_coordinate, z):
        super().__init__(id, actor_coordinate)
        self.z = z
        self.color = "white"
        self.robbed = None
        self.robbed_counter = None

    def increase_criminal(self):
        self.z += 1

    def decrease_criminal(self):
        if self.z <= 1:
            self.z = 0
        else:
            self.z -= 1

    def set_robbed_id(self, id):
        self.robbed = id
        self.color = "red"
        self.robbed_counter = 0

    def set_incognito(self):
        self.robbed = None
        self.color = "white"
        self.robbed_counter = None


class Police(Actor):
    def __init__(self, id, coordinates, z):
        super().__init__(id, coordinates)
        self.z = z
        self.color = "blue"
        self.suspect_id = None
        self.suspect_last_known_coordinate = None

    def set_suspect(self, suspect_id, suspect_last_known_coordintates):
        self.suspect_id = suspect_id
        self.suspect_last_known_coordinate = suspect_last_known_coordintates


class Civilian(Actor):
    def __init__(self, id, coordinates):
        super().__init__(id, coordinates)
        self.event_by_id = None

    def set_was_robbed_by(self, id):
        self.event_by_id = id



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
