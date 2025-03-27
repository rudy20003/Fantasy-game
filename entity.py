from __future__ import annotations

import math # For distance calculations
from typing import Optional, Tuple, Type, TypeVar, TYPE_CHECKING
import enum # For RenderOrder

# --- Forward References for Type Hinting ---
# These prevent circular import errors if components/maps import Entity
if TYPE_CHECKING:
    from components.ai import BaseAI
    from components.consumable import Consumable
    from components.equippable import Equippable
    from components.equipment import Equipment
    from components.fighter import Fighter
    from components.inventory import Inventory
    from components.item import Item as ItemComponent # Rename component to avoid clash
    from components.level import Level
    from components.stairs import Stairs
    from game_map import GameMap

# Generic type for component lookups (optional advanced use)
T = TypeVar("T")

# --- Render Order Enum ---
class RenderOrder(enum.Enum):
    """Determines the drawing order for entities."""
    CORPSE = 0
    ITEM = 1
    ACTOR = 2 # Player and enemies


# --- Expanded Entity Class ---
class Entity:
    """
    A generic object representing players, enemies, items, structures, etc.
    Now acts primarily as a container for components that define its behavior and data.
    """

    # Allow parent to be GameMap (for top-level entities) or another Entity (items in inv)
    parent: Optional[GameMap | Inventory | Equipment]

    def __init__(
        self,
        # Core Identification & Position
        x: int = 0, # Default position to 0, set later via place() or spawn()
        y: int = 0,
        char: str = "?", # Default character
        color: Tuple[int, int, int] = (255, 255, 255), # Default white
        name: str = "<Unnamed>", # Name for identification
        *, # Make subsequent arguments keyword-only
        # Core Properties
        blocks_movement: bool = False, # Does this entity block movement?
        render_order: RenderOrder = RenderOrder.CORPSE, # Default render order
        # Optional Components - Passed on creation
        fighter: Optional[Fighter] = None,
        ai: Optional[BaseAI] = None,
        inventory: Optional[Inventory] = None,
        item: Optional[ItemComponent] = None, # Component defining item properties
        consumable: Optional[Consumable] = None, # If item is consumable
        equippable: Optional[Equippable] = None, # If item is equippable
        equipment: Optional[Equipment] = None, # Component managing equipped items (usually only on Actors)
        level: Optional[Level] = None, # For XP and leveling (usually only on Actors)
        stairs: Optional[Stairs] = None, # Component for stairs entities
        # Parent/Map reference (usually None initially, set via place/add_item)
        parent: Optional[GameMap | Inventory | Equipment] = None,
        gamemap: Optional[GameMap] = None, # Reference to the current map
    ):
        self.x = x
        self.y = y
        self.char = char
        self.color = color
        self.name = name
        self.blocks_movement = blocks_movement
        self.render_order = render_order
        self.parent = parent # Link to inventory/equipment if applicable
        self._gamemap = gamemap # Internal storage for gamemap reference

        # --- Component Assignment ---
        # Assign components passed in constructor and link them back to this entity
        self.fighter = fighter
        if self.fighter:
            self.fighter.owner = self

        self.ai = ai
        if self.ai:
            self.ai.owner = self

        self.inventory = inventory
        if self.inventory:
            self.inventory.owner = self

        self.item = item
        if self.item:
            self.item.owner = self

        self.consumable = consumable
        if self.consumable:
            self.consumable.owner = self
            # Often, Item component is implicitly required if Consumable exists
            if not self.item:
                 print(f"Warning: Entity '{self.name}' has Consumable but no Item component.")

        self.equippable = equippable
        if self.equippable:
            self.equippable.owner = self
            if not self.item:
                 print(f"Warning: Entity '{self.name}' has Equippable but no Item component.")

        self.equipment = equipment
        if self.equipment:
            self.equipment.owner = self

        self.level = level
        if self.level:
            self.level.owner = self

        self.stairs = stairs
        if self.stairs:
            self.stairs.owner = self

    # --- Properties for Convenience ---

    @property
    def is_alive(self) -> bool:
        """Returns True if this entity is considered 'alive' (usually actors with HP > 0)."""
        # Relies on the Fighter component
        return bool(self.fighter and self.fighter.hp > 0)

    @property
    def gamemap(self) -> GameMap | None:
        """Get the GameMap this entity is currently on."""
        return self._gamemap

    @gamemap.setter
    def gamemap(self, value: GameMap | None) -> None:
        """
        Set the GameMap for this entity.
        Note: Adding/removing from map's entity lists should be handled externally
        (e.g., by the Engine or map generation) when this is set.
        """
        self._gamemap = value

    # --- Core Methods ---

    def move(self, dx: int, dy: int) -> None:
        """Update the entity's position. Does not handle collision or bounds checks."""
        self.x += dx
        self.y += dy

    def place(self, x: int, y: int, gamemap: Optional[GameMap] = None) -> None:
        """
        Place this entity at a specific location on a given GameMap.
        Updates position and the internal gamemap reference.
        Optionally updates the gamemap reference if provided.
        """
        self.x = x
        self.y = y
        if gamemap:
            # If entity changes maps, old map might need cleanup externally
            if self._gamemap and self._gamemap is not gamemap:
                print(f"Warning: Entity '{self.name}' changed gamemap via place(). External cleanup might be needed.")
            self._gamemap = gamemap
            # Consider adding self to gamemap.entities here, if managing centrally

    def distance(self, x: int, y: int) -> float:
        """
        Calculate the distance between this entity and the given (x, y) coordinates.
        Uses the Pythagorean theorem.
        """
        return math.sqrt((self.x - x) ** 2 + (self.y - y) ** 2)

    # --- Component Access (Optional Generic Method) ---

    def get_component(self, component_type: Type[T]) -> Optional[T]:
        """
        Retrieve a component of a specific type from this entity, if it exists.
        Example: entity.get_component(Fighter)
        """
        # This requires components to have predictable attribute names
        # or a more sophisticated component storage mechanism (like a dictionary).
        # Simple implementation based on current attribute names:
        component_map = {
            Fighter: self.fighter,
            BaseAI: self.ai,
            Inventory: self.inventory,
            ItemComponent: self.item,
            Consumable: self.consumable,
            Equippable: self.equippable,
            Equipment: self.equipment,
            Level: self.level,
            Stairs: self.stairs,
            # Add other component types here
        }
        # Find the component in the map based on type
        for comp_cls, comp_instance in component_map.items():
             # Use issubclass to handle potential component inheritance
             if issubclass(component_type, comp_cls) and comp_instance:
                 return comp_instance # type: ignore - Known limitation of simple dict mapping

        return None # Component not found or not of the expected base type


