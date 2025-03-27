from __future__ import annotations

import random # For potential randomness in actions
from typing import TYPE_CHECKING, Optional, Tuple

# Assuming component imports exist or are defined elsewhere
# from components.ai import BaseAI
# from components.consumable import Consumable
# from components.equippable import Equippable
# from components.equipment import Equipment
# from components.fighter import Fighter
# from components.inventory import Inventory
# from components.level import Level
import color # Assuming a color definition module


if TYPE_CHECKING:
    from engine import Engine
    from entity import Entity, Actor, Item # Assuming Actor and Item subclasses exist


# Base Action Class (Unchanged)
class Action:
    """Base class for all actions."""

    # Added reference to the entity performing the action for convenience in subclasses
    def __init__(self, entity: Actor):
        super().__init__()
        self.entity = entity

    @property
    def engine(self) -> Engine:
        """Return the engine associated with this action's entity."""
        # Assumes Entity has a reference to its GameMap, which has a reference to the Engine
        # Or, pass Engine during Action creation if preferred
        return self.entity.gamemap.engine

    def perform(self) -> None:
        """
        Perform this action.

        This method must be overridden by Action subclasses.
        It should interact with the engine, game map, and entities as needed.
        Returns None, but state changes occur within the engine/entities.
        """
        raise NotImplementedError()


# Simple Actions ###############################################################

class WaitAction(Action):
    """Action for doing nothing and passing the turn."""
    def perform(self) -> None:
        # No action needed, turn is simply consumed.
        # Engine might add energy cost here if using that system.
        pass # Doesn't interact with engine/entity state directly


class EscapeAction(Action):
    """Action for exiting the game."""
    def perform(self) -> None:
        # Note: Directly raising SystemExit can be abrupt.
        # A cleaner approach might involve setting a flag in the engine
        # or changing the game state to 'EXITING'.
        raise SystemExit()


# Actions with Direction ######################################################

class ActionWithDirection(Action):
    """Base class for actions that involve a direction (dx, dy)."""
    def __init__(self, entity: Actor, dx: int, dy: int):
        super().__init__(entity)
        self.dx = dx
        self.dy = dy

    @property
    def dest_xy(self) -> Tuple[int, int]:
        """Returns the destination coordinates for this action."""
        return self.entity.x + self.dx, self.entity.y + self.dy

    @property
    def blocking_entity(self) -> Optional[Actor]:
        """Returns the blocking actor at the destination, if any."""
        return self.engine.game_map.get_blocking_entity_at_location(*self.dest_xy)

    def perform(self) -> None:
        raise NotImplementedError()


class MeleeAction(ActionWithDirection):
    """Action for performing a melee attack against a target in a direction."""
    def perform(self) -> None:
        target = self.blocking_entity # Find target at destination

        # Check if there is a valid target with a Fighter component
        if not target or not target.fighter:
            self.engine.message_log.add_message("Nothing to attack.", color.impossible)
            return # No valid target

        # --- Combat Logic ---
        # Assumes Fighter component has methods for handling attacks/damage
        attack_desc = f"{self.entity.name.capitalize()} attacks {target.name}"
        if self.entity is self.engine.player:
            attack_color = color.player_atk
        else:
            attack_color = color.enemy_atk

        # Calculate damage (this logic might live in the Fighter component)
        damage = self.entity.fighter.power - target.fighter.defense

        if damage > 0:
            self.engine.message_log.add_message(
                f"{attack_desc} for {damage} hit points.", attack_color
            )
            # Apply damage via target's fighter component
            target.fighter.hp -= damage # target.fighter.take_damage(damage) might be better
        else:
            self.engine.message_log.add_message(
                f"{attack_desc} but does no damage.", attack_color
            )


class MovementAction(ActionWithDirection):
    """Action for moving an entity in a direction."""
    def perform(self) -> None:
        dest_x, dest_y = self.dest_xy

        # --- Check Validity ---
        if not self.engine.game_map.in_bounds(dest_x, dest_y):
            self.engine.message_log.add_message("That way is blocked.", color.impossible)
            return  # Destination out of bounds.
        if not self.engine.game_map.walkable[dest_x, dest_y]:
            self.engine.message_log.add_message("That way is blocked.", color.impossible)
            return  # Destination blocked by tile.
        if self.engine.game_map.get_blocking_entity_at_location(dest_x, dest_y):
            self.engine.message_log.add_message("That way is blocked.", color.impossible)
            return  # Destination blocked by an entity.

        # --- Perform Move ---
        self.entity.move(self.dx, self.dy)


