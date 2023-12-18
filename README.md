# Introduction
On each tile, an actor may be present
- an actor can be criminal or police
- the amount of actors can be increased or decreased based on simulation rules

## Installation
### Requirements
- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- [MongoDB Database Tools](https://www.mongodb.com/docs/database-tools/installation/installation/)
- install python dependencies
```bash
python3 -m venv .venv

.venv\Scripts\activate.bat

pip install -r requirements.txt
```
- Start MongoDB in docker
```bash 
docker run --name DunkelfeldDB --env=MONGO_INITDB_ROOT_USERNAME=admin --env=MONGO_INITDB_ROOT_PASSWORD=admin -p 27017:27017 -d mongo
```
- Set up database in docker using dbdump (you have to replace the path to mongorestore.exe installed previously and the path to tiles\dbdump)
```bash
mongorestore.exe --uri mongodb://admin:admin@localhost:27017 tiles\dbdump
```