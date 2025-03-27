from __future__ import annotations

import pickle  # For saving/loading
import lzma  # For compressing save files
import os  # For checking save file existence
from typing import TYPE_CHECKING, Any, Iterable, List, Optional, Tuple

from tcod.context import Context
from tcod.console import Console
# FOV compute now assumed to be handled by GameMap
# from tcod.map import compute_fov

# Assuming these modules/classes exist and are structured appropriately
import color
import components.ai
import components.fighter
import exceptions # e.g., exceptions.ImpossibleAction
from entity import Actor, Entity # Assuming Actor subclass exists
from game_map import GameMap
from game_states import GameState, MainMenuState # Example states
from input_handlers import BaseEventHandler, MainGameEventHandler, GameOverEventHandler # Specific handlers
from message_log import MessageLog
import render_functions # Module handling all rendering logic

if TYPE_CHECKING:
    from actions import Action


# --- Constants ---
FOV_RADIUS = 8
SAVE_FILE = "savegame.sav" # Consider platform-specific paths later


class Engine:
    """
    The main game engine, responsible for managing game state, turns,
    rendering, event handling, and core game logic.
    """
    game_map: GameMap
    event_handler: BaseEventHandler # Can now be different types of handlers
    player: Actor # Player is specifically an Actor
    message_log: MessageLog
    game_state: GameState # Manages the overall state (MainMenu, Gameplay, GameOver etc)
    mouse_location: Tuple[int, int]
    # entities: Set[Entity] # Now likely managed primarily by GameMap

    def __init__(self, player: Actor):
        # Core components initialized empty or with defaults
        self.message_log = MessageLog()
        self.mouse_location = (0, 0)
        self.player = player
        # Game state management - start typically in Main Menu or setup phase
        self.game_state = MainMenuState(self) # Or set later after setup
        self.event_handler = self.game_state.event_handler # Handler derived from state
        # GameMap and FOV are set up during new_game() or load_game()
        # self.game_map = GameMap(...) # Set in new_game/load_game
        # self.update_fov() # Called in new_game/load_game

    # --- Game Initialization / State Changes ---

    def new_game(self) -> None:
        """Start a new game."""
        # Reset relevant parts
        self.message_log.clear() # Clear log for new game

        # Setup player (might already be done externally)
        # Ensure player has necessary components if not already added

        # Generate the first floor
        # Assumes generate_dungeon returns a GameMap instance
        # and potentially places the player and other entities.
        from procgen import generate_dungeon # Local import ok here
        self.current_floor = 1 # Add floor tracking
        self.game_map = generate_dungeon(
            # Pass parameters from constants or config
            max_rooms=30, room_min_size=6, room_max_size=10,
            map_width=80, map_height=43, # Example sizes
            engine=self, # Pass engine for entity placement, linking map back
            current_floor=self.current_floor
        )
        self.game_map.engine = self # Link map back to engine

        # Update state and handler
        self.game_state = GameState(self) # Switch to main gameplay state
        self.event_handler = self.game_state.event_handler

        # Add welcome message
        self.message_log.add_message(
            "Hello and welcome, adventurer, to yet another dungeon!", color.welcome_text
        )

        # Initial FOV calculation
        self.update_fov()

    def change_floor(self, going_down: bool = True) -> None:
        """Generate a new map for the next floor."""
        if going_down:
            self.current_floor += 1
        else:
            # Logic for going up if implemented
             self.current_floor = max(1, self.current_floor - 1)
             # Potentially load previous floor state if kept in memory/disk

        # Generate new dungeon floor
        from procgen import generate_dungeon
        self.game_map = generate_dungeon(
            # ... parameters ...
            engine=self,
            current_floor=self.current_floor
        )
        self.game_map.engine = self

        # Clear entities' old pathfinding data if using pathfinding
        for entity in self.game_map.actors:
            if entity.ai:
                entity.ai.path = None # Reset path on floor change

        # Add floor change message
        direction = "descend" if going_down else "ascend"
        self.message_log.add_message(f"You {direction}...", color.descend) # Example color

        # Update FOV on the new map
        self.update_fov()


    def check_player_death(self) -> None:
        """Check if the player has died and trigger game over if so."""
        if self.player.fighter and self.player.fighter.is_dead:
            self.message_log.add_message("You died!", color.player_die)
            # Optionally save high score, etc.
            # self.save_game(filename="game_over_autosave.sav") # Example autosave
            self.game_state.on_player_death() # Delegate state change logic
            self.event_handler = self.game_state.event_handler # Update handler

    # --- Event Handling and Turn Management ---

    def handle_events(self, events: Iterable[Any]) -> None:
        """Handle a sequence of events, process actions, and manage turns."""
        # Process non-blocking events first (like mouse motion)
        for event in events:
            # Update mouse location for tooltips/targeting
            if isinstance(event, tcod.event.MouseMotion):
                self.mouse_location = event.tile

            # Let the current event handler process the event
            # It might change the game state or return an action
            self.event_handler.handle_event(event)

        # Process turn-based logic if in gameplay state and player is alive
        if self.game_state.is_player_turn and not self.player.fighter.is_dead:
             self.process_player_turn()


    def process_player_turn(self) -> None:
        """
        Check if the player has an action queued by the event handler
        and perform it. Then, handle enemy turns if applicable.
        """
        action = self.event_handler.get_action() # Get action queued by handler

        if action is None:
            return # No player action this frame

        try:
            # Perform the player's action
            # Assumes action.perform() returns True if turn is consumed, False otherwise
            # Or action has a 'consumes_turn' property
            turn_consumed = action.perform() # Perform should now signal turn consumption

            if turn_consumed:
                 # If player action consumed a turn, handle enemy turns
                 self.handle_enemy_turns()
                 # Update FOV after all turns are processed for the round
                 self.update_fov() # Update FOV once per round after all movements

            # Check for player death after player action and enemy reactions
            self.check_player_death()

        except exceptions.ImpossibleAction as exc:
            self.message_log.add_message(str(exc), color.impossible)
            # Do not advance turn if action was impossible
            return


    def handle_enemy_turns(self) -> None:
        """Iterate through actors and let them perform actions via their AI."""
        # Use list(self.game_map.actors) to avoid issues if actors die/are removed mid-iteration
        for actor in list(self.game_map.actors):
            if actor is not self.player and actor.ai and actor.fighter and not actor.fighter.is_dead:
                try:
                    # Let the AI determine and perform an action
                    # AI's perform method should execute the chosen action
                    actor.ai.perform()

                    # Check if the player died as a result of this enemy's action
                    self.check_player_death()
                    if self.player.fighter.is_dead:
                        break # Stop processing enemy turns if player died

                except exceptions.ImpossibleAction:
                    # AI tried an impossible action, just skip its turn
                    pass
                except Exception as e:
                    # Log unexpected AI errors
                    print(f"Error in AI for {actor.name}: {e}")
                    import traceback
                    traceback.print_exc()


    # --- Field of View ---

    def update_fov(self) -> None:
        """Recompute the player's FOV and update explored tiles."""
        # Delegate FOV computation to the GameMap instance
        self.game_map.compute_fov(self.player.x, self.player.y, FOV_RADIUS)


    # --- Rendering ---

    def render(self, console: Console, context: Context) -> None:
        """Render the game screen, including map, UI, and entities."""
        # Call the centralized rendering function
        render_functions.render_all(
            engine=self,
            console=console,
            # Pass necessary parameters for rendering UI etc.
            # screen_width=console.width,
            # screen_height=console.height,
            # ... other UI parameters (bar width, panel height etc.)
        )

        # Present the drawn console to the context
        context.present(console)

        # Clear the console for the *next* frame AFTER presenting
        console.clear()

    # --- Utility Methods ---

    def get_actor_at_location(self, x: int, y: int) -> Optional[Actor]:
        """Return the Actor at a given location, if any."""
        # Assumes GameMap provides an efficient way to get actors
        return self.game_map.get_actor_at_location(x, y)

    # --- Saving and Loading ---

    def save_game(self, filename: str = SAVE_FILE) -> None:
        """Save the current game state to a compressed file."""
        # Create a savable version of the engine state.
        # Event handlers are often tricky to pickle, might need reconstruction.
        # Create a copy, null out non-serializable parts or replace with placeholders.
        save_data = lzma.compress(pickle.dumps(self))
        try:
            with open(filename, "wb") as f:
                f.write(save_data)
            self.message_log.add_message(f"Game saved to {filename}.", color.save_text)
        except Exception as e:
            self.message_log.add_message(f"Error saving game: {e}", color.error_text)
            print(f"Error saving game: {e}")

    @staticmethod
    def load_game(filename: str = SAVE_FILE) -> Engine:
        """Load a game state from a compressed file."""
        if not os.path.exists(filename):
            raise FileNotFoundError(f"Save file '{filename}' not found.")
        try:
            with open(filename, "rb") as f:
                engine_data = lzma.decompress(f.read())
            engine = pickle.loads(engine_data)
            # Re-initialize non-pickled parts if necessary (e.g., event handler logic)
            if not hasattr(engine, 'game_state') or not engine.game_state: # Check if state needs reset
                engine.game_state = GameState(engine) # Reset to default gameplay state
            # Ensure event handler matches the loaded state
            engine.event_handler = engine.game_state.event_handler
            print("Game loaded successfully.")
            engine.message_log.add_message("Game loaded.", color.welcome_text)
            return engine
        except Exception as e:
            print(f"Error loading game: {e}")
            raise # Re-raise exception after logging