class BumpAction(ActionWithDirection):
    """
    Handles movement or melee attack based on what's in the target direction.
    This is often the default action bound to movement keys.
    """
    def perform(self) -> None:
        target_actor = self.blocking_entity # Check for blocking actor first

        if target_actor:
            # If there's an actor, perform a melee attack
            # Delegate to MeleeAction by returning it or calling its perform method
            return MeleeAction(self.entity, self.dx, self.dy).perform()
        else:
            # If no actor, attempt movement
            # Delegate to MovementAction or call its perform method
            return MovementAction(self.entity, self.dx, self.dy).perform()


# Item Actions ###############################################################

class PickupAction(Action):
    """Action for picking up an item at the entity's location."""
    def perform(self) -> None:
        actor_location_x = self.entity.x
        actor_location_y = self.entity.y

        # Check inventory capacity (if implemented)
        # if self.entity.inventory and len(self.entity.inventory.items) >= self.entity.inventory.capacity:
        #     self.engine.message_log.add_message("Your inventory is full.", color.impossible)
        #     return

        # Find items at the actor's location
        items_at_location = self.engine.game_map.get_items_at_location(
            actor_location_x, actor_location_y
        )

        if not items_at_location:
            self.engine.message_log.add_message("There is nothing here to pick up.", color.impossible)
            return

        # Pick up the first item found (or implement selection)
        # For simplicity, let's pick up the "top" item.
        item_to_pickup = items_at_location.pop() # Get one item

        # Add to inventory (Assumes Inventory component)
        if self.entity.inventory:
             # Add item to actor's inventory
            self.entity.inventory.items.append(item_to_pickup)
             # Remove item from the game map's entity list
            self.engine.game_map.entities.remove(item_to_pickup)
            # Update the item's parent reference if needed
            item_to_pickup.parent = self.entity.inventory

            self.engine.message_log.add_message(f"You picked up the {item_to_pickup.name}!", color.item_pickup)
        else:
            # Actor has no inventory component
             self.engine.message_log.add_message(f"{self.entity.name.capitalize()} cannot pick things up.", color.impossible)


class ActionWithItem(Action):
    """Base class for actions that involve a specific item."""
    def __init__(self, entity: Actor, item: Item):
        super().__init__(entity)
        self.item = item

    def perform(self) -> None:
        raise NotImplementedError()


class UseItemAction(ActionWithItem):
    """Action for using a consumable item."""
    def perform(self) -> None:
        if not self.item.consumable:
            self.engine.message_log.add_message(f"You can't use the {self.item.name}.", color.impossible)
            return

        # Activate the consumable's effect
        # The consumable's activate method handles logic and messages
        # It might return False if activation failed, or True otherwise
        action_result = self.item.consumable.activate(self) # Pass self (the action) for context

        # Consume the item if activation was successful (handled by consumable.activate potentially)
        # if action_result and self.item.consumable.consume_on_use:
        #     self.entity.inventory.items.remove(self.item)


class DropItemAction(ActionWithItem):
    """Action for dropping an item from inventory."""
    def perform(self) -> None:
        if self.entity.equipment and self.entity.equipment.item_is_equipped(self.item):
            self.entity.equipment.toggle_equip(self.item, add_message=False) # Unequip before dropping

        self.entity.inventory.drop(self.item) # Assumes Inventory component has drop method

        self.engine.message_log.add_message(f"You dropped the {self.item.name}.", color.item_drop)


class EquipAction(ActionWithItem):
    """Action for equipping or unequipping an item."""
    def __init__(self, entity: Actor, item: Item):
        super().__init__(entity, item)

    def perform(self) -> None:
        # Check if entity has Equipment component and item has Equippable component
        if not self.entity.equipment:
             self.engine.message_log.add_message(f"{self.entity.name.capitalize()} cannot equip items.", color.impossible)
             return
        if not self.item.equippable:
            self.engine.message_log.add_message(f"The {self.item.name} cannot be equipped.", color.impossible)
            return

        # Delegate equipping logic to the Equipment component
        self.entity.equipment.toggle_equip(self.item)


