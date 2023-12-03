import json
import geopandas as gpd
from database import get_database
from geojson_utils import linestrings_intersect


def write_to_db():
    db = get_database()
    collection = db["transportations"]
    with open("tiles/mittweida.transportation.geojson", encoding="utf-8") as f:
        transportations = json.load(f)
    # transportations = gpd.read_file("tiles/mittweida.transportation.geojson")

    for index, feature in enumerate(transportations["features"]):
        feature["id"] = index + 1
        collection.insert_one(feature)


def find_intersections():
    db = get_database()
    transportation_collection = db["transportations"]
    intersection_collection = db["intersections"]
    max_docs = transportation_collection.count_documents({})
    for source_index in range(1, max_docs+1):
        print(f"{source_index}/{max_docs}")
        source_transportation = transportation_collection.find_one({"id": source_index})
        source_geometry = source_transportation["geometry"]
        intersections = []
        for target_index in range(1, max_docs+1):
            if source_index == target_index:
                continue
            target_transportation = transportation_collection.find_one({"id": target_index})
            target_geometry = target_transportation["geometry"]
            if source_geometry["type"] != "LineString" or target_geometry["type"] != "LineString":
                continue
            results = linestrings_intersect(source_geometry, target_geometry)
            for result in results:
                intersections.append({"id": target_index, "coordinates": result["coordinates"]})
        intersection_collection.insert_one({"id": source_index, "intersections": intersections})


if __name__ == "__main__":
    #write_to_db()
    find_intersections()