# --- Convenience Subclasses ---

class Actor(Entity):
    """
    An entity subclass representing actors like the player and monsters.
    Typically blocks movement and has Fighter/AI/Inventory/Equipment/Level components.
    """
    def __init__(
        self,
        *,
        x: int = 0,
        y: int = 0,
        char: str = "?",
        color: Tuple[int, int, int] = (255, 255, 255),
        name: str = "<Unnamed Actor>",
        # Components required/expected for Actors
        ai_cls: Optional[Type[BaseAI]], # Pass AI *class* to instantiate
        fighter: Fighter, # Fighter component is usually mandatory
        inventory: Optional[Inventory] = None, # Optional inventory
        equipment: Optional[Equipment] = None, # Optional equipment management
        level: Optional[Level] = None, # Optional leveling
        # Default Actor properties
        blocks_movement: bool = True,
        render_order: RenderOrder = RenderOrder.ACTOR,
        parent: Optional[GameMap | Inventory | Equipment] = None,
        gamemap: Optional[GameMap] = None,
    ):
        super().__init__(
            x=x, y=y, char=char, color=color, name=name,
            blocks_movement=blocks_movement, render_order=render_order,
            fighter=fighter,
            # Instantiate AI component using the provided class
            ai=ai_cls(self) if ai_cls else None,
            inventory=inventory,
            equipment=equipment if equipment else Equipment(), # Default to having equipment manager
            level=level if level else Level(), # Default to having level tracking
            parent=parent,
            gamemap=gamemap,
        )
        # Ensure default equipment component is linked if created here
        if not equipment and self.equipment:
             self.equipment.owner = self
        # Ensure default level component is linked if created here
        if not level and self.level:
             self.level.owner = self


class Item(Entity):
    """
    An entity subclass representing items.
    Typically does not block movement and has Item/Consumable/Equippable components.
    """
    def __init__(
        self,
        *,
        x: int = 0,
        y: int = 0,
        char: str = "?",
        color: Tuple[int, int, int] = (255, 255, 255),
        name: str = "<Unnamed Item>",
        # Components required/expected for Items
        item: Optional[ItemComponent] = None, # Usually needed to define it *as* an item
        consumable: Optional[Consumable] = None,
        equippable: Optional[Equippable] = None,
        # Default Item properties
        blocks_movement: bool = False, # Items usually don't block
        render_order: RenderOrder = RenderOrder.ITEM,
        parent: Optional[GameMap | Inventory | Equipment] = None,
        gamemap: Optional[GameMap] = None,
    ):
        # Assign item component if not provided explicitly
        item_comp = item if item else ItemComponent()

        super().__init__(
            x=x, y=y, char=char, color=color, name=name,
            blocks_movement=blocks_movement, render_order=render_order,
            item=item_comp, # Assign item component
            consumable=consumable,
            equippable=equippable,
            parent=parent,
            gamemap=gamemap,
        )
        # Link default item component if created here
        if not item and self.item:
             self.item.owner = self
