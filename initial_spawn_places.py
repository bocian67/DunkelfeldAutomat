class InitialSpawnPlaces():
    #possible_starting_locations = ["ALL", "MARKT", "TECH", "SCHWAN"]
    possible_starting_locations = {
        "ALL": "Random",
        "MARKT": "Marktplatz",
        "TECH": "Technikumsplatz",
        "SCHWAN": "Schwanenteich"
    }


    @staticmethod
    def get_street_ids_for_location(location):
        if location == "MARKT":
            return InitialSpawnPlaces.get_markt_street_ids()
        elif location == "TECH":
            return InitialSpawnPlaces.get_technikumsplatz_street_ids()
        elif location == "SCHWAN":
            return InitialSpawnPlaces.get_schwanenteich_street_ids()
        else:
            return None

    @staticmethod
    def get_markt_street_ids():
        return [81, 100, 141, 184, 223, 268]

    @staticmethod
    def get_technikumsplatz_street_ids():
        return [152, 153, 177, 197, 209, 287, 288, 289, 290, 307]

    @staticmethod
    def get_schwanenteich_street_ids():
        return [169, 308, 305, 285, 297]