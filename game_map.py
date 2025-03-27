import numpy as np  # type: ignore
from typing import Iterable, Optional, Set, TYPE_CHECKING # Added imports
import tcod # Added import

import tile_types

# Forward declaration for type hinting if Entity is in another file
if TYPE_CHECKING:
    from entity import Entity
    from tcod.console import Console


class GameMap:
    """
    Represents the game map, including tiles, entities, visibility, and FOV calculation.
    """
    # Added entities parameter and type hints
    def __init__(
        self,
        width: int,
        height: int,
        entities: Iterable["Entity"] = () # Store entities present on the map
    ):
        self.width, self.height = width, height
        # Initialize with floor tiles; map generation will add walls, etc.
        self.tiles = np.full((width, height), fill_value=tile_types.floor, order="F")

        self.visible = np.full((width, height), fill_value=False, order="F") # Tiles the player can currently see
        self.explored = np.full((width, height), fill_value=False, order="F") # Tiles the player has seen before

        # Store entities. Using a set for efficient lookups and addition/removal.
        self.entities = set(entities)

        # --- New Elements: Pre-calculated properties from tiles ---
        # These arrays are derived from self.tiles for quick lookups.
        # Initialize them here, but they should be properly updated after
        # map generation sets the actual tile types.
        self.walkable = np.copy(self.tiles["walkable"])
        self.transparent = np.copy(self.tiles["transparent"])
        # Note: Assumes tile_types.floor/wall have 'walkable' and 'transparent' fields.
        # Example tile_types.py definition for a tile:
        # graphic_dt = np.dtype([("ch", np.int32), ("fg", "3B"), ("bg", "3B")])
        # tile_dt = np.dtype(
        #     [
        #         ("walkable", np.bool_),
        #         ("transparent", np.bool_),
        #         ("dark", graphic_dt),
        #         ("light", graphic_dt),
        #     ]
        # )
        # floor = new_tile(walkable=True, transparent=True, dark=..., light=...)
        # wall = new_tile(walkable=False, transparent=False, dark=..., light=...)


    # --- New Function: Update derived properties ---
    def update_tile_properties(self) -> None:
        """
        Updates the walkable and transparent arrays based on the current self.tiles.
        Call this after modifying self.tiles (e.g., after map generation or digging).
        """
        self.walkable = np.copy(self.tiles["walkable"])
        self.transparent = np.copy(self.tiles["transparent"])


    def in_bounds(self, x: int, y: int) -> bool:
        """Return True if x and y are inside of the bounds of this map."""
        return 0 <= x < self.width and 0 <= y < self.height

    # --- New Function: FOV Calculation ---
    def compute_fov(self, player_x: int, player_y: int, radius: int = 8) -> None:
         """
         Calculate the visible area from the player's position using tcod's FOV functions.
         Updates self.visible and marks newly visible tiles as explored.
         """
         # Use the pre-calculated transparent array for FOV computation
         self.visible = tcod.map.compute_fov(
             transparency=self.transparent, # Input: boolean array where True means transparent
             pov=(player_x, player_y),       # Point of View: (x, y) coordinates
             radius=radius,                  # How far the FOV extends
             light_walls=True,               # See walls adjacent to lit tiles?
             algorithm=tcod.FOV_SYMMETRIC_SHADOWCAST # Common FOV algorithm
         )
         # Whenever FOV is computed, add the newly visible tiles to the explored set
         self.explored |= self.visible

    # --- New Function: Entity Query ---
    def get_blocking_entity_at_location(
        self, location_x: int, location_y: int
    ) -> Optional["Entity"]:
        """
        Checks if there is an entity at the given location that blocks movement.
        Returns the entity if found, otherwise None.
        """
        for entity in self.entities:
            # Check if the entity blocks movement and is at the specified location
            if entity.blocks_movement and entity.x == location_x and entity.y == location_y:
                return entity
        return None # No blocking entity found at this location

    # --- New Function: Entity Query ---
    def get_entities_at_location(self, location_x: int, location_y: int) -> Set["Entity"]:
         """Returns all entities at a specific location."""
         return {
             entity for entity in self.entities
             if entity.x == location_x and entity.y == location_y
         }

    # --- Enhanced Function: Render Map and Entities ---
    def render(self, console: "Console") -> None:
        """
        Renders the map tiles based on visibility and exploration status.
        Then, renders visible entities on top of the map.
        """
        # Render the map tiles using np.select for efficiency
        console.tiles_rgb[0:self.width, 0:self.height] = np.select(
            condlist=[self.visible, self.explored], # Conditions: Is it visible? Is it explored?
            choicelist=[self.tiles["light"], self.tiles["dark"]], # Choices: Use light tiles, use dark tiles
            default=tile_types.SHROUD # Default: Use shroud tile if neither visible nor explored
        )

        # --- Feature Enhancement: Render Entities ---
        # Sort entities by render order so actors appear above items, corpses etc.
        # Assumes Entity has a 'render_order' attribute (e.g., an Enum)
        entities_sorted_for_rendering = sorted(
            self.entities, key=lambda e: e.render_order.value
        )

        # Iterate through sorted entities and render them if they are visible
        for entity in entities_sorted_for_rendering:
             # Only draw entities that are within the player's current FOV
             if self.visible[entity.x, entity.y]:
                 console.print(x=entity.x, y=entity.y, string=entity.char, fg=entity.color)
