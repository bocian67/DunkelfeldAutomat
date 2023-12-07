"""
NavigationRoute:

    streets = [42, 455, 636]
    route = {0: [lat, lon], 1: [lat, lon] ...}



"""



class NavigationRoute:
    def __init__(self):
        self.streets = []
        self.route = {}
        self.step = 0

    def add_street(self, street):
        self.streets.append(street["id"])
        self.route[self.step] = street["coordinates"]
        self.step += 1