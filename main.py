#!/usr/bin/env python3
import copy # Needed for deep copying entities, especially the player
import traceback # For error logging
import os # For save file path handling

import tcod

# --- Assuming new/updated module imports ---
import color # Assumed module for color definitions (e.g., color.player_atk, color.enemy_atk)
from engine import Engine
# Entity now likely uses a component system
from entity import Entity
# EventHandler needs significant updates to handle different game states and actions
from input_handlers import MainGameEventHandler, GameOverEventHandler, EventHandler # Base class might be needed
from message_log import MessageLog # New module for handling messages
# Procgen likely needs updates to place monsters and items
from procgen import generate_dungeon
# New modules/classes for core systems
import components # e.g., components.Fighter, components.BasicMonsterAI
import game_states # e.g., game_states.GameplayState, game_states.MainMenuState etc. (if using state pattern)
import render_functions # e.g., render_functions.render_all, render_functions.render_bar

# --- Centralized Constants ---
SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50

MAP_WIDTH = 80
# Make map height smaller to accommodate UI panel
MAP_HEIGHT = 43 # Adjusted from 45

# UI Panel constants
BAR_WIDTH = 20
PANEL_HEIGHT = SCREEN_HEIGHT - MAP_HEIGHT # Should be 7
PANEL_Y = SCREEN_HEIGHT - PANEL_HEIGHT
MESSAGE_X = BAR_WIDTH + 2
MESSAGE_WIDTH = SCREEN_WIDTH - BAR_WIDTH - 2
MESSAGE_HEIGHT = PANEL_HEIGHT - 1

# Dungeon Generation constants
ROOM_MAX_SIZE = 10
ROOM_MIN_SIZE = 6
MAX_ROOMS = 30
# New constants for populating the dungeon
MAX_MONSTERS_PER_ROOM = 2
MAX_ITEMS_PER_ROOM = 2 # Example

# FOV Constants
FOV_ALGORITHM = tcod.FOV_SYMMETRIC_SHADOWCAST
FOV_LIGHT_WALLS = True
FOV_RADIUS = 8

# File paths
SAVE_FILE = "savegame.sav"


def setup_game() -> Engine:
    """Initializes and returns a new Engine instance for a new game."""
    print("Setting up new game...")

    # --- Core Game Objects ---
    event_handler: EventHandler = MainGameEventHandler() # Start with the main game handler
    message_log = MessageLog()

    # --- Player Setup ---
    # Create components for the player
    fighter_component = components.Fighter(hp=30, defense=2, power=5)
    level_component = components.Level(level_up_base=200) # Example Level component
    # Player starts with no specific AI component (controlled by input)
    player = Entity(
        x=0, y=0, # Positioned by generate_dungeon
        char="@",
        color=color.player, # Use color definitions
        name="Player",
        blocks_movement=True,
        fighter=fighter_component, # Add components
        level=level_component,
    )

    # --- Engine Initialization (Initial) ---
    # Initialize engine early with player and message log, map/entities come next
    engine = Engine(event_handler=event_handler, message_log=message_log, player=player)

    # --- Map Generation ---
    # generate_dungeon now needs to handle placing player, monsters, items
    # It might modify the engine's entities set directly or return lists
    engine.game_map = generate_dungeon(
        max_rooms=MAX_ROOMS,
        room_min_size=ROOM_MIN_SIZE,
        room_max_size=ROOM_MAX_SIZE,
        map_width=MAP_WIDTH,
        map_height=MAP_HEIGHT,
        max_monsters_per_room=MAX_MONSTERS_PER_ROOM,
        max_items_per_room=MAX_ITEMS_PER_ROOM,
        engine=engine, # Pass engine to place entities/player directly
    )
    # Ensure tile properties (walkable/transparent) are updated after generation
    engine.game_map.update_tile_properties()

    # Add a welcome message
    engine.message_log.add_message(
        "Hello and welcome, adventurer, to yet another dungeon!", color.welcome_text
    )

    # --- Initial FOV Calculation ---
    engine.update_fov()

    # Set initial game state (if using a state machine in Engine)
    # engine.game_state = game_states.GameplayState() # Or handled internally

    print("Setup complete.")
    return engine

def load_game() -> Engine:
    """Loads an Engine instance from the save file."""
    if not os.path.exists(SAVE_FILE):
        raise FileNotFoundError("Save file not found.")

    import pickle # Or shelve, dill, etc.
    with open(SAVE_FILE, "rb") as f:
        engine = pickle.load(f)
    print("Game loaded.")
    # Make sure the loaded event handler is appropriate (might need reset)
    if not isinstance(engine.event_handler, MainGameEventHandler):
        # Could happen if saved during inventory screen etc. Reset to main handler.
        engine.event_handler = MainGameEventHandler(engine) # Pass engine if needed
        print("Resetting event handler to main game.")
    # Add a message confirming load
    engine.message_log.add_message("Game loaded successfully!", color.welcome_text)
    return engine

# --- Main Menu Function (Conceptual) ---
def main_menu(root_console: tcod.Console, context: tcod.context.Context) -> str:
    """Displays the main menu and returns the chosen action ('new', 'load', 'quit')."""
    menu_options = ["(N) New Game", "(L) Load Game", "(Q) Quit"]
    selected_option = 0

    while True:
        # Clear console and draw menu title
        root_console.clear()
        root_console.print(
            x=root_console.width // 2,
            y=root_console.height // 2 - 4,
            string="YET ANOTHER ROGUELIKE",
            fg=color.menu_title,
            alignment=tcod.CENTER
        )
        root_console.print(
            x=root_console.width // 2,
            y=root_console.height - 2,
            string="By You", # Your name/handle
            fg=color.menu_title,
            alignment=tcod.CENTER
        )

        # Draw options
        for i, option_text in enumerate(menu_options):
            color_fg = color.menu_text_selected if i == selected_option else color.menu_text
            root_console.print(
                x=root_console.width // 2,
                y=root_console.height // 2 - 2 + i,
                string=option_text,
                fg=color_fg,
                alignment=tcod.CENTER
            )

        context.present(root_console) # Display the menu

        # --- Event Handling for Menu ---
        for event in tcod.event.wait():
            context.convert_event(event) # Sets mouse position if needed

            if isinstance(event, tcod.event.Quit):
                return "quit" # Chosen action

            if isinstance(event, tcod.event.KeyDown):
                key = event.sym
                if key == tcod.event.KeySym.n:
                    return "new"
                elif key == tcod.event.KeySym.l:
                    return "load"
                elif key == tcod.event.KeySym.q or key == tcod.event.KeySym.ESCAPE:
                    return "quit"
                # Add arrow key navigation if desired (UP/DOWN to change selected_option)
                elif key == tcod.event.KeySym.UP:
                    selected_option = (selected_option - 1) % len(menu_options)
                elif key == tcod.event.KeySym.DOWN:
                    selected_option = (selected_option + 1) % len(menu_options)
                elif key == tcod.event.KeySym.RETURN or key == tcod.event.KeySym.KP_ENTER:
                    if selected_option == 0: return "new"
                    if selected_option == 1: return "load"
                    if selected_option == 2: return "quit"

    return "quit" # Default exit case


def main() -> None:
    # --- Basic Setup ---
    tileset = tcod.tileset.load_tilesheet(
        "image.png", 32, 8, tcod.tileset.CHARMAP_TCOD # Ensure image path is correct
    )

    engine: Optional[Engine] = None # Engine might not exist until game started/loaded

    # --- TCOD Context and Console ---
    with tcod.context.new_terminal(
        SCREEN_WIDTH,
        SCREEN_HEIGHT,
        tileset=tileset,
        title="Yet Another Roguelike",
        vsync=True,
    ) as context:
        root_console = tcod.Console(SCREEN_WIDTH, SCREEN_HEIGHT, order="F")

        # --- Main Menu Loop ---
        while True: # Loop allows returning to menu after game over
            if engine is None: # Show main menu if no game is running
                menu_choice = main_menu(root_console, context)

                if menu_choice == "new":
                    try:
                        engine = setup_game()
                    except Exception:
                        traceback.print_exc() # Log error
                        engine = None # Prevent crash loop
                        # Optionally display an error message on screen here
                elif menu_choice == "load":
                    try:
                        engine = load_game()
                    except FileNotFoundError:
                        # Display "Save not found" message on menu screen (needs menu update)
                        print("Save file not found.")
                        engine = None
                    except Exception:
                        traceback.print_exc()
                        engine = None
                        # Display "Failed to load" message
                elif menu_choice == "quit":
                    print("Exiting.")
                    return # Exit main completely

            # --- Main Game Loop ---
            while engine: # Run as long as we have a valid engine instance
                try:
                    # Rendering (now likely uses a dedicated function)
                    # render_functions.render_all(
                    #     console=root_console,
                    #     context=context,
                    #     engine=engine,
                    #     screen_width=SCREEN_WIDTH,
                    #     screen_height=SCREEN_HEIGHT,
                    #     panel_height=PANEL_HEIGHT,
                    #     panel_y=PANEL_Y,
                    #     bar_width=BAR_WIDTH,
                    #     message_log=engine.message_log, # Pass necessary parts
                    #     message_x=MESSAGE_X,
                    #     message_width=MESSAGE_WIDTH,
                    #     message_height=MESSAGE_HEIGHT,
                    # )
                    # Simplified version if render_all is part of Engine:
                    engine.render(console=root_console, context=context)


                    # Event Handling (Engine handles state changes)
                    events = tcod.event.wait()
                    engine.handle_events(events)

                    # --- Game Over Check ---
                    # Assuming Engine updates its state or EventHandler appropriately
                    if isinstance(engine.event_handler, GameOverEventHandler):
                         # Optionally save high score etc. here
                         save_game(engine) # Example: Auto-save on game over? Or maybe not.
                         engine = None # Clear engine to return to main menu
                         print("Game Over! Returning to main menu.")
                         # Game over screen is handled by the GameOverEventHandler render/loop

                except Exception: # Log exceptions during gameplay
                    traceback.print_exc() # Print error to console.
                    # Optionally: Save a crash report or attempt auto-save
                    if engine: # Try to save if engine exists
                       try:
                           save_game(engine, filename="crash_save.sav")
                           print("Attempted to save game state to crash_save.sav")
                       except Exception as e:
                           print(f"Crash save failed: {e}")
                    engine = None # Exit to menu after crash
                    print("An error occurred! Returning to main menu.")


if __name__ == "__main__":
    main()

# --- Placeholder Save/Load Functions (To be implemented properly) ---
def save_game(engine: Engine, filename: str = SAVE_FILE) -> None:
    """Saves the current Engine state to a file."""
    import pickle # Or other serialization library
    # The engine, containing the map, entities (with components), player ref, message log,
    # and current game state needs to be serializable.
    try:
        with open(filename, "wb") as f:
            pickle.dump(engine, f)
        print(f"Game saved to {filename}.")
        engine.message_log.add_message("Game saved.", color.save_text) # Feedback
    except Exception as e:
        print(f"Error saving game: {e}")
        engine.message_log.add_message(f"Error saving game: {e}", color.error_text)
        # Handle specific serialization errors if necessary
