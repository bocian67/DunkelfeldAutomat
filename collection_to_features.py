import geopandas as gpd
import json

classes = ["transportation", "transportation_name", "housenumber"]


def main():
    with open("tiles/mittweida.geojson", encoding="utf-8") as input:
        collection = json.load(input)["features"]

    tileCollection = []
    for i in collection:
        tileCollection.append(i["features"])

    features = [[] for i in classes]

    for c_index, c in enumerate(classes):
        for tileFeatures in tileCollection:
            for tile in tileFeatures:
                if tile["properties"]["layer"] == c:
                    for final in tile["features"]:
                        features[c_index].append(final)

        geojson = {
            "type": "FeatureCollection",
            "features": features[c_index]
        }
        with open(f"tiles/mittweida.{c}.geojson", "w", encoding="utf-8") as output:
            json.dump(geojson, output)


if __name__ == "__main__":
    main()