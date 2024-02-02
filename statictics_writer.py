from datetime import datetime
from pathlib import Path
import csv


class StatisticsWriter():
    def __init__(self):
        self.name = datetime.now().strftime("%d-%m-%Y_%H-%M-%S") + ".csv"
        self.path = Path(self.name)

    def init_parameter(self, actor_count, criminal_percent, police_percent, penalty_months, general_speed, police_mobility, seed):
        with open(self.path, 'a') as outfile:
            writer = csv.writer(outfile)
            writer.writerow(["ActorCount", "CriminalPercent", "PolicePercent", "PenaltyMonth", "GeneralSpeed", "PoliceMobility", "Seed"])
            writer.writerow([actor_count, criminal_percent, police_percent, penalty_months, general_speed,
                             police_mobility, seed])
            writer.writerow(["PoliceCount", "CriminalCount", "CivilCount", "RobberyCount", "PrisonCount"])

    def write_csv(self, police_count, criminal_count, civil_count, robbery_count, prison_count):
        with open(self.path, 'a') as outfile:
            writer = csv.writer(outfile)
            writer.writerow([police_count, criminal_count, civil_count, robbery_count, prison_count])