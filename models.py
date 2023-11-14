class Actor:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.z = 0


class Criminal(Actor):
    def __init__(self, x, y, z):
        super().__init__(x, y)
        self.z = z

    def increase_criminal(self):
        self.z += 1

    def decrease_criminal(self):
        if self.z <= 1:
            self.z = 0
        else:
            self.z -= 1


class Police(Actor):
    def __init__(self, x, y, z):
        super().__init__(x, y)
        self.z = z
