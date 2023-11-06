# Introduction
On each tile, an actor may be present
- an actor can be criminal or police
- the amount of actors can be increased or decreased based on simulation rules

# Rules
- actors are placed randomly on board
  - the amount of actors is based on a ratio (f.e. 30% criminal, 50% police)
  - the maximum amount of police is static
- (fields without police will become criminal after 3 turns)
- if criminal is above a threshold, a police will be placed
  - one police will eliminate one criminal
  - if the police is on a tile, no criminal will be added
- if no criminal exists, the police will be removed
- (if criminal exists, the criminal amount will increase)
- if a cell has more than 3 criminal neighbors, it will also become criminal
- 