import json
import sqlite3
import gzip
from io import BytesIO
import mapbox_vector_tile as mvt
import geopandas as gpd

# connect to tiles
MBTILES = "tiles/mittweida.mbtiles"
con = sqlite3.connect(MBTILES)
cursor = con.cursor()

# tile coordinates
zoom = 14

cursor.execute(
    """SELECT tile_column, tile_row FROM tiles
    WHERE zoom_level=:zoom;""",
    {"zoom": zoom},
)

data = cursor.fetchall()
tile_columns = [item[0] for item in data]
tile_rows = [item[1] for item in data]

for index, col in enumerate(tile_columns):
    row = tile_rows[index]

    cursor.execute(
        """SELECT tile_data FROM tiles 
        WHERE zoom_level=:zoom 
        AND tile_column=:column AND tile_row=:row;""",
        {"zoom": zoom, "column": col, "row": row},
    )
    data = cursor.fetchall()
    tile_data = data[0][0]
    raw_data = BytesIO(tile_data)

    with gzip.open(raw_data, "rb") as f:
        tile = f.read()
    decoded_data = mvt.decode(tile)

    layers = [{'name': key, **decoded_data[key]} for key in decoded_data]

    # this list will contain features ready to be stored in a geojson dict
    features = []

    # unpack features for each layer into the list
    for layer in layers:
        for feature in layer['features']:
            features.append({'layer': layer['name'],
                             'geometry': feature['geometry'],
                             'id': feature['id'],
                             'properties': {'layer': layer['name'],
                                               'id': feature['id'],
                                               **feature['properties']
                                               },
                             'type': 'Feature'})

    # write to a json file ready to be loaded by geopandas
    with open(f'mittweida_{index}.json', 'w') as file:
        data = json.dumps({'type': 'FeatureCollection', 'features': features})
        file.write(data)
    # read the saved geojson as a geodataframe
    feature_df = gpd.read_file(f'mittweida_{index}.json', driver='GeoJSON')
    print(feature_df)

    # TEST

