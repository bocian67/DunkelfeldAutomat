from pymongo import MongoClient


def get_database():
    client = MongoClient("mongodb://admin:admin@localhost:27017")
    return client['geojson']


if __name__ == '__main__':
    dbname = get_database()