# Environment Actions #########################################################

class TakeStairsAction(Action):
    """Action for using stairs to change dungeon levels."""
    def perform(self) -> None:
        # Check if entity is standing on stairs
        # This requires stairs to be identifiable, e.g., via a specific tile type
        # or a dedicated "Stairs" entity/component.
        # Example assuming stairs are special tiles:
        if (self.entity.x, self.entity.y) == self.engine.game_map.stairs_location: # Assumes map knows stair location
             # Trigger engine logic to change floor
             self.engine.change_floor()
             self.engine.message_log.add_message(
                "You descend deeper into the dungeon...", color.descend
             )
        else:
            self.engine.message_log.add_message(
                "There are no stairs here.", color.impossible
            )


# Targeting Actions (More Advanced) ##########################################
# These often involve changing game state and input handlers

class ActionWithPosition(Action):
    """Base class for actions targeting a specific map coordinate."""
    def __init__(self, entity: Actor, target_xy: Tuple[int, int]):
        super().__init__(entity)
        self.target_xy = target_xy

    @property
    def target_actor(self) -> Optional[Actor]:
        """Returns the actor at the target position, if any."""
        return self.engine.game_map.get_actor_at_location(*self.target_xy) # Assumes this method exists

    def perform(self) -> None:
        raise NotImplementedError()


class AreaRangedAttackAction(ActionWithPosition):
    """Action for attacking an area around a target coordinate."""
    def __init__(self, entity: Actor, target_xy: Tuple[int, int], radius: int, damage: int):
        super().__init__(entity, target_xy)
        self.radius = radius
        self.damage = damage

    def perform(self) -> None:
        target_x, target_y = self.target_xy

        # Validate target position (optional, maybe handled by input handler)
        if not self.engine.game_map.in_bounds(target_x, target_y):
             self.engine.message_log.add_message("Target is out of bounds.", color.impossible)
             return
        # Check if target is in FOV (usually handled by input handler)
        if not self.engine.game_map.visible[target_x, target_y]:
             self.engine.message_log.add_message("You cannot target an area you cannot see.", color.impossible)
             return

        self.engine.message_log.add_message(
            f"A blast explodes, engulfing the area around ({target_x},{target_y})!", color.needs_targeting # Example color
        )

        # Find actors within the radius
        actors_hit = []
        for actor in self.engine.game_map.actors: # Assumes game_map has an 'actors' property/method
            if actor.distance(*self.target_xy) <= self.radius and actor.fighter:
                actors_hit.append(actor)

        # Apply damage to hit actors
        for actor in actors_hit:
            self.engine.message_log.add_message(
                f"The {actor.name} is hit for {self.damage} damage!", color.enemy_atk # Example
            )
            actor.fighter.hp -= self.damage # Use take_damage method if available

        # Consume resources (e.g., mana, scroll) if applicable - often handled by the item/spell itself


class SingleRangedAttackAction(ActionWithPosition):
    """Action for attacking a single target at a specific coordinate."""
    def __init__(self, entity: Actor, target_xy: Tuple[int, int], damage: int):
        super().__init__(entity, target_xy)
        self.damage = damage

    def perform(self) -> None:
        target = self.target_actor

        if not target or not target.fighter:
            self.engine.message_log.add_message("You fire, but hit nothing.", color.impossible)
            return

        # Validate target position/visibility (usually handled by input handler)
        if not self.engine.game_map.visible[self.target_xy]:
             self.engine.message_log.add_message("You cannot target something you cannot see.", color.impossible)
             return

        attack_desc = f"{self.entity.name.capitalize()} fires at {target.name}"
        attack_color = color.player_atk if self.entity is self.engine.player else color.enemy_atk

        # Simple damage application
        effective_damage = self.damage - target.fighter.defense # Consider target defense
        if effective_damage > 0:
             self.engine.message_log.add_message(
                f"{attack_desc} hitting for {effective_damage} points.", attack_color
            )
             target.fighter.hp -= effective_damage
        else:
             self.engine.message_log.add_message(
                f"{attack_desc} but it has no effect.", attack_color
            )
        # Consume resources if applicable
