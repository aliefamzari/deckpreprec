#!/usr/bin/env python3
"""
Curses UI Module
Original curses interface extracted for parallel development
"""

import curses
import time
import sys
import os

# Import shared modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from shared.config import TapeConfig, COLOR_CYAN, COLOR_MAGENTA, COLOR_YELLOW, COLOR_GREEN, COLOR_RED, COLOR_BLUE, COLOR_WHITE
from shared.audio_processor import list_tracks, normalize_tracks
from shared.deck_profiles import get_tape_type_info
from shared.counter_engine import calibrate_counter_wizard
from shared.tracklist_generator import format_duration, write_deck_tracklist


def safe_addstr(stdscr, y, x, text, attr=0):
    """Safely add string to screen with boundary checking"""
    try:
        max_y, max_x = stdscr.getmaxyx()
        if y < max_y - 1 and x < max_x - 1:
            # Truncate text if it would exceed screen width
            available_width = max_x - x - 1
            if len(text) > available_width:
                text = text[:available_width]
            stdscr.addstr(y, x, text, attr)
    except:
        pass


def init_colors():
    """Initialize 80s-style color scheme"""
    if curses.has_colors():
        curses.start_color()
        curses.init_pair(1, curses.COLOR_CYAN, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_MAGENTA, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)
        curses.init_pair(4, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(5, curses.COLOR_RED, curses.COLOR_BLACK)
        curses.init_pair(6, curses.COLOR_BLUE, curses.COLOR_BLACK)
        curses.init_pair(7, curses.COLOR_WHITE, curses.COLOR_BLACK)


def draw_cassette_art(stdscr, y, x):
    """Draw ASCII cassette tape art"""
    art = [
        " ___________________________________________",
        "|  _______________________________________  |",
        "| / .-----------------------------------. \\ |",
        "| | | /\\ :                        90 min| | |",
        "| | |/--\\:....................... NR [ ]| | |",
        "| | `-----------------------------------' | |",
        "| |      //-\\\\   |         |   //-\\\\      | |",
        "| |     ||( )||  |_________|  ||( )||     | |",
        "| |      \\\\-//   :....:....:   \\\\-//      | |",
        "| |       _ _ ._  _ _ .__|_ _.._  _       | |",
        "| |      (_(_)| |(_(/_|  |_(_||_)(/_      | |",
        "| |               low noise   |           | |",
        "| `______ ____________________ ____ ______' |",
        "|        /    []             []    \\        |",
        "|       /  ()                   ()  \\       |",
        "!______/_____________________________\\______!"
    ]
    for i, line in enumerate(art):
        try:
            stdscr.addstr(y + i, x, line, curses.color_pair(COLOR_MAGENTA))
        except:
            pass


def draw_config_info(stdscr, y, x, config: TapeConfig, selected_tracks=None, show_warning=False):
    """Draw current configuration information"""
    mode_names = {
        "manual": "Manual Calibrated",
        "auto": "Auto Physics", 
        "static": "Static Linear"
    }
    
    # Multi-line detailed format
    safe_addstr(stdscr, y, x, "CONFIGURATION:", curses.color_pair(COLOR_MAGENTA) | curses.A_BOLD)
    
    counter_info = f"Counter: {mode_names.get(config.counter_mode, config.counter_mode)}"
    if config.counter_mode == "static":
        counter_info += f" ({config.counter_rate} counts/sec)"
    elif config.counter_mode == "manual" and config.calibration_data:
        deck = config.calibration_data.get('deck_model', 'Unknown')
        counter_info += f" ({deck})"
    safe_addstr(stdscr, y + 1, x, counter_info, curses.color_pair(COLOR_CYAN))
    
    # Tape type information
    tape_info = get_tape_type_info(config.tape_type)
    tape_line = f"Tape: {config.tape_type} - {tape_info['name']} ({tape_info['bias']})"
    safe_addstr(stdscr, y + 2, x, tape_line, curses.color_pair(COLOR_CYAN))
    
    norm_info = f"Audio: {config.normalization_method.upper()} normalization"
    if config.normalization_method == "lufs":
        norm_info += f" (target: {config.target_lufs:+.1f} LUFS)"
    safe_addstr(stdscr, y + 3, x, norm_info, curses.color_pair(COLOR_CYAN))
    
    timing_info = f"Timing: {config.leader_gap_seconds}s leader + {config.track_gap_seconds}s gaps"
    safe_addstr(stdscr, y + 4, x, timing_info, curses.color_pair(COLOR_CYAN))
    
    # Total recording time and tape capacity (always display)
    if selected_tracks and len(selected_tracks) > 0:
        total_duration = sum(track.get('duration', 0) for track in selected_tracks)
        total_with_gaps = total_duration + (config.track_gap_seconds * (len(selected_tracks) - 1)) + config.leader_gap_seconds
    else:
        total_with_gaps = 0
    
    # Colors and attributes for warning
    time_color = COLOR_RED if show_warning else COLOR_CYAN
    time_attr = curses.A_BOLD | curses.A_BLINK if show_warning else 0
    
    safe_addstr(stdscr, y + 5, x, "Total Recording Time: ", curses.color_pair(COLOR_CYAN))
    safe_addstr(stdscr, y + 5, x + 22, format_duration(total_with_gaps), curses.color_pair(time_color) | time_attr)
    
    # Tape length with C-type indicator
    tape_type_indicator = ""
    if config.total_duration_minutes == 30:
        tape_type_indicator = " (C60)"
    elif config.total_duration_minutes == 45:
        tape_type_indicator = " (C90)"
    elif config.total_duration_minutes == 60:
        tape_type_indicator = " (C120)"
    
    safe_addstr(stdscr, y + 6, x, "Tape Length: ", curses.color_pair(COLOR_CYAN))
    tape_length_text = f"{config.total_duration_minutes}min{tape_type_indicator}"
    safe_addstr(stdscr, y + 6, x + 13, tape_length_text, curses.color_pair(time_color) | time_attr)
    
    if config.audio_latency > 0:
        latency_info = f"Audio latency compensation: {config.audio_latency}s"
        safe_addstr(stdscr, y + 7, x, latency_info, curses.color_pair(COLOR_YELLOW))
        return 8  # Height used
    
    return 7  # Height used (always includes timing info now)


class CursesUI:
    """Original curses interface implementation"""
    
    def __init__(self, config: TapeConfig):
        self.config = config
        self.tracks = []
        self.selected_tracks = []
        self.current_index = 0
    
    def run(self):
        """Run the curses interface"""
        # Load tracks
        self.tracks = list_tracks(self.config.target_folder)
        if not self.tracks:
            print("No audio tracks found in the folder!")
            input("Press Enter to exit...")
            return
        
        # Start curses interface
        curses.wrapper(self._main_loop)
    
    def _main_loop(self, stdscr):
        """Main curses event loop"""
        init_colors()
        curses.curs_set(0)
        stdscr.nodelay(True)
        
        while True:
            stdscr.erase()
            max_y, max_x = stdscr.getmaxyx()
            
            # Draw cassette art
            draw_cassette_art(stdscr, 2, 2)
            
            # Draw configuration
            config_height = draw_config_info(stdscr, 20, 2, self.config, self.selected_tracks)
            
            # Draw track list
            track_y = 30
            safe_addstr(stdscr, track_y, 2, "TRACKS:", curses.color_pair(COLOR_YELLOW) | curses.A_BOLD)
            
            for i, track in enumerate(self.tracks):
                y_pos = track_y + 2 + i
                if y_pos >= max_y - 5:
                    break
                
                # Highlight current track
                attr = curses.color_pair(COLOR_GREEN) if i == self.current_index else curses.color_pair(COLOR_WHITE)
                if track in self.selected_tracks:
                    attr |= curses.A_BOLD
                
                marker = "?" if i == self.current_index else " "
                selected_marker = "?" if track in self.selected_tracks else "?"
                
                track_line = f"{marker} {selected_marker} {track['name']} - {format_duration(track['duration'])}"
                safe_addstr(stdscr, y_pos, 2, track_line, attr)
            
            # Draw controls
            controls_y = max_y - 4
            safe_addstr(stdscr, controls_y, 2, "CONTROLS:", curses.color_pair(COLOR_MAGENTA) | curses.A_BOLD)
            safe_addstr(stdscr, controls_y + 1, 2, "?/?:Navigate  Space:Select  Enter:Record  Q:Quit", curses.color_pair(COLOR_WHITE))
            
            stdscr.refresh()
            
            # Handle input
            key = stdscr.getch()
            if key != -1:
                if key in (ord('q'), ord('Q')):
                    break
                elif key == curses.KEY_UP:
                    self.current_index = max(0, self.current_index - 1)
                elif key == curses.KEY_DOWN:
                    self.current_index = min(len(self.tracks) - 1, self.current_index + 1)
                elif key == ord(' '):
                    # Toggle selection
                    current_track = self.tracks[self.current_index]
                    if current_track in self.selected_tracks:
                        self.selected_tracks.remove(current_track)
                    else:
                        self.selected_tracks.append(current_track)
                elif key in (curses.KEY_ENTER, 10, 13):
                    if self.selected_tracks:
                        self._start_recording()
                        break
            
            time.sleep(0.05)
    
    def _start_recording(self):
        """Start the recording process"""
        print("\nNormalizing tracks...")
        normalized_tracks = normalize_tracks(
            self.selected_tracks,
            self.config.target_folder,
            self.config.normalization_method,
            self.config.target_lufs
        )
        
        # Generate tracklist
        tracklist_path = write_deck_tracklist(
            normalized_tracks,
            self.config.track_gap_seconds,
            self.config.target_folder,
            self.config.leader_gap_seconds,
            self.config.normalization_method,
            self.config.target_lufs,
            self.config.tape_type,
            self.config.counter_mode,
            self.config.counter_rate,
            self.config.calibration_data,
            self.config.counter_config_path,
            self.config.total_duration_minutes,
            self.config.audio_latency,
            self.config.calculate_tape_counter,
            get_tape_type_info
        )
        
        print(f"Recording ready! Tracklist saved to: {tracklist_path}")
        print("Press Enter to exit...")
        input()


def main():
    """Run the curses tape deck interface"""
    from shared.config import create_argument_parser
    parser = create_argument_parser()
    args = parser.parse_args()
    
    # Handle calibration mode
    if args.calibrate_counter:
        calibrate_counter_wizard(args.folder, args.counter_config)
        return
    
    # Initialize configuration
    config = TapeConfig(args)
    if not config.load_calibration_data():
        sys.exit(1)
    
    # Run curses UI
    ui = CursesUI(config)
    ui.run()


if __name__ == "__main__":
    main()