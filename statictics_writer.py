from datetime import datetime
from pathlib import Path
import csv

import pandas as pd


class StatisticsWriter():
    def __init__(self):
        self.name = datetime.now().strftime("%d-%m-%Y_%H-%M-%S") + ".csv"
        self.path = Path(self.name)
        self.data = []
        self.iteration = 0

    def init_parameter(self, actor_count, criminal_percent, police_percent, penalty_months, general_speed, police_mobility, seed):
        with open(self.path, 'a') as outfile:
            writer = csv.writer(outfile)
            writer.writerow(["ActorCount", "CriminalPercent", "PolicePercent", "PenaltyMonth", "GeneralSpeed", "PoliceMobility", "Seed"])
            writer.writerow([actor_count, criminal_percent, police_percent, penalty_months, general_speed,
                             police_mobility, seed])
            writer.writerow(["PoliceCount", "CriminalCount", "CivilCount", "RobberyCount", "PrisonCount"])

    def write_csv(self, police_count, criminal_count, civil_count, robbery_count, prison_count):
        self.data.append({"iteration": self.iteration, "y": police_count, "category": "PoliceCount", "dash": "solid"})
        self.data.append({"iteration": self.iteration, "y": criminal_count, "category": "CriminalCount", "dash": "solid"})
        self.data.append({"iteration": self.iteration, "y": civil_count, "category": "CivilCount", "dash": "solid"})
        self.data.append({"iteration": self.iteration, "y": robbery_count, "category": "RobberyCount", "dash": "dot"})
        self.data.append({"iteration": self.iteration, "y": prison_count, "category": "PrisonCount", "dash": "longdashdot"})

        with open(self.path, 'a') as outfile:
            writer = csv.writer(outfile)
            writer.writerow([str(police_count), str(criminal_count), str(civil_count), str(robbery_count), str(prison_count)])
        self.iteration += 1

    def data_to_df(self):
        return pd.DataFrame(self.data)