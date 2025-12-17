#!/usr/bin/env python3
"""
Retro 80s Tape Deck Recording CLI
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

A nostalgic tape deck recording utility with 80s-inspired aesthetics for
preparing and recording audio tracks to cassette tapes.

Features:
  • Interactive curses-based UI with retro color scheme (cyan, magenta, yellow)
  • ASCII cassette tape art and box-drawing borders
  • Audio normalization with caching (skips existing normalized files)
  • 4-digit tape counter with configurable rate
  • Real-time VU meters displaying actual audio waveform levels (L/R channels)
  • Pre-analyzed audio with RMS-based level detection
  • Track selection with duration validation
  • 10-second prep countdown before recording
  • Real-time playback monitoring with track positions
  • Generates detailed tracklist reference file with counter positions

Usage:
  python3 decprec.py --folder ./tracks --track-gap 5 --duration 60 --counter-rate 1.0 --leader-gap 10

Arguments:
  --folder        Path to audio tracks directory (default: ./tracks)
  --track-gap     Gap between tracks in seconds (default: 5)
  --duration      Maximum tape duration in minutes (default: 60)
  --counter-rate  Tape counter increments per second (default: 1.0)
  --leader-gap    Leader gap before first track in seconds (default: 10)

Keyboard Controls:
  Main Menu:
    Up/Down       Navigate tracks
    Space         Select/deselect track
    P             Preview track
    X             Stop preview
    Enter         Normalize and start recording
    Q             Quit
  
  Recording Mode:
    Q             Return to main menu

Supported Formats: MP3, WAV, FLAC, WebM, M4A, AAC, OGG

Requirements: ffmpeg, ffprobe, ffplay, pydub

Author: Improved by GitHub Copilot
License: MIT
"""

import os
import sys
import subprocess
import json
import signal
import argparse
import time
import curses
import random
import math
import numpy as np
from datetime import datetime
from pydub import AudioSegment

# --- Deck Profile Preset Loader ---
def load_deck_profile(profile_path, args):
    """Load deck profile JSON and override args namespace."""
    if not os.path.isfile(profile_path):
        print(f"\nERROR: Deck profile '{profile_path}' not found.\n")
        sys.exit(1)
    try:
        with open(profile_path, 'r') as f:
            profile = json.load(f)
    except Exception as e:
        print(f"\nERROR: Failed to load deck profile: {e}\n")
        sys.exit(1)
    # Map profile keys to arg names
    mapping = {
        'counter_mode': 'counter_mode',
        'counter_config': 'counter_config',
        'counter_rate': 'counter_rate',
        'leader_gap': 'leader_gap',
        'normalization': 'normalization',
        'target_lufs': 'target_lufs',
        'tape_type': 'tape_type',
        'deck_model': 'deck_model',
        'folder': 'folder',
        'duration': 'duration',
        'track_gap': 'track_gap',
    }
    for k, v in profile.items():
        if k in mapping:
            setattr(args, mapping[k], v)
    print(f"\n✓ Loaded deck profile: {profile_path}")
    if 'deck_model' in profile:
        print(f"  Deck: {profile['deck_model']}")
    if 'tape_type' in profile:
        print(f"  Tape: {profile['tape_type']}")
    print()
    return args
try:
    import pyloudnorm as pyln
    PYLOUDNORM_AVAILABLE = True
except ImportError:
    PYLOUDNORM_AVAILABLE = False
    pyln = None

# --- Argument parsing ---
parser = argparse.ArgumentParser(description="Audio Player for Tape Recording")
parser.add_argument("--track-gap", type=int, default=5, help="Gap between tracks in seconds (default: 5)")
parser.add_argument("--duration", type=int, default=30, help="Maximum tape duration in minutes per side (default: 30 - C60 cassette side)")
parser.add_argument("--folder", type=str, default="./tracks", help="Folder with audio tracks")
parser.add_argument("--counter-rate", type=float, default=1.0, help="Tape counter increments per second for static mode (default: 1.0)")
parser.add_argument("--counter-mode", type=str, default="static", choices=["manual", "auto", "static"], help="Counter calculation mode: 'manual' (calibrated), 'auto' (physics), 'static' (constant rate) (default: static)")
parser.add_argument("--calibrate-counter", action="store_true", help="Run interactive counter calibration wizard")
parser.add_argument("--counter-config", type=str, default="counter_calibration.json", help="Path to counter calibration config file for manual mode (default: counter_calibration.json)")
parser.add_argument("--leader-gap", type=int, default=10, help="Leader gap before first track in seconds (default: 10)")
parser.add_argument("--normalization", type=str, default="lufs", choices=["peak", "lufs"], help="Normalization method: 'peak' or 'lufs' (default: lufs)")
parser.add_argument("--target-lufs", type=float, default=-14.0, help="Target LUFS level for LUFS normalization (default: -14.0)")
parser.add_argument("--audio-latency", type=float, default=0.0, help="Audio latency compensation in seconds for VU meter sync (default: 0.0, try 0.1-0.5 if audio lags behind meters)")
parser.add_argument("--tape-type", type=str, default="Type I", choices=["Type I", "Type II", "Type III", "Type IV"], help="Cassette tape type: Type I (Normal/Ferric), Type II (Chrome/High Bias), Type III (Ferrochrome), Type IV (Metal) (default: Type I)")
parser.add_argument("--ffmpeg-path", type=str, default="/usr/bin/ffmpeg", help="Path to ffmpeg binary (default: /usr/bin/ffmpeg)")
parser.add_argument("--deck-profile", type=str, default=None, help="Path to deck profile preset JSON (overrides most options)")
args = parser.parse_args()

# --- Deck Profile Preset Application ---
if args.deck_profile:
    args = load_deck_profile(args.deck_profile, args)

TRACK_GAP_SECONDS = args.track_gap
TOTAL_DURATION_MINUTES = args.duration
TARGET_FOLDER = args.folder
COUNTER_RATE = args.counter_rate
COUNTER_MODE = args.counter_mode
COUNTER_CONFIG_PATH = args.counter_config
LEADER_GAP_SECONDS = args.leader_gap
NORMALIZATION_METHOD = args.normalization
TARGET_LUFS = args.target_lufs
AUDIO_LATENCY = args.audio_latency
TAPE_TYPE = args.tape_type
FFMPEG_PATH = args.ffmpeg_path

# Tape reel physics constants for realistic counter behavior
TAPE_THICKNESS = 0.016  # mm - standard cassette tape thickness
HUB_RADIUS = 10.0  # mm - radius of empty hub/spool
TAPE_SPEED = 47.625  # mm/s - standard cassette speed (1 7/8 ips)
TAPE_LENGTH = TOTAL_DURATION_MINUTES * 60 * TAPE_SPEED  # Total tape length in mm

# Add /usr/sbin to PATH for ffmpeg/ffprobe/ffplay if present
os.environ["PATH"] += os.pathsep + "/usr/sbin"

# Add ffmpeg directory to PATH (for ffprobe/ffplay) and set converter
ffmpeg_dir = os.path.dirname(FFMPEG_PATH)
if ffmpeg_dir and ffmpeg_dir not in os.environ["PATH"]:
    os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ["PATH"]
AudioSegment.converter = FFMPEG_PATH

# Global ffplay process used for preview playback (from main menu)
ffplay_proc = None

# Color pairs (initialized in curses)
COLOR_CYAN = 1
COLOR_MAGENTA = 2
COLOR_YELLOW = 3
COLOR_GREEN = 4
COLOR_RED = 5
COLOR_BLUE = 6
COLOR_WHITE = 7

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

def draw_retro_border(stdscr, y, x, width, title=""):
    """Draw 80s-style border with optional title"""
    try:
        stdscr.addstr(y, x, "╔" + "═" * (width - 2) + "╗", curses.color_pair(COLOR_CYAN))
        if title:
            title_x = x + (width - len(title)) // 2
            stdscr.addstr(y, title_x - 1, "═", curses.color_pair(COLOR_CYAN))
            stdscr.addstr(y, title_x, title, curses.color_pair(COLOR_MAGENTA) | curses.A_BOLD)
            stdscr.addstr(y, title_x + len(title), "═", curses.color_pair(COLOR_CYAN))
    except:
        pass

def draw_cassette_art(stdscr, y, x):
    """Draw ASCII cassette tape art from cassette.txt"""
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

# Global calibration data loaded from config file
CALIBRATION_DATA = None

def load_calibration_config(config_path):
    """Load manual calibration data from JSON config file"""
    try:
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                return json.load(f)
        else:
            print(f"Warning: Calibration file '{config_path}' not found.")
            print("Run with --calibrate-counter to create calibration file.")
            return None
    except Exception as e:
        print(f"Error loading calibration file: {e}")
        return None

def get_tape_type_info(tape_type):
    """Get detailed information about cassette tape type"""
    tape_info = {
        "Type I": {
            "name": "Normal (Ferric Oxide)",
            "material": "Ferric Oxide",
            "color": "Brown",
            "sound": "Good bass, lacks high-frequency detail",
            "bias": "Standard (120µs EQ)",
            "notches": "Standard write-protect only"
        },
        "Type II": {
            "name": "Chrome/High Bias", 
            "material": "Chromium Dioxide (CrO₂)",
            "color": "Dark brown/black",
            "sound": "Crisp highs, better dynamics",
            "bias": "High bias (70µs EQ)",
            "notches": "Extra detection notches"
        },
        "Type III": {
            "name": "Ferrochrome (Rare)",
            "material": "Ferric + Chrome mix",
            "color": "Varies",
            "sound": "Type I bass + Type II highs",
            "bias": "High bias (70µs EQ)", 
            "notches": "Distinct pattern"
        },
        "Type IV": {
            "name": "Metal (Pure Metal)",
            "material": "Pure metal particles",
            "color": "Solid black",
            "sound": "Highest output, best clarity",
            "bias": "Metal bias (70µs EQ)",
            "notches": "Third center notch set"
        }
    }
    return tape_info.get(tape_type, tape_info["Type I"])

def calculate_tape_counter(elapsed_seconds):
    """
    Calculate tape counter based on selected mode.
    
    Modes:
    - 'manual': Uses user-calibrated checkpoints with interpolation
    - 'auto': Physics-based simulation using reel mechanics
    - 'static': Constant linear rate
    
    Args:
        elapsed_seconds: Time elapsed in seconds
    
    Returns:
        Integer counter value
    """
    if COUNTER_MODE == "manual":
        return calculate_counter_manual(elapsed_seconds)
    elif COUNTER_MODE == "auto":
        return calculate_counter_auto(elapsed_seconds)
    else:  # static
        return calculate_counter_static(elapsed_seconds)

def calculate_counter_static(elapsed_seconds):
    """
    Static counter: constant rate throughout tape.
    Simple linear calculation.
    """
    return int(elapsed_seconds * COUNTER_RATE)

def calculate_counter_manual(elapsed_seconds):
    """
    Manual calibrated counter: interpolates between user-measured checkpoints.
    Uses linear interpolation between calibration points.
    """
    global CALIBRATION_DATA
    
    if CALIBRATION_DATA is None:
        # Fallback to static if no calibration data
        return calculate_counter_static(elapsed_seconds)
    
    checkpoints = CALIBRATION_DATA.get('checkpoints', [])
    if not checkpoints:
        return calculate_counter_static(elapsed_seconds)
    
    # Sort checkpoints by time
    checkpoints = sorted(checkpoints, key=lambda x: x['time_seconds'])
    
    # Before first checkpoint: extrapolate from 0,0 to first checkpoint
    # Assumes tape counter was reset to 000 at the start of recording
    if elapsed_seconds <= checkpoints[0]['time_seconds']:
        t1, c1 = checkpoints[0]['time_seconds'], checkpoints[0]['counter']
        # Calculate rate from origin (0,0) to first checkpoint
        rate = c1 / t1 if t1 > 0 else 0
        return int(elapsed_seconds * rate)
    
    # After last checkpoint: extrapolate from last two points
    if elapsed_seconds >= checkpoints[-1]['time_seconds']:
        if len(checkpoints) >= 2:
            t1, c1 = checkpoints[-2]['time_seconds'], checkpoints[-2]['counter']
            t2, c2 = checkpoints[-1]['time_seconds'], checkpoints[-1]['counter']
            rate = (c2 - c1) / (t2 - t1)
            return int(c2 + rate * (elapsed_seconds - t2))
        else:
            rate = checkpoints[0]['counter'] / checkpoints[0]['time_seconds']
            return int(elapsed_seconds * rate)
    
    # Between checkpoints: linear interpolation
    for i in range(len(checkpoints) - 1):
        t1, c1 = checkpoints[i]['time_seconds'], checkpoints[i]['counter']
        t2, c2 = checkpoints[i + 1]['time_seconds'], checkpoints[i + 1]['counter']
        
        if t1 <= elapsed_seconds <= t2:
            # Linear interpolation
            factor = (elapsed_seconds - t1) / (t2 - t1)
            counter = c1 + (c2 - c1) * factor
            return int(counter)
    
    # Fallback
    return calculate_counter_static(elapsed_seconds)

def calculate_counter_auto(elapsed_seconds):
    """
    Auto physics-based counter: simulates tape reel mechanics.
    Counter rate varies with reel radius (faster at start, slower at end).
    """
    # Calculate how much tape has been consumed
    tape_consumed = min(elapsed_seconds * TAPE_SPEED, TAPE_LENGTH)
    
    # Calculate take-up reel radius based on tape wound onto it
    tape_area_on_takeup = tape_consumed * TAPE_THICKNESS
    takeup_radius = math.sqrt(HUB_RADIUS**2 + (tape_area_on_takeup / math.pi))
    
    # Normalize to match COUNTER_RATE at middle of tape
    mid_tape_length = TAPE_LENGTH / 2
    mid_tape_area = mid_tape_length * TAPE_THICKNESS
    mid_radius = math.sqrt(HUB_RADIUS**2 + (mid_tape_area / math.pi))
    
    # Counter scales inversely with radius
    counter_scale = mid_radius / takeup_radius
    counter_value = elapsed_seconds * COUNTER_RATE * counter_scale
    
    return int(counter_value)

def calibrate_counter_wizard():
    """
    Interactive wizard to calibrate tape counter.
    Guides user through measuring checkpoints and generates config file.
    """
    print("\n" + "="*70)
    print("    TAPE COUNTER CALIBRATION WIZARD")
    print("="*70)
    print("\nThis wizard will help you calibrate your tape deck counter.")
    print("\nPREPARATION:")
    print("  1. Insert a blank cassette tape (C60 or C90)")
    print("  2. Reset your tape deck counter to 000")
    print("  3. Have a stopwatch ready (or use your phone timer)")
    print("  4. Press RECORD on your deck to start the tape")
    print("\nYou will measure the counter value at specific time intervals.")
    print("The more checkpoints you measure, the more accurate the calibration.")
    print("\nRecommended checkpoints: 1min, 5min, 20min, 30min")
    print("Optional: End of tape side (for full calibration)")
    
    input("\nPress Enter when you're ready to start...")
    
    # Collect metadata
    print("\n" + "-"*70)
    print("DECK INFORMATION (optional, press Enter to skip):")
    tape_type = input("  Tape type (e.g., C60, C90): ").strip() or "Unknown"
    deck_model = input("  Deck model (e.g., Sony TC-D5M): ").strip() or "Unknown"
    
    # Define standard checkpoints
    suggested_times = [
        (60, "1 minute"),
        (300, "5 minutes"),
        (1200, "20 minutes"),
        (1800, "30 minutes")
    ]
    
    checkpoints = []
    
    print("\n" + "-"*70)
    print("CHECKPOINT MEASUREMENT:")
    print("For each checkpoint, let the tape run and note the counter value.")
    print("You can skip checkpoints by pressing Enter without a value.\n")
    
    for time_sec, label in suggested_times:
        minutes = time_sec // 60
        print(f"\nCheckpoint: {label} ({minutes} min / {time_sec} sec)")
        print(f"  → Let tape run to {minutes} minute(s) on your stopwatch")
        
        while True:
            counter_input = input(f"  → Enter counter value at {label}: ").strip()
            
            if not counter_input:
                print(f"  Skipped {label}")
                break
            
            try:
                counter_value = int(counter_input)
                if counter_value < 0:
                    print("  Error: Counter value must be positive. Try again.")
                    continue
                
                checkpoints.append({
                    "time_seconds": time_sec,
                    "counter": counter_value,
                    "note": label
                })
                print(f"  ✓ Recorded: {time_sec}s → {counter_value}")
                break
            except ValueError:
                print("  Error: Please enter a valid number. Try again.")
    
    # Optional: End of tape
    print("\n" + "-"*70)
    print("OPTIONAL: End of tape measurement")
    print("If you want to measure until the end of the tape side:")
    add_end = input("Measure end of tape? (y/n): ").strip().lower()
    
    if add_end == 'y':
        print("\nLet the tape run until it auto-stops at the end.")
        
        while True:
            time_input = input("Enter total time in seconds (or MM:SS format): ").strip()
            
            if not time_input:
                print("Skipped end measurement")
                break
            
            try:
                # Parse MM:SS or seconds
                if ':' in time_input:
                    parts = time_input.split(':')
                    time_sec = int(parts[0]) * 60 + int(parts[1])
                else:
                    time_sec = int(time_input)
                
                counter_input = input("Enter final counter value: ").strip()
                if not counter_input:
                    break
                    
                counter_value = int(counter_input)
                
                checkpoints.append({
                    "time_seconds": time_sec,
                    "counter": counter_value,
                    "note": "End of tape"
                })
                print(f"  ✓ Recorded: {time_sec}s → {counter_value}")
                break
            except ValueError:
                print("  Error: Invalid format. Try again.")
    
    if not checkpoints:
        print("\nNo checkpoints recorded. Calibration cancelled.")
        return
    
    # Sort checkpoints by time
    checkpoints = sorted(checkpoints, key=lambda x: x['time_seconds'])
    
    # Calculate statistics
    print("\n" + "="*70)
    print("CALIBRATION SUMMARY:")
    print(f"  Tape Type: {tape_type}")
    print(f"  Deck Model: {deck_model}")
    print(f"  Checkpoints Measured: {len(checkpoints)}")
    print("\n  Checkpoint Details:")
    
    for cp in checkpoints:
        minutes = cp['time_seconds'] // 60
        rate = cp['counter'] / cp['time_seconds']
        print(f"    {cp['note']:20s} → {cp['counter']:4d} (rate: {rate:.3f} counts/sec)")
    
    # Calculate average rate
    if len(checkpoints) >= 2:
        first_cp = checkpoints[0]
        last_cp = checkpoints[-1]
        time_diff = last_cp['time_seconds'] - first_cp['time_seconds']
        counter_diff = last_cp['counter'] - first_cp['counter']
        avg_rate = counter_diff / time_diff if time_diff > 0 else 0
        print(f"\n  Average Rate: {avg_rate:.3f} counts/second")
    
    # Create config structure
    config = {
        "tape_type": tape_type,
        "deck_model": deck_model,
        "calibration_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "checkpoints": checkpoints,
        "interpolation": "linear"
    }
    
    # Save to file
    config_path = os.path.join(TARGET_FOLDER, COUNTER_CONFIG_PATH)
    os.makedirs(os.path.dirname(config_path) if os.path.dirname(config_path) else '.', exist_ok=True)
    
    try:
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        print("\n" + "="*70)
        print(f"✓ Calibration saved to: {config_path}")
        print("\nTo use this calibration:")
        print(f"  python3 decprec.py --counter-mode manual --folder {TARGET_FOLDER}")
        print("\nYou can edit the JSON file manually if needed.")
        print("="*70 + "\n")
    except Exception as e:
        print(f"\nError saving calibration file: {e}")

def format_duration(seconds):
    if seconds is None or seconds == "Unknown":
        return "Unknown"
    seconds = int(round(seconds))
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes}:{secs:02d}"

def draw_config_info(stdscr, y, x, compact=False, selected_tracks=None, show_warning=False):
    """Draw current configuration information"""
    mode_names = {
        "manual": "Manual Calibrated",
        "auto": "Auto Physics", 
        "static": "Static Linear"
    }
    
    if compact:
        # Single line compact format for recording mode
        config_text = f"Tape Counter Config: {mode_names.get(COUNTER_MODE, COUNTER_MODE)}"
        if COUNTER_MODE == "static":
            config_text += f" ({COUNTER_RATE:.1f})"
        elif COUNTER_MODE == "manual" and CALIBRATION_DATA:
            deck = CALIBRATION_DATA.get('deck_model', 'Unknown')
            tape = CALIBRATION_DATA.get('tape_type', TAPE_TYPE)
            if deck != 'Unknown':
                config_text += f" ({deck}/{tape})"
        config_text += f" | {NORMALIZATION_METHOD.upper()}"
        if NORMALIZATION_METHOD == "lufs":
            config_text += f" {TARGET_LUFS:+.1f}dB"
        config_text += f" | Gap:{TRACK_GAP_SECONDS}s | Lead:{LEADER_GAP_SECONDS}s"
        safe_addstr(stdscr, y, x, config_text, curses.color_pair(COLOR_CYAN))
        return 1  # Height used
    else:
        # Multi-line detailed format for main menu and preview
        safe_addstr(stdscr, y, x, "CONFIGURATION:", curses.color_pair(COLOR_MAGENTA) | curses.A_BOLD)
        
        counter_info = f"Counter: {mode_names.get(COUNTER_MODE, COUNTER_MODE)}"
        if COUNTER_MODE == "static":
            counter_info += f" ({COUNTER_RATE} counts/sec)"
        elif COUNTER_MODE == "manual" and CALIBRATION_DATA:
            deck = CALIBRATION_DATA.get('deck_model', 'Unknown')
            counter_info += f" ({deck})"
        safe_addstr(stdscr, y + 1, x, counter_info, curses.color_pair(COLOR_CYAN))
        
        # Tape type information
        tape_info = get_tape_type_info(TAPE_TYPE)
        tape_line = f"Tape: {TAPE_TYPE} - {tape_info['name']} ({tape_info['bias']})"
        safe_addstr(stdscr, y + 2, x, tape_line, curses.color_pair(COLOR_CYAN))
        
        norm_info = f"Audio: {NORMALIZATION_METHOD.upper()} normalization"
        if NORMALIZATION_METHOD == "lufs":
            norm_info += f" (target: {TARGET_LUFS:+.1f} LUFS)"
        safe_addstr(stdscr, y + 3, x, norm_info, curses.color_pair(COLOR_CYAN))
        
        timing_info = f"Timing: {LEADER_GAP_SECONDS}s leader + {TRACK_GAP_SECONDS}s gaps"
        safe_addstr(stdscr, y + 4, x, timing_info, curses.color_pair(COLOR_CYAN))
        
        # Total recording time and tape capacity (always display)
        if selected_tracks and len(selected_tracks) > 0:
            total_duration = sum(track.get('duration', 0) for track in selected_tracks)
            total_with_gaps = total_duration + (TRACK_GAP_SECONDS * (len(selected_tracks) - 1)) + LEADER_GAP_SECONDS
            at_capacity = total_with_gaps >= TOTAL_DURATION_MINUTES * 60
        else:
            total_with_gaps = 0
            at_capacity = False
        
        # Colors and attributes for warning
        time_color = COLOR_RED if show_warning else COLOR_CYAN
        time_attr = curses.A_BOLD | curses.A_BLINK if show_warning else 0
        
        safe_addstr(stdscr, y + 5, x, "Total Recording Time: ", curses.color_pair(COLOR_CYAN))
        safe_addstr(stdscr, y + 5, x + 22, format_duration(total_with_gaps), curses.color_pair(time_color) | time_attr)
        
        # Tape length with C-type indicator
        tape_type_indicator = ""
        if TOTAL_DURATION_MINUTES == 30:
            tape_type_indicator = " (C60)"
        elif TOTAL_DURATION_MINUTES == 45:
            tape_type_indicator = " (C90)"
        elif TOTAL_DURATION_MINUTES == 60:
            tape_type_indicator = " (C120)"
        
        safe_addstr(stdscr, y + 6, x, "Tape Length: ", curses.color_pair(COLOR_CYAN))
        tape_length_text = f"{TOTAL_DURATION_MINUTES}min{tape_type_indicator}"
        safe_addstr(stdscr, y + 6, x + 13, tape_length_text, curses.color_pair(time_color) | time_attr)
        
        if AUDIO_LATENCY > 0:
            latency_info = f"Audio latency compensation: {AUDIO_LATENCY}s"
            safe_addstr(stdscr, y + 7, x, latency_info, curses.color_pair(COLOR_YELLOW))
            return 8  # Height used
        
        return 7  # Height used (always includes timing info now)


def draw_vu_meter(stdscr, y, x, level, max_width=40, label=""):
    """
    Draw a retro VU meter with segmented blocks
    level: float from 0.0 to 1.0
    """
    # Calculate number of blocks (each block = 2 chars width + 1 space)
    block_width = 2
    block_spacing = 1
    block_unit = block_width + block_spacing
    num_blocks = max_width // block_unit
    segments = int(level * num_blocks)
    
    # Color zones: white (0-85%), red (85-100%)
    peak_zone = int(num_blocks * 0.85)
    
    safe_addstr(stdscr, y, x, f"{label:3s} [", curses.color_pair(COLOR_CYAN))
    
    current_x = x + len(f"{label:3s} [")
    for i in range(num_blocks):
        if i < segments:
            if i < peak_zone:
                char = "██"
                color = COLOR_WHITE
            else:
                char = "██"
                color = COLOR_RED
            safe_addstr(stdscr, y, current_x, char, curses.color_pair(color))
        else:
            safe_addstr(stdscr, y, current_x, "░░", curses.color_pair(COLOR_BLUE))
        current_x += block_unit
    
    # Add closing bracket
    safe_addstr(stdscr, y, current_x, "]", curses.color_pair(COLOR_CYAN))


def analyze_audio_levels(audio_segment, chunk_duration_ms=50):
    """
    Analyze audio file and pre-compute RMS levels for L/R channels
    Returns list of tuples: [(time_ms, level_l, level_r), ...]
    """
    levels = []
    duration_ms = len(audio_segment)
    
    # Split into stereo channels
    try:
        channels = audio_segment.split_to_mono()
        if len(channels) == 2:
            left_channel, right_channel = channels
        else:
            # Mono audio - duplicate for both channels
            left_channel = right_channel = channels[0]
    except:
        # Fallback for mono
        left_channel = right_channel = audio_segment
    
    # First pass: collect all RMS values to find peak
    rms_values_l = []
    rms_values_r = []
    for i in range(0, duration_ms, chunk_duration_ms):
        chunk_l = left_channel[i:i + chunk_duration_ms]
        chunk_r = right_channel[i:i + chunk_duration_ms]
        
        rms_l = chunk_l.rms if len(chunk_l) > 0 else 0
        rms_r = chunk_r.rms if len(chunk_r) > 0 else 0
        
        rms_values_l.append(rms_l)
        rms_values_r.append(rms_r)
    
    # Calculate adaptive max_rms based on 95th percentile (avoid outlier peaks)
    if rms_values_l and rms_values_r:
        sorted_l = sorted(rms_values_l)
        sorted_r = sorted(rms_values_r)
        percentile_95_idx = int(len(sorted_l) * 0.95)
        max_rms_l = sorted_l[percentile_95_idx] if percentile_95_idx < len(sorted_l) else sorted_l[-1]
        max_rms_r = sorted_r[percentile_95_idx] if percentile_95_idx < len(sorted_r) else sorted_r[-1]
        # Use the higher of the two channels, add 20% headroom
        adaptive_max_rms = max(max_rms_l, max_rms_r) * 1.2
        # Ensure reasonable minimum
        adaptive_max_rms = max(adaptive_max_rms, 1000)
    else:
        adaptive_max_rms = 8000
    
    # Second pass: normalize using adaptive max
    for i in range(0, duration_ms, chunk_duration_ms):
        idx = i // chunk_duration_ms
        rms_l = rms_values_l[idx] if idx < len(rms_values_l) else 0
        rms_r = rms_values_r[idx] if idx < len(rms_values_r) else 0
        
        # Normalize RMS to 0.0-1.0 range using adaptive max
        level_l = min(1.0, (rms_l / adaptive_max_rms) ** 0.5)
        level_r = min(1.0, (rms_r / adaptive_max_rms) ** 0.5)
        
        levels.append((i, level_l, level_r))
    
    return levels


def get_audio_level_at_time(levels, elapsed_ms):
    """
    Get interpolated audio level at specific time from pre-analyzed data
    Returns (level_l, level_r) tuple
    """
    if not levels:
        return 0.0, 0.0
    
    # Find nearest chunk
    for i, (time_ms, level_l, level_r) in enumerate(levels):
        if elapsed_ms <= time_ms:
            if i == 0:
                return level_l, level_r
            # Linear interpolation between chunks
            prev_time, prev_l, prev_r = levels[i - 1]
            time_diff = time_ms - prev_time
            if time_diff > 0:
                factor = (elapsed_ms - prev_time) / time_diff
                interp_l = prev_l + (level_l - prev_l) * factor
                interp_r = prev_r + (level_r - prev_r) * factor
                return interp_l, interp_r
            return level_l, level_r
    
    # Return last level if beyond end
    return levels[-1][1], levels[-1][2]


def normalize_lufs(audio_segment, target_lufs=-14.0):
    """
    Normalize audio to target LUFS level using pyloudnorm.
    This ensures consistent perceived loudness across tracks.
    """
    if not PYLOUDNORM_AVAILABLE:
        return audio_segment.normalize()  # Fallback to peak normalization
    
    # Convert AudioSegment to numpy array
    samples = np.array(audio_segment.get_array_of_samples())
    
    # Handle stereo
    if audio_segment.channels == 2:
        samples = samples.reshape((-1, 2))
    else:
        samples = samples.reshape((-1, 1))
    
    # Normalize to float32 [-1.0, 1.0]
    samples = samples.astype(np.float32) / (2 ** (audio_segment.sample_width * 8 - 1))
    
    # Initialize loudness meter
    meter = pyln.Meter(audio_segment.frame_rate)
    
    # Measure loudness
    loudness = meter.integrated_loudness(samples)
    
    # Normalize audio to target LUFS
    normalized_samples = pyln.normalize.loudness(samples, loudness, target_lufs)
    
    # Convert back to int16/int32
    max_val = 2 ** (audio_segment.sample_width * 8 - 1) - 1
    normalized_samples = np.clip(normalized_samples * max_val, -max_val, max_val)
    normalized_samples = normalized_samples.astype(np.int16 if audio_segment.sample_width == 2 else np.int32)
    
    # Flatten for mono or keep shape for stereo
    if audio_segment.channels == 1:
        normalized_samples = normalized_samples.flatten()
    
    # Create new AudioSegment
    normalized_audio = AudioSegment(
        normalized_samples.tobytes(),
        frame_rate=audio_segment.frame_rate,
        sample_width=audio_segment.sample_width,
        channels=audio_segment.channels
    )
    
    return normalized_audio


def calculate_loudness(audio_segment):
    """
    Calculate integrated loudness (LUFS) of an audio segment.
    Returns None if pyloudnorm is not available.
    """
    if not PYLOUDNORM_AVAILABLE:
        return None
    
    try:
        # Convert AudioSegment to numpy array
        samples = np.array(audio_segment.get_array_of_samples())
        
        # Handle stereo
        if audio_segment.channels == 2:
            samples = samples.reshape((-1, 2))
        else:
            samples = samples.reshape((-1, 1))
        
        # Normalize to float32 [-1.0, 1.0]
        samples = samples.astype(np.float32) / (2 ** (audio_segment.sample_width * 8 - 1))
        
        # Initialize loudness meter
        meter = pyln.Meter(audio_segment.frame_rate)
        
        # Measure loudness
        loudness = meter.integrated_loudness(samples)
        
        return loudness
    except Exception:
        return None


def get_ffprobe_info(filepath):
    """Return duration (seconds), codec (first audio codec found), bitrate_kbps or 'Unknown'."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error", "-show_entries",
                "format=duration","-show_streams",
                "-of", "json", filepath
            ],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False
        )
        info = json.loads(result.stdout or "{}")
        duration = None
        codec = "Unknown"
        bitrate = "Unknown"
        if "format" in info and info["format"].get("duration"):
            try:
                duration = float(info["format"]["duration"])
            except Exception:
                duration = None
        # Find first audio stream
        for s in info.get("streams", []):
            if s.get("codec_type") == "audio":
                codec = s.get("codec_name", codec)
                if s.get("bit_rate"):
                    try:
                        bitrate = int(s["bit_rate"]) // 1000
                    except Exception:
                        bitrate = "Unknown"
                break
        return duration, codec, bitrate
    except Exception:
        return None, "Unknown", "Unknown"


def list_tracks(folder):
    tracks = []
    if not os.path.isdir(folder):
        return tracks
    for file in sorted(os.listdir(folder)):
        if file.lower().endswith(('.mp3', '.wav', '.flac', '.webm', '.m4a', '.aac', '.ogg')):
            filepath = os.path.join(folder, file)
            duration, codec, quality = get_ffprobe_info(filepath)
            if duration is None:
                # skip unreadable files
                continue
            tracks.append({'name': file, 'duration': duration, 'codec': codec, 'quality': quality})
    return tracks


def normalize_tracks(tracks, folder, stdscr=None):
    """Normalize all tracks and return list of dicts with keys: name, path, audio, dBFS, loudness, method
    Skips normalization if normalized file exists.
    Supports both peak and LUFS normalization.
    """
    # Check if LUFS normalization is requested but not available
    if NORMALIZATION_METHOD == "lufs" and not PYLOUDNORM_AVAILABLE:
        if stdscr:
            stdscr.clear()
            safe_addstr(stdscr, 0, 0, "ERROR: LUFS normalization requires pyloudnorm", curses.color_pair(COLOR_RED) | curses.A_BOLD)
            safe_addstr(stdscr, 1, 0, "Install with: pip install pyloudnorm", curses.color_pair(COLOR_YELLOW))
            safe_addstr(stdscr, 2, 0, "Falling back to peak normalization...", curses.color_pair(COLOR_CYAN))
            safe_addstr(stdscr, 3, 0, "Press any key to continue.", curses.color_pair(COLOR_WHITE))
            stdscr.refresh()
            stdscr.nodelay(False)
            stdscr.getch()
            stdscr.nodelay(True)
        method = "peak"
    else:
        method = NORMALIZATION_METHOD
    
    normalized_dir = os.path.join(folder, "normalized")
    os.makedirs(normalized_dir, exist_ok=True)
    normalized_tracks = []
    
    for i, track in enumerate(tracks):
        src_path = os.path.join(folder, track['name'])
        # normalized filename includes method and target value to distinguish between normalizations
        if method == "lufs":
            norm_name = f"{track['name']}.lufs{TARGET_LUFS:+.1f}.normalized.wav"
        else:
            norm_name = f"{track['name']}.peak.normalized.wav"
        norm_path = os.path.join(normalized_dir, norm_name)
        
        if os.path.exists(norm_path):
            audio = AudioSegment.from_file(norm_path)
            if stdscr:
                stdscr.clear()
                safe_addstr(stdscr, 0, 0, f"Loading {i+1}/{len(tracks)}: {track['name']}", curses.color_pair(COLOR_YELLOW))
                safe_addstr(stdscr, 1, 0, "Analyzing waveform...", curses.color_pair(COLOR_GREEN))
                stdscr.refresh()
            audio_levels = analyze_audio_levels(audio, chunk_duration_ms=50)
            # Calculate loudness for display
            loudness = calculate_loudness(audio) if method == "lufs" and PYLOUDNORM_AVAILABLE else None
            normalized_tracks.append({
                'name': track['name'], 
                'audio': audio, 
                'path': norm_path, 
                'dBFS': audio.dBFS, 
                'loudness': loudness,
                'audio_levels': audio_levels,
                'method': method
            })
            continue
        
        # Show progress in curses (if provided)
        if stdscr:
            stdscr.clear()
            method_name = "LUFS" if method == "lufs" else "Peak"
            safe_addstr(stdscr, 0, 0, f"Normalizing ({method_name}) {i+1}/{len(tracks)}: {track['name']}", curses.color_pair(COLOR_YELLOW))
            safe_addstr(stdscr, 1, 0, "(This may take a few seconds per file)", curses.color_pair(COLOR_CYAN))
            if method == "lufs":
                safe_addstr(stdscr, 2, 0, f"Target: {TARGET_LUFS} LUFS", curses.color_pair(COLOR_MAGENTA))
            stdscr.refresh()
        
        audio = AudioSegment.from_file(src_path)
        
        # Apply normalization based on method
        if method == "lufs" and PYLOUDNORM_AVAILABLE:
            normalized_audio = normalize_lufs(audio, TARGET_LUFS)
            loudness = calculate_loudness(normalized_audio)
        else:
            normalized_audio = audio.normalize()
            loudness = None
        
        normalized_audio.export(norm_path, format="wav")
        
        if stdscr:
            safe_addstr(stdscr, 3, 0, "Analyzing waveform...", curses.color_pair(COLOR_GREEN))
            stdscr.refresh()
        
        audio_levels = analyze_audio_levels(normalized_audio, chunk_duration_ms=50)
        normalized_tracks.append({
            'name': track['name'], 
            'audio': normalized_audio, 
            'path': norm_path, 
            'dBFS': normalized_audio.dBFS,
            'loudness': loudness,
            'audio_levels': audio_levels,
            'method': method
        })
    
    return normalized_tracks


def write_deck_tracklist(normalized_tracks, track_gap, folder, counter_rate, leader_gap):
    """Generate tracklist file with timestamp to avoid overwriting"""
    lines = []
    current_time = leader_gap  # Start after leader gap
    for idx, track in enumerate(normalized_tracks):
        start_time = current_time
        duration = int(round(track['audio'].duration_seconds))
        end_time = start_time + duration
        # Use the actual counter logic for start/end
        counter_start = calculate_tape_counter(start_time)
        counter_end = calculate_tape_counter(end_time)
        lines.append(
            f"{idx+1:02d}. {track['name']}\n"
            f"    Start: {format_duration(start_time)}   End: {format_duration(end_time)}   Duration: {format_duration(duration)}\n"
            f"    Counter: {counter_start:04d} - {counter_end:04d}"
        )
        current_time = end_time + (track_gap if idx < len(normalized_tracks)-1 else 0)
    
    # Generate unique filename with timestamp and normalization info
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    norm_info = f"lufs{TARGET_LUFS:+.1f}" if NORMALIZATION_METHOD == "lufs" else "peak"
    output_filename = f"deck_tracklist_{timestamp}_{norm_info}.txt"
    output_path = os.path.join(folder, output_filename)
    
    with open(output_path, "w") as f:
        f.write("Tape Deck Tracklist Reference\n")
        f.write("="*60 + "\n")
        f.write(f"Session: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        # Tape Information
        f.write("TAPE INFORMATION:\n")
        f.write("-" * 17 + "\n")
        tape_info = get_tape_type_info(TAPE_TYPE)
        f.write(f"Tape Type: {TAPE_TYPE} - {tape_info['name']}\n")
        f.write(f"Material: {tape_info['material']}\n")
        f.write(f"Bias Setting: {tape_info['bias']}\n")
        f.write(f"Sound Character: {tape_info['sound']}\n")
        f.write(f"Physical Notes: {tape_info['notches']}\n\n")
        
        # Tape Counter Configuration
        f.write("TAPE COUNTER CONFIGURATION:\n")
        f.write("-" * 30 + "\n")
        mode_names = {
            "manual": "Manual Calibrated",
            "auto": "Auto Physics", 
            "static": "Static Linear"
        }
        f.write(f"Counter Mode: {mode_names.get(COUNTER_MODE, COUNTER_MODE)}\n")
        
        if COUNTER_MODE == "static":
            f.write(f"Counter Rate: {COUNTER_RATE} counts/second (constant)\n")
        elif COUNTER_MODE == "manual" and CALIBRATION_DATA:
            f.write(f"Calibration Source: {COUNTER_CONFIG_PATH}\n")
            deck = CALIBRATION_DATA.get('deck_model', 'Unknown')
            tape = CALIBRATION_DATA.get('tape_type', 'Unknown')
            cal_date = CALIBRATION_DATA.get('calibration_date', 'Unknown')
            f.write(f"Deck Model: {deck}\n")
            f.write(f"Tape Type: {tape}\n")
            f.write(f"Calibration Date: {cal_date}\n")
            checkpoints = CALIBRATION_DATA.get('checkpoints', [])
            if checkpoints:
                f.write(f"Calibration Points: {len(checkpoints)} measurements\n")
        elif COUNTER_MODE == "auto":
            f.write(f"Physics Simulation: Reel-based calculation\n")
            f.write(f"Base Rate: {COUNTER_RATE} counts/second (at tape midpoint)\n")
        
        f.write(f"Leader Gap: {leader_gap}s (Counter: 0000 - {calculate_tape_counter(leader_gap):04d})\n\n")
        
        # Audio Configuration
        f.write("AUDIO CONFIGURATION:\n")
        f.write("-" * 20 + "\n")
        f.write(f"Normalization: {NORMALIZATION_METHOD.upper()}")
        if NORMALIZATION_METHOD == "lufs":
            f.write(f" (target: {TARGET_LUFS:+.1f} LUFS)\n")
        else:
            f.write(" (peak normalization)\n")
        f.write(f"Track Gap: {track_gap}s between tracks\n")
        f.write(f"Tape Duration: {TOTAL_DURATION_MINUTES} minutes per side\n")
        if AUDIO_LATENCY > 0:
            f.write(f"Audio Latency Compensation: {AUDIO_LATENCY}s\n")
        f.write(f"Total Tracks: {len(normalized_tracks)}\n")
        total_duration = sum(int(round(t['audio'].duration_seconds)) for t in normalized_tracks)
        total_with_gaps = total_duration + (track_gap * (len(normalized_tracks) - 1)) + leader_gap
        f.write(f"Total Recording Time: {format_duration(total_with_gaps)} (including gaps)\n\n")
        
        # Track List
        f.write("TRACK LIST:\n")
        f.write("=" * 60 + "\n")
        for line in lines:
            f.write(line + "\n")
    
    return output_path


def show_normalization_summary(stdscr, normalized_tracks):
    """Show normalized tracks with playback preview capability"""
    current_track_idx = 0  # Currently highlighted track
    playing_track_idx = -1  # Track that is actually playing
    playing = False
    preview_proc = None
    seek_position = 0.0  # Current seek position in seconds
    play_start_time = None  # When playback started
    playback_start_time = None  # Absolute time when current track playback started
    
    def stop_preview():
        nonlocal preview_proc, playing, seek_position, play_start_time, playing_track_idx, playback_start_time
        if preview_proc is not None and preview_proc.poll() is None:
            # Calculate current position before stopping
            if play_start_time is not None:
                elapsed = time.time() - play_start_time
                seek_position += elapsed
            preview_proc.terminate()
            preview_proc = None
        playing = False
        playing_track_idx = -1
        play_start_time = None
        playback_start_time = None
    
    def start_preview(idx, start_pos=0.0):
        nonlocal preview_proc, playing, playing_track_idx, seek_position, play_start_time, playback_start_time
        stop_preview()
        playing_track_idx = idx
        seek_position = max(0.0, start_pos)
        track_path = normalized_tracks[idx]['path']
        track_duration = normalized_tracks[idx]['audio'].duration_seconds
        
        # Don't start if seek position is beyond track duration
        if seek_position >= track_duration:
            seek_position = 0.0
        
        # Start ffplay with seek position
        preview_proc = subprocess.Popen([
            "ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet",
            "-ss", str(seek_position), track_path
        ])
        playing = True
        play_start_time = time.time()
        playback_start_time = time.time()
    
    stdscr.nodelay(True)
    needs_full_redraw = True
    
    while True:
        # Check if preview finished naturally
        if playing and preview_proc is not None and preview_proc.poll() is not None:
            playing = False
            preview_proc = None
            needs_full_redraw = True
        
        if needs_full_redraw:
            stdscr.erase()
            needs_full_redraw = False
        
        max_y, max_x = stdscr.getmaxyx()
        
        # Header
        safe_addstr(stdscr, 0, 0, "═" * min(70, max_x - 2), curses.color_pair(COLOR_CYAN))
        safe_addstr(stdscr, 1, 15, "NORMALIZATION COMPLETE - PREVIEW MODE", curses.color_pair(COLOR_GREEN) | curses.A_BOLD)
        safe_addstr(stdscr, 2, 0, "═" * min(70, max_x - 2), curses.color_pair(COLOR_CYAN))
        
        # Configuration info - create track list for timing calculation
        track_list = [{'duration': track['audio'].duration_seconds} for track in normalized_tracks]
        total_duration = sum(track['duration'] for track in track_list)
        total_with_gaps = total_duration + (TRACK_GAP_SECONDS * (len(track_list) - 1)) + LEADER_GAP_SECONDS if track_list else 0
        at_capacity = total_with_gaps >= TOTAL_DURATION_MINUTES * 60
        show_warning = at_capacity  # No time-based warning in preview mode
        
        config_height = draw_config_info(stdscr, 3, 2, selected_tracks=track_list, show_warning=show_warning)
        safe_addstr(stdscr, 3 + config_height, 0, "─" * min(70, max_x - 2), curses.color_pair(COLOR_CYAN))
        
        # Playback Status Section
        playback_section_y = 3 + config_height + 2
        safe_addstr(stdscr, playback_section_y, 0, "PLAYBACK STATUS:", curses.color_pair(COLOR_MAGENTA) | curses.A_BOLD)
        
        # VU Meters at top (always visible)
        meter_y = playback_section_y + 2
        # Always clear the status lines first
        stdscr.move(meter_y, 0)
        stdscr.clrtoeol()
        stdscr.move(meter_y + 1, 0)
        stdscr.clrtoeol()
        
        if playing:
            # Calculate current playback position with latency compensation
            current_pos = seek_position
            if play_start_time is not None:
                current_pos += time.time() - play_start_time - AUDIO_LATENCY
            track_duration = normalized_tracks[playing_track_idx]['audio'].duration_seconds
            
            # Get audio levels from pre-analyzed data
            elapsed_ms = int(current_pos * 1000)
            level_l, level_r = get_audio_level_at_time(normalized_tracks[playing_track_idx]['audio_levels'], elapsed_ms)
            
            status_text = f"NOW PLAYING: {normalized_tracks[playing_track_idx]['name']}"
            position_text = f"Position: {format_duration(current_pos)} / {format_duration(track_duration)}"
            safe_addstr(stdscr, meter_y, 0, status_text, curses.color_pair(COLOR_GREEN) | curses.A_BOLD)
            safe_addstr(stdscr, meter_y + 1, 0, position_text, curses.color_pair(COLOR_YELLOW))
        else:
            level_l, level_r = 0.0, 0.0
            safe_addstr(stdscr, meter_y, 0, "Ready to preview tracks", curses.color_pair(COLOR_WHITE))
        
        safe_addstr(stdscr, meter_y + 2, 0, "─" * 78, curses.color_pair(COLOR_CYAN))
        draw_vu_meter(stdscr, meter_y + 3, 2, level_l, max_width=50, label="L")
        # dB scale between meters
        db_scale = "    -60  -40  -30  -20  -12   -6   -3    0 dB"
        safe_addstr(stdscr, meter_y + 4, 2, db_scale, curses.color_pair(COLOR_YELLOW))
        draw_vu_meter(stdscr, meter_y + 5, 2, level_r, max_width=50, label="R")
        safe_addstr(stdscr, meter_y + 6, 0, "─" * 78, curses.color_pair(COLOR_CYAN))
        
        # Track list with method indicator
        tracklist_y = meter_y + 8
        method = normalized_tracks[0].get('method', 'peak') if normalized_tracks else 'peak'
        method_label = "LUFS" if method == "lufs" else "Peak dBFS"
        safe_addstr(stdscr, tracklist_y, 0, f"TRACK LIST ({method_label} Normalization):", curses.color_pair(COLOR_YELLOW))
        
        for i, track in enumerate(normalized_tracks):
            if tracklist_y + 1 + i >= max_y - 10:  # Leave room for footer
                break
            
            is_current = i == current_track_idx
            is_playing = i == playing_track_idx and playing
            
            # Markers
            play_marker = " ♪" if is_playing else ""
            cursor_marker = "▶" if is_current else " "
            
            # Color selection
            if is_playing:
                color = COLOR_GREEN
                attr = curses.A_BOLD
            elif is_current:
                color = COLOR_YELLOW
                attr = curses.A_BOLD
            else:
                color = COLOR_CYAN
                attr = 0
            
            # Show appropriate level info
            if track.get('method') == 'lufs' and track.get('loudness') is not None:
                level_info = f"LUFS: {track['loudness']:.1f} | dBFS: {track['dBFS']:.2f}"
            else:
                level_info = f"dBFS: {track['dBFS']:.2f}"
            
            track_line = f"{cursor_marker} {i+1:02d}. {track['name']} - {level_info}{play_marker}"
            safe_addstr(stdscr, tracklist_y + 1 + i, 0, track_line, curses.color_pair(color) | attr)
        
        # Controls footer
        footer_y = tracklist_y + 2 + min(len(normalized_tracks), max_y - tracklist_y - 12)
        safe_addstr(stdscr, footer_y, 0, "─" * min(70, max_x - 2), curses.color_pair(COLOR_CYAN))
        safe_addstr(stdscr, footer_y + 1, 0, "CONTROLS:", curses.color_pair(COLOR_MAGENTA) | curses.A_BOLD)
        safe_addstr(stdscr, footer_y + 2, 0, "  ↑/↓: Navigate  ", curses.color_pair(COLOR_WHITE))
        safe_addstr(stdscr, footer_y + 2, 35, "P", curses.color_pair(COLOR_GREEN) | curses.A_BOLD)
        safe_addstr(stdscr, footer_y + 2, 36, ": Play  ", curses.color_pair(COLOR_WHITE))
        safe_addstr(stdscr, footer_y + 2, 43, "X", curses.color_pair(COLOR_RED) | curses.A_BOLD)
        safe_addstr(stdscr, footer_y + 2, 44, ": Stop", curses.color_pair(COLOR_WHITE))
        
        safe_addstr(stdscr, footer_y + 3, 0, "  ", curses.color_pair(COLOR_WHITE))
        safe_addstr(stdscr, footer_y + 3, 2, "←", curses.color_pair(COLOR_YELLOW) | curses.A_BOLD)
        safe_addstr(stdscr, footer_y + 3, 3, ": Rewind 10s  ", curses.color_pair(COLOR_WHITE))
        safe_addstr(stdscr, footer_y + 3, 17, "→", curses.color_pair(COLOR_YELLOW) | curses.A_BOLD)
        safe_addstr(stdscr, footer_y + 3, 18, ": Forward 10s", curses.color_pair(COLOR_WHITE))
        
        safe_addstr(stdscr, footer_y + 4, 0, "  ", curses.color_pair(COLOR_WHITE))
        safe_addstr(stdscr, footer_y + 4, 2, "[", curses.color_pair(COLOR_CYAN) | curses.A_BOLD)
        safe_addstr(stdscr, footer_y + 4, 3, ": Prev Track  ", curses.color_pair(COLOR_WHITE))
        safe_addstr(stdscr, footer_y + 4, 17, "]", curses.color_pair(COLOR_CYAN) | curses.A_BOLD)
        safe_addstr(stdscr, footer_y + 4, 18, ": Next Track", curses.color_pair(COLOR_WHITE))
        
        safe_addstr(stdscr, footer_y + 5, 0, "  ", curses.color_pair(COLOR_WHITE))
        safe_addstr(stdscr, footer_y + 5, 2, "ENTER", curses.color_pair(COLOR_GREEN) | curses.A_BOLD)
        safe_addstr(stdscr, footer_y + 5, 7, ": Start Recording  ", curses.color_pair(COLOR_WHITE))
        safe_addstr(stdscr, footer_y + 5, 17, "Q", curses.color_pair(COLOR_RED) | curses.A_BOLD)
        safe_addstr(stdscr, footer_y + 5, 18, ": Cancel", curses.color_pair(COLOR_WHITE))
        
        stdscr.refresh()
        
        # Handle input
        key = stdscr.getch()
        if key != -1:  # Key was pressed
            if key in (curses.KEY_ENTER, 10, 13):
                stop_preview()
                stdscr.nodelay(False)
                stdscr.clear()
                return True
            elif key in (ord('q'), ord('Q')):
                stop_preview()
                stdscr.nodelay(False)
                stdscr.clear()
                return False
            elif key in (curses.KEY_UP, ord('k')):
                # Navigate without stopping playback
                current_track_idx = (current_track_idx - 1) % len(normalized_tracks)
                needs_full_redraw = True
            elif key in (curses.KEY_DOWN, ord('j')):
                # Navigate without stopping playback
                current_track_idx = (current_track_idx + 1) % len(normalized_tracks)
                needs_full_redraw = True
            elif key in (curses.KEY_LEFT, ord('h')):
                # Rewind 10 seconds in currently playing track
                if playing:
                    # Calculate current position
                    current_pos = seek_position
                    if play_start_time is not None:
                        current_pos += time.time() - play_start_time
                    # Rewind by 10 seconds
                    new_pos = max(0.0, current_pos - 10.0)
                    start_preview(playing_track_idx, new_pos)
            elif key in (curses.KEY_RIGHT, ord('l')):
                # Forward 10 seconds in currently playing track
                if playing:
                    # Calculate current position
                    current_pos = seek_position
                    if play_start_time is not None:
                        current_pos += time.time() - play_start_time
                    # Forward by 10 seconds
                    new_pos = current_pos + 10.0
                    start_preview(playing_track_idx, new_pos)
            elif key in (ord('['), ord('{')):
                # Previous track
                stop_preview()
                seek_position = 0.0
                current_track_idx = (current_track_idx - 1) % len(normalized_tracks)
                start_preview(current_track_idx)
            elif key in (ord(']'), ord('}')):
                # Next track
                stop_preview()
                seek_position = 0.0
                current_track_idx = (current_track_idx + 1) % len(normalized_tracks)
                start_preview(current_track_idx)
            elif key in (ord('p'), ord('P')):
                if playing_track_idx == current_track_idx and playing:
                    # Pause current playback if pressing P on the same track
                    stop_preview()
                else:
                    # Stop any currently playing track and start the highlighted one
                    if playing:
                        stop_preview()
                    # Reset seek position to 0 since we want to start from beginning
                    seek_position = 0.0
                    start_preview(current_track_idx, seek_position)
            elif key in (ord('x'), ord('X')):
                stop_preview()
                seek_position = 0.0
        
        time.sleep(0.05)  # Reduce CPU usage


def prep_countdown(stdscr, seconds=10):
    """Show a cancellable countdown. Return True to proceed, False to cancel."""
    # Digital 7-segment style numbers for countdown
    big_numbers = {
        '0': [
            "███████",
            "█     █",
            "█     █",
            "█     █",
            "█     █",
            "█     █",
            "███████"
        ],
        '1': [
            "      █",
            "      █",
            "      █",
            "      █",
            "      █",
            "      █",
            "      █"
        ],
        '2': [
            "███████",
            "      █",
            "      █",
            "███████",
            "█      ",
            "█      ",
            "███████"
        ],
        '3': [
            "███████",
            "      █",
            "      █",
            "███████",
            "      █",
            "      █",
            "███████"
        ],
        '4': [
            "█     █",
            "█     █",
            "█     █",
            "███████",
            "      █",
            "      █",
            "      █"
        ],
        '5': [
            "███████",
            "█      ",
            "█      ",
            "███████",
            "      █",
            "      █",
            "███████"
        ],
        '6': [
            "███████",
            "█      ",
            "█      ",
            "███████",
            "█     █",
            "█     █",
            "███████"
        ],
        '7': [
            "███████",
            "      █",
            "      █",
            "      █",
            "      █",
            "      █",
            "      █"
        ],
        '8': [
            "███████",
            "█     █",
            "█     █",
            "███████",
            "█     █",
            "█     █",
            "███████"
        ],
        '9': [
            "███████",
            "█     █",
            "█     █",
            "███████",
            "      █",
            "      █",
            "███████"
        ]
    }
    
    stdscr.nodelay(True)
    max_y, max_x = stdscr.getmaxyx()
    
    for s in range(seconds, 0, -1):
        # Aggressive clearing
        stdscr.erase()
        stdscr.clear()
        stdscr.refresh()
        
        countdown_y = max_y // 2 - 6
        
        # Draw title
        title_str = "DECK PREP COUNTDOWN"
        title_x = max(0, (max_x - len(title_str)) // 2)
        safe_addstr(stdscr, countdown_y, title_x, title_str, curses.color_pair(COLOR_MAGENTA) | curses.A_BOLD)
        
        # Draw big number
        num_str = f"{s:02d}"
        num_lines = big_numbers[num_str[0]]
        total_width = len(num_lines[0]) * 2 + 3  # Two digits + spacing
        start_x = max(0, (max_x - total_width) // 2)
        
        for i, line in enumerate(num_lines):
            y_pos = countdown_y + 2 + i
            # Draw first digit
            safe_addstr(stdscr, y_pos, start_x, line, curses.color_pair(COLOR_YELLOW) | curses.A_BOLD | curses.A_BLINK)
            # Draw second digit
            safe_addstr(stdscr, y_pos, start_x + len(line) + 3, big_numbers[num_str[1]][i], curses.color_pair(COLOR_YELLOW) | curses.A_BOLD | curses.A_BLINK)
        
        # Important instruction
        important_str = "PRESS RECORD ON YOUR DECK WHEN COUNTDOWN HITS 0"
        important_x = max(0, (max_x - len(important_str)) // 2)
        safe_addstr(stdscr, countdown_y + 11, important_x, important_str, curses.color_pair(COLOR_RED) | curses.A_BOLD | curses.A_BLINK)
        
        # Instructions
        instr_str = "Press Q to cancel and return to menu."
        instr_x = max(0, (max_x - len(instr_str)) // 2)
        safe_addstr(stdscr, countdown_y + 13, instr_x, instr_str, curses.color_pair(COLOR_WHITE))
        stdscr.refresh()
        # allow immediate cancel
        for _ in range(10):
            key = stdscr.getch()
            if key in (ord('q'), ord('Q')):
                stdscr.nodelay(False)
                stdscr.clear()
                return False
            time.sleep(0.1)
    stdscr.nodelay(False)
    stdscr.clear()
    return True


def playback_deck_recording(stdscr, normalized_tracks, track_gap, total_duration, leader_gap):
    stdscr.clear()
    total_tracks = len(normalized_tracks)
    total_time = leader_gap + sum(int(round(t['audio'].duration_seconds)) for t in normalized_tracks) + (track_gap * (total_tracks - 1))

    # Precompute start/end/duration for display
    track_times = []
    current_time = leader_gap  # Start after leader gap
    for t in normalized_tracks:
        duration = int(round(t['audio'].duration_seconds))
        start_time_track = current_time
        end_time_track = start_time_track + duration
        track_times.append((start_time_track, end_time_track, duration))
        current_time = end_time_track + track_gap

    avg_dbfs = sum(t['dBFS'] for t in normalized_tracks) / len(normalized_tracks) if normalized_tracks else 0

    # Start timing - tape deck "record" button pressed after prep countdown
    overall_start_time = time.time()

    # Leader gap countdown before first track
    if leader_gap > 0:
        stdscr.nodelay(True)
        leader_start_time = time.time()
        quit_to_menu = False
        first_leader_draw = True
        last_leader_counter = -1
        while True:
            elapsed = time.time() - overall_start_time
            leader_elapsed = time.time() - leader_start_time
            current_counter = calculate_tape_counter(elapsed)
            
            if leader_elapsed >= leader_gap:
                break
            
            # Only redraw if counter changed
            if current_counter == last_leader_counter and not first_leader_draw:
                time.sleep(0.05)
                key = stdscr.getch()
                if key in (ord('q'), ord('Q')):
                    quit_to_menu = True
                    break
                continue
            
            last_leader_counter = current_counter
            if first_leader_draw:
                stdscr.erase()
                first_leader_draw = False
            
            # Draw large tape counter
            max_y, max_x = stdscr.getmaxyx()
            counter_str = f"{current_counter:04d}"
            
            # Digital 7-segment style numbers for tape counter
            big_numbers = {
                '0': ["███████", "█     █", "█     █", "█     █", "█     █", "█     █", "███████"],
                '1': ["      █", "      █", "      █", "      █", "      █", "      █", "      █"],
                '2': ["███████", "      █", "      █", "███████", "█      ", "█      ", "███████"],
                '3': ["███████", "      █", "      █", "███████", "      █", "      █", "███████"],
                '4': ["█     █", "█     █", "█     █", "███████", "      █", "      █", "      █"],
                '5': ["███████", "█      ", "█      ", "███████", "      █", "      █", "███████"],
                '6': ["███████", "█      ", "█      ", "███████", "█     █", "█     █", "███████"],
                '7': ["███████", "      █", "      █", "      █", "      █", "      █", "      █"],
                '8': ["███████", "█     █", "█     █", "███████", "█     █", "█     █", "███████"],
                '9': ["███████", "█     █", "█     █", "███████", "      █", "      █", "███████"]
            }
            
            # Draw title first
            title_y = 0
            safe_addstr(stdscr, title_y, 0, "╔" + "═" * 78 + "╗", curses.color_pair(COLOR_CYAN))
            safe_addstr(stdscr, title_y + 1, 28, "LEADER GAP - STAND BY", curses.color_pair(COLOR_MAGENTA) | curses.A_BOLD)
            safe_addstr(stdscr, title_y + 2, 0, "╚" + "═" * 78 + "╝", curses.color_pair(COLOR_CYAN))
            
            # Compact configuration info
            draw_config_info(stdscr, title_y + 3, 2, compact=True)
            
            # Draw tape counter below title
            counter_y = title_y + 4
            
            # Start from left with consistent margin
            digit_width = 7
            spacing = 2
            start_x = 2
            
            # Draw each digit
            for line_idx in range(7):
                current_x = start_x
                for digit in counter_str:
                    line = big_numbers[digit][line_idx]
                    safe_addstr(stdscr, counter_y + 2 + line_idx, current_x, line, curses.color_pair(COLOR_GREEN) | curses.A_BOLD)
                    current_x += digit_width + spacing
            
            # Counter label centered below digits
            label_y = counter_y + 10
            total_counter_width = (digit_width * 4) + (spacing * 3)
            label_text = "[TAPE COUNTER]"
            # Center the label within the counter width
            padding = (total_counter_width - len(label_text)) // 2
            safe_addstr(stdscr, label_y, start_x + padding, label_text, curses.color_pair(COLOR_MAGENTA) | curses.A_BOLD)
            
            # Messages below counter label
            msg_y = counter_y + 12
            leader_remaining = int(leader_gap - leader_elapsed)
            safe_addstr(stdscr, msg_y, 10, f"Waiting for leader tape to pass... {leader_remaining}s", 
                         curses.color_pair(COLOR_YELLOW) | curses.A_BLINK)
            safe_addstr(stdscr, msg_y + 2, 10, f"First track will start at counter {calculate_tape_counter(leader_gap):04d}", 
                         curses.color_pair(COLOR_CYAN))
            
            footer_y = msg_y + 5
            safe_addstr(stdscr, footer_y, 0, "Press ", curses.color_pair(COLOR_WHITE))
            safe_addstr(stdscr, footer_y, 6, "Q", curses.color_pair(COLOR_RED) | curses.A_BOLD)
            safe_addstr(stdscr, footer_y, 7, " to quit to main menu.", curses.color_pair(COLOR_WHITE))
            
            stdscr.refresh()
        
        stdscr.nodelay(False)
        if quit_to_menu:
            stdscr.clear()
            return

    for idx, track in enumerate(normalized_tracks):
        track_duration = track_times[idx][2]
        track_start_time = time.time()
        # launch ffplay for each track
        proc = subprocess.Popen(["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", track['path']])
        stdscr.nodelay(True)
        quit_to_menu = False
        last_counter = -1
        last_progress = -1
        first_draw = True
        
        while True:
            now = time.time()
            elapsed = now - overall_start_time
            track_elapsed = now - track_start_time
            current_counter = calculate_tape_counter(elapsed)
            current_progress = int(60 * (track_elapsed / max(1, track_duration)))
            
            # Check if we need to redraw static elements
            counter_changed = current_counter != last_counter
            progress_changed = current_progress != last_progress
            
            # Only redraw on first draw or when values change
            if first_draw or counter_changed or progress_changed:
                if first_draw:
                    stdscr.erase()
                    first_draw = False
            
                # Draw large tape counter at top
                counter_str = f"{current_counter:04d}"
                
                # Use big_numbers dictionary
                big_numbers = {
                    '0': ["███████", "█     █", "█     █", "█     █", "█     █", "█     █", "███████"],
                    '1': ["      █", "      █", "      █", "      █", "      █", "      █", "      █"],
                    '2': ["███████", "      █", "      █", "███████", "█      ", "█      ", "███████"],
                    '3': ["███████", "      █", "      █", "███████", "      █", "      █", "███████"],
                    '4': ["█     █", "█     █", "█     █", "███████", "      █", "      █", "      █"],
                    '5': ["███████", "█      ", "█      ", "███████", "      █", "      █", "███████"],
                    '6': ["███████", "█      ", "█      ", "███████", "█     █", "█     █", "███████"],
                    '7': ["███████", "      █", "      █", "      █", "      █", "      █", "      █"],
                    '8': ["███████", "█     █", "█     █", "███████", "█     █", "█     █", "███████"],
                    '9': ["███████", "█     █", "█     █", "███████", "      █", "      █", "███████"]
                }
                
                # Draw title first
                title_y = 0
                safe_addstr(stdscr, title_y, 0, "╔" + "═" * 78 + "╗", curses.color_pair(COLOR_CYAN))
                safe_addstr(stdscr, title_y + 1, 30, "DECK RECORDING MODE", curses.color_pair(COLOR_MAGENTA) | curses.A_BOLD)
                safe_addstr(stdscr, title_y + 2, 0, "╚" + "═" * 78 + "╝", curses.color_pair(COLOR_CYAN))
                
                # Compact configuration info
                draw_config_info(stdscr, title_y + 3, 2, compact=True)
                
                # Draw tape counter below title
                counter_y = title_y + 4
                
                # Start from left with consistent margin
                digit_width = 7
                spacing = 2
                start_x = 2
                
                # Draw each digit
                for line_idx in range(7):
                    current_x = start_x
                    for digit in counter_str:
                        line = big_numbers[digit][line_idx]
                        safe_addstr(stdscr, counter_y + 2 + line_idx, current_x, line, curses.color_pair(COLOR_GREEN) | curses.A_BOLD)
                        current_x += digit_width + spacing
                
                # Counter label centered below digits
                label_y = counter_y + 10
                total_counter_width = (digit_width * 4) + (spacing * 3)
                label_text = "[TAPE COUNTER]"
                # Center the label within the counter width
                padding = (total_counter_width - len(label_text)) // 2
                safe_addstr(stdscr, label_y, start_x + padding, label_text, curses.color_pair(COLOR_MAGENTA) | curses.A_BOLD)
                
                safe_addstr(stdscr, title_y + 4, 2, f"AVG dBFS: {avg_dbfs:+.2f}", curses.color_pair(COLOR_CYAN))
                safe_addstr(stdscr, title_y + 4, 25, f"TRACK GAP: {track_gap}s", curses.color_pair(COLOR_CYAN))
            
            # VU Meters - real audio levels from waveform analysis (update every frame for smooth animation)
            title_y = 4
            meter_y = counter_y + 12
            # Apply latency compensation to delay meters and match audio output
            elapsed_ms = int((track_elapsed - AUDIO_LATENCY) * 1000)
            level_l, level_r = get_audio_level_at_time(track['audio_levels'], elapsed_ms)
            safe_addstr(stdscr, meter_y, 0, "─" * 78, curses.color_pair(COLOR_CYAN))
            draw_vu_meter(stdscr, meter_y + 1, 2, level_l, max_width=50, label="L")
            # dB scale between meters
            db_scale = "    -60  -40  -30  -20  -12   -6   -3    0 dB"
            safe_addstr(stdscr, meter_y + 2, 2, db_scale, curses.color_pair(COLOR_YELLOW))
            draw_vu_meter(stdscr, meter_y + 3, 2, level_r, max_width=50, label="R")
            safe_addstr(stdscr, meter_y + 4, 0, "─" * 78, curses.color_pair(COLOR_CYAN))
            
            # NOW PLAYING section and track list (only update when counter/progress changes)
            if counter_changed or progress_changed or first_draw:
                play_y = meter_y + 6
                safe_addstr(stdscr, play_y, 0, "NOW PLAYING: ", curses.color_pair(COLOR_MAGENTA) | curses.A_BOLD)
                safe_addstr(stdscr, play_y, 13, f"{os.path.basename(track['path'])}", curses.color_pair(COLOR_YELLOW))
                # Progress bar with duration time on the right
                bar_len = 60
                progress = min(int(bar_len * (track_elapsed / max(1, track_duration))), bar_len)
                progress_line = f"[{'█' * progress}{'░' * (bar_len - progress)}] [{format_duration(track_elapsed)}/{format_duration(track_duration)}]"
                safe_addstr(stdscr, play_y + 1, 0, "[", curses.color_pair(COLOR_CYAN))
                safe_addstr(stdscr, play_y + 1, 1, "█" * progress, curses.color_pair(COLOR_GREEN))
                safe_addstr(stdscr, play_y + 1, 1 + progress, "░" * (bar_len - progress), curses.color_pair(COLOR_BLUE))
                safe_addstr(stdscr, play_y + 1, 1 + bar_len, "]", curses.color_pair(COLOR_CYAN))
                safe_addstr(stdscr, play_y + 1, 2 + bar_len, f" [{format_duration(track_elapsed)}/{format_duration(track_duration)}]", curses.color_pair(COLOR_GREEN))
                
                # Track list
                tracks_y = play_y + 3
                safe_addstr(stdscr, tracks_y, 0, "[TRACKS]:", curses.color_pair(COLOR_MAGENTA) | curses.A_BOLD)
                for i, t in enumerate(normalized_tracks):
                    wav_name = os.path.basename(t['path'])
                    start_time_track, end_time_track, duration = track_times[i]
                    counter_start = calculate_tape_counter(start_time_track)
                    counter_end = calculate_tape_counter(end_time_track)
                    is_current = i == idx
                    marker = "▶▶" if is_current else "  "
                    color = COLOR_GREEN if is_current else COLOR_CYAN
                    line_y = tracks_y + 1 + (i * 3)
                    safe_addstr(stdscr, line_y, 0, marker, curses.color_pair(COLOR_GREEN) | curses.A_BOLD if is_current else curses.color_pair(COLOR_WHITE))
                    safe_addstr(stdscr, line_y, 3, f" {i+1:02d}. ", curses.color_pair(color))
                    safe_addstr(stdscr, line_y, 9, f"{wav_name}", curses.color_pair(COLOR_YELLOW) if is_current else curses.color_pair(COLOR_WHITE))
                    safe_addstr(stdscr, line_y + 1, 5, f"Start: {format_duration(start_time_track)}   End: {format_duration(end_time_track)}   Duration: {format_duration(duration)}", curses.color_pair(color))
                    counter_line = f"Counter: {counter_start:04d} - {counter_end:04d}"
                    safe_addstr(stdscr, line_y + 2, 5, counter_line, curses.color_pair(color))
                    safe_addstr(stdscr, line_y + 2, 14, f"{counter_start:04d}", curses.color_pair(COLOR_YELLOW))
                    safe_addstr(stdscr, line_y + 2, 21, f"{counter_end:04d}", curses.color_pair(COLOR_YELLOW))
                
                # Footer (with boundary checking)
                footer_y = tracks_y + 1 + (len(normalized_tracks) * 3) + 1
                max_y, max_x = stdscr.getmaxyx()
                if footer_y < max_y - 5:
                    safe_addstr(stdscr, footer_y, 0, "─" * min(70, max_x - 2), curses.color_pair(COLOR_CYAN))
                    safe_addstr(stdscr, footer_y + 1, 0, f"TOTAL RECORDING TIME: {format_duration(elapsed)}/{format_duration(total_time)}", curses.color_pair(COLOR_YELLOW))
                    # Total progress bar
                    bar_len = 60
                    total_progress = min(int(bar_len * (elapsed / max(1, total_time))), bar_len)
                    safe_addstr(stdscr, footer_y + 2,  0, "[", curses.color_pair(COLOR_CYAN))
                    safe_addstr(stdscr, footer_y + 2, 1, "█" * total_progress, curses.color_pair(COLOR_YELLOW))
                    safe_addstr(stdscr, footer_y + 2, 1 + total_progress, "░" * (bar_len - total_progress), curses.color_pair(COLOR_BLUE))
                    safe_addstr(stdscr, footer_y + 2, 1 + bar_len, "]", curses.color_pair(COLOR_CYAN))
                    safe_addstr(stdscr, footer_y + 4, 0, "Press ", curses.color_pair(COLOR_WHITE))
                    safe_addstr(stdscr, footer_y + 4, 6, "Q", curses.color_pair(COLOR_RED) | curses.A_BOLD)
                    safe_addstr(stdscr, footer_y + 4, 7, " to quit to main menu.", curses.color_pair(COLOR_WHITE))
            
            stdscr.refresh()
            
            last_counter = current_counter
            last_progress = current_progress
            
            key = stdscr.getch()
            if key in (ord('q'), ord('Q')):
                if proc.poll() is None:
                    proc.terminate()
                quit_to_menu = True
                break
            if proc.poll() is not None:
                break
            time.sleep(0.05)  # Reduced from 0.1 to make VU meters more responsive
        stdscr.nodelay(False)
        if quit_to_menu:
            stdscr.clear()
            return
        # Track gap countdown
        if idx < total_tracks - 1:
            stdscr.nodelay(True)
            for gap_sec in range(track_gap, 0, -1):
                max_y, max_x = stdscr.getmaxyx()
                gap_y = max_y - 3 if max_y > 5 else 0
                safe_addstr(stdscr, gap_y, 0, f"Next track in {gap_sec} seconds... (Press Q to quit to main menu)", curses.color_pair(COLOR_YELLOW))
                stdscr.refresh()
                key = stdscr.getch()
                if key in (ord('q'), ord('Q')):
                    stdscr.nodelay(False)
                    stdscr.clear()
                    return
                time.sleep(1)
            stdscr.nodelay(False)
    max_y, max_x = stdscr.getmaxyx()
    final_y = max_y - 2 if max_y > 3 else 0
    safe_addstr(stdscr, final_y, 0, "Recording complete! Press any key to exit.", curses.color_pair(COLOR_GREEN) | curses.A_BOLD)
    stdscr.refresh()
    stdscr.getch()
    stdscr.clear()
    stdscr.clear()


def play_audio(path, seek_pos=0.0):
    """Start ffplay for preview with optional seek position. Uses global ffplay_proc so main menu can stop it."""
    global ffplay_proc
    # stop existing if running
    try:
        if ffplay_proc is not None and ffplay_proc.poll() is None:
            ffplay_proc.terminate()
    except Exception:
        pass
    
    if seek_pos > 0:
        ffplay_proc = subprocess.Popen([
            "ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet",
            "-ss", str(seek_pos), path
        ])
    else:
        ffplay_proc = subprocess.Popen(["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path])


def main_menu(folder):
    tracks = list_tracks(folder)
    if not tracks:
        print("No audio tracks found in the folder!")
        input("Press Enter to exit...")
        return
    selected_tracks = []
    total_selected_duration = 0.0
    current_index = 0
    playing = False  # Ensure playback state is always defined
    paused = False

    def draw_menu(stdscr):
        nonlocal current_index, selected_tracks, total_selected_duration, paused
        global ffplay_proc
        init_colors()
        curses.curs_set(0)
        stdscr.nodelay(True)  # Non-blocking input for real-time updates
        previewing_index = -1  # Track which file is being previewed
        seek_position = 0.0  # Current seek position in seconds
        play_start_time = None  # When playback started
        preview_audio_levels = None  # Pre-analyzed audio levels for preview
        preview_audio_segment = None  # AudioSegment for current preview
        playing = False  # Playback state
        
        def stop_preview():
            nonlocal previewing_index, playing, seek_position, play_start_time
            global ffplay_proc
            if ffplay_proc is not None and ffplay_proc.poll() is None:
                ffplay_proc.terminate()
                ffplay_proc = None
            playing = False
            previewing_index = -1
            play_start_time = None
            seek_position = 0.0
        
        def start_preview(idx, start_pos=0.0):
            nonlocal previewing_index, playing, seek_position, play_start_time, preview_audio_levels, preview_audio_segment
            stop_preview()
            previewing_index = idx
            seek_position = max(0.0, start_pos)
            track_path = os.path.join(folder, tracks[idx]['name'])
            
            # Start ffplay with seek position
            play_audio(track_path, seek_position)
            playing = True
            play_start_time = time.time()
            
            # Load audio levels for VU meter display
            try:
                audio_segment = AudioSegment.from_file(track_path)
                preview_audio_levels = analyze_audio_levels(audio_segment)
                preview_audio_segment = audio_segment
            except Exception:
                preview_audio_levels = None
                preview_audio_segment = None
        
        needs_full_redraw = True
        last_scroll_offset = -1  # Track scroll position changes
        capacity_warning_until = 0  # Timestamp until which to show capacity warning
        
        while True:
            max_y, max_x = stdscr.getmaxyx()
            
            if needs_full_redraw:
                stdscr.erase()
                needs_full_redraw = False
            
            # Only draw cassette if there's enough room
            if max_y > 30:
                draw_cassette_art(stdscr, 1, 12)
                header_y = 18
            else:
                header_y = 0
            
            safe_addstr(stdscr, header_y, 0, "═" * min(70, max_x - 2), curses.color_pair(COLOR_CYAN))
            safe_addstr(stdscr, header_y + 1, 20, "TAPE DECK PREP MENU", curses.color_pair(COLOR_MAGENTA) | curses.A_BOLD)
            safe_addstr(stdscr, header_y + 2, 0, "═" * min(70, max_x - 2), curses.color_pair(COLOR_CYAN))
            
            # Calculate capacity warning before displaying config
            at_capacity = total_selected_duration >= TOTAL_DURATION_MINUTES * 60
            show_warning = at_capacity or time.time() < capacity_warning_until
            
            # Configuration info
            config_height = draw_config_info(stdscr, header_y + 3, 2, selected_tracks=selected_tracks, show_warning=show_warning)
            safe_addstr(stdscr, header_y + 3 + config_height, 0, "─" * min(70, max_x - 2), curses.color_pair(COLOR_CYAN))
            
            # Playback Status Section
            playback_section_y = header_y + 3 + config_height + 2
            safe_addstr(stdscr, playback_section_y, 0, "PLAYBACK STATUS:", curses.color_pair(COLOR_MAGENTA) | curses.A_BOLD)
            
            # VU Meters at top (always visible)
            meter_y = playback_section_y + 2
            # Always clear the playing status line first
            stdscr.move(meter_y, 0)
            stdscr.clrtoeol()
            
            # Clear the second status line as well
            stdscr.move(meter_y + 1, 0)
            stdscr.clrtoeol()
            
            if previewing_index >= 0 and play_start_time is not None:
                current_pos = seek_position + (time.time() - play_start_time) - AUDIO_LATENCY
                track_duration = tracks[previewing_index]['duration']
                
                status_text = f"NOW PLAYING: {tracks[previewing_index]['name']}"
                position_text = f"Position: {format_duration(current_pos)} / {format_duration(track_duration)}"
                safe_addstr(stdscr, meter_y, 0, status_text, curses.color_pair(COLOR_GREEN) | curses.A_BOLD)
                safe_addstr(stdscr, meter_y + 1, 0, position_text, curses.color_pair(COLOR_YELLOW))
                
                # Get audio levels if available
                if preview_audio_levels is not None:
                    elapsed_ms = int(current_pos * 1000)
                    level_l, level_r = get_audio_level_at_time(preview_audio_levels, elapsed_ms)
                else:
                    level_l, level_r = 0.0, 0.0
            else:
                level_l, level_r = 0.0, 0.0
                safe_addstr(stdscr, meter_y, 0, "Ready to preview tracks", curses.color_pair(COLOR_WHITE))
            
            safe_addstr(stdscr, meter_y + 2, 0, "─" * 78, curses.color_pair(COLOR_CYAN))
            draw_vu_meter(stdscr, meter_y + 3, 2, level_l, max_width=50, label="L")
            # dB scale between meters
            db_scale = "    -60  -40  -30  -20  -12   -6   -3    0 dB"
            safe_addstr(stdscr, meter_y + 4, 2, db_scale, curses.color_pair(COLOR_YELLOW))
            draw_vu_meter(stdscr, meter_y + 5, 2, level_r, max_width=50, label="R")
            safe_addstr(stdscr, meter_y + 6, 0, "─" * 78, curses.color_pair(COLOR_CYAN))
            
            tracklist_y = meter_y + 8
            safe_addstr(stdscr, tracklist_y, 0, f"TRACKS IN FOLDER ({folder}):", curses.color_pair(COLOR_YELLOW) | curses.A_BOLD)
            
            # Check if preview is still playing
            if previewing_index >= 0:
                if ffplay_proc is None or ffplay_proc.poll() is not None:
                    previewing_index = -1  # Preview ended
                    play_start_time = None
            
            # Scrollable track list with fixed visible window
            track_start_y = tracklist_y + 1
            max_visible_tracks = 10  # Fixed number of visible tracks
            
            # Calculate scroll offset to keep current track visible
            scroll_offset = max(0, current_index - max_visible_tracks + 1)
            if current_index < scroll_offset:
                scroll_offset = current_index
            
            # Clear entire content area if scroll position changed or on full redraw
            if scroll_offset != last_scroll_offset or needs_full_redraw:
                # Clear from track list all the way to bottom (tracks + selected + footer + controls)
                for clear_y in range(track_start_y, max_y - 1):
                    try:
                        stdscr.move(clear_y, 0)
                        stdscr.clrtoeol()
                    except:
                        pass
                last_scroll_offset = scroll_offset
            
            # Show scroll indicators
            if scroll_offset > 0:
                safe_addstr(stdscr, track_start_y, 0, "  ↑ More tracks above...", curses.color_pair(COLOR_CYAN) | curses.A_DIM)
                track_display_start = track_start_y + 1
            else:
                track_display_start = track_start_y
            
            # Display visible tracks
            visible_end = min(scroll_offset + max_visible_tracks, len(tracks))
            for idx, i in enumerate(range(scroll_offset, visible_end)):
                track = tracks[i]
                track_y = track_display_start + idx
                
                selected_marker = "●" if track in selected_tracks else "○"
                highlight_marker = "▶" if i == current_index else " "
                preview_marker = " ♪" if i == previewing_index else ""
                duration_str = format_duration(track['duration'])
                is_current = i == current_index
                is_selected = track in selected_tracks
                is_previewing = i == previewing_index
                
                # Use green for previewing track
                if is_previewing:
                    text_color = COLOR_GREEN
                    attr = curses.A_BOLD
                elif is_current:
                    text_color = COLOR_YELLOW
                    attr = curses.A_BOLD
                elif is_selected:
                    text_color = COLOR_CYAN
                    attr = 0
                else:
                    text_color = COLOR_WHITE
                    attr = 0
                
                # Build track line with proper truncation
                prefix = f"{highlight_marker} {selected_marker} {i + 1:02d}. "
                suffix = f" - {duration_str}{preview_marker}"
                
                # Calculate available space for filename
                available_space = max_x - len(prefix) - len(suffix) - 2  # -2 for safety margin
                track_name = track['name']
                if len(track_name) > available_space and available_space > 10:
                    track_name = track_name[:available_space - 3] + "..."
                
                track_line = f"{prefix}{track_name}{suffix}"
                
                # Ensure entire line fits in screen width
                if len(track_line) > max_x - 2:
                    track_line = track_line[:max_x - 5] + "..."
                
                safe_addstr(stdscr, track_y, 0, track_line, curses.color_pair(text_color) | attr)
            
            # Show bottom scroll indicator
            if visible_end < len(tracks):
                safe_addstr(stdscr, track_display_start + (visible_end - scroll_offset), 0, 
                           f"  ↓ {len(tracks) - visible_end} more tracks below...", 
                           curses.color_pair(COLOR_CYAN) | curses.A_DIM)
                sel_y = track_display_start + (visible_end - scroll_offset) + 2
            else:
                sel_y = track_display_start + (visible_end - scroll_offset) + 1
            if sel_y < max_y - 8:
                safe_addstr(stdscr, sel_y, 0, "─" * min(70, max_x - 2), curses.color_pair(COLOR_CYAN))
                safe_addstr(stdscr, sel_y + 1, 0, f"SELECTED TRACKS ({len(selected_tracks)}):", curses.color_pair(COLOR_GREEN) | curses.A_BOLD)
                
                # List selected tracks in order
                current_y = sel_y + 2
                for i, track in enumerate(selected_tracks):
                    if current_y >= max_y - 6:  # Leave room for footer
                        break
                    duration_str = format_duration(track['duration'])
                    track_info = f"  {i + 1:02d}. {track['name']} - {duration_str}"
                    safe_addstr(stdscr, current_y, 0, track_info, curses.color_pair(COLOR_YELLOW))
                    current_y += 1
                
                # Footer info with highlighting if at/over capacity or warning active
                footer_y = current_y + 1
                total_duration_str = format_duration(total_selected_duration)
                tape_length_str = format_duration(TOTAL_DURATION_MINUTES * 60)
                
                # Check if at or over capacity, or if warning is active
                at_capacity = total_selected_duration >= TOTAL_DURATION_MINUTES * 60
                show_warning = at_capacity or time.time() < capacity_warning_until
                
                safe_addstr(stdscr, footer_y, 0, "─" * min(70, max_x - 2), curses.color_pair(COLOR_CYAN))
                
                # Controls
                controls_y = footer_y + 2
                safe_addstr(stdscr, controls_y, 0, "CONTROLS:", curses.color_pair(COLOR_MAGENTA) | curses.A_BOLD)
                safe_addstr(stdscr, controls_y + 2, 0, "  ↑/↓:Nav  Space:Select  C:Clear  ", curses.color_pair(COLOR_WHITE))
                safe_addstr(stdscr, controls_y + 2, 35, "P", curses.color_pair(COLOR_GREEN) | curses.A_BOLD)
                safe_addstr(stdscr, controls_y + 2, 36, ":Play  ", curses.color_pair(COLOR_WHITE))
                safe_addstr(stdscr, controls_y + 2, 43, "X", curses.color_pair(COLOR_RED) | curses.A_BOLD)
                safe_addstr(stdscr, controls_y + 2, 44, ":Stop", curses.color_pair(COLOR_WHITE))
                
                safe_addstr(stdscr, controls_y + 3, 0, "  ", curses.color_pair(COLOR_WHITE))
                safe_addstr(stdscr, controls_y + 3, 2, "←", curses.color_pair(COLOR_YELLOW) | curses.A_BOLD)
                safe_addstr(stdscr, controls_y + 3, 3, ":Rewind 10s  ", curses.color_pair(COLOR_WHITE))
                safe_addstr(stdscr, controls_y + 3, 17, "→", curses.color_pair(COLOR_YELLOW) | curses.A_BOLD)
                safe_addstr(stdscr, controls_y + 3, 18, ":Forward 10s", curses.color_pair(COLOR_WHITE))
                
                safe_addstr(stdscr, controls_y + 4, 0, "  ", curses.color_pair(COLOR_WHITE))
                safe_addstr(stdscr, controls_y + 4, 2, "[", curses.color_pair(COLOR_CYAN) | curses.A_BOLD)
                safe_addstr(stdscr, controls_y + 4, 3, ":Prev Track  ", curses.color_pair(COLOR_WHITE))
                safe_addstr(stdscr, controls_y + 4, 17, "]", curses.color_pair(COLOR_CYAN) | curses.A_BOLD)
                safe_addstr(stdscr, controls_y + 4, 18, ":Next Track", curses.color_pair(COLOR_WHITE))
                
                safe_addstr(stdscr, controls_y + 5, 0, "  ", curses.color_pair(COLOR_WHITE))
                safe_addstr(stdscr, controls_y + 5, 2, "ENTER", curses.color_pair(COLOR_GREEN) | curses.A_BOLD)
                safe_addstr(stdscr, controls_y + 5, 7, ":Record  ", curses.color_pair(COLOR_WHITE))
                safe_addstr(stdscr, controls_y + 5, 17, "Q", curses.color_pair(COLOR_RED) | curses.A_BOLD)
                safe_addstr(stdscr, controls_y + 5, 18, ":Quit", curses.color_pair(COLOR_WHITE))
            stdscr.refresh()

            key = stdscr.getch()
            if key != -1:  # Key was pressed
                if key in (ord('q'), ord('Q')):
                    # Stop ffplay if running
                    if ffplay_proc is not None and ffplay_proc.poll() is None:
                        ffplay_proc.terminate()
                        ffplay_proc = None
                    break
                elif key in (curses.KEY_UP, ord('k')):
                    # Navigate without stopping playback
                    if current_index > 0:
                        current_index -= 1
                elif key in (curses.KEY_DOWN, ord('j')):
                    # Navigate without stopping playback
                    if current_index < len(tracks) - 1:
                        current_index += 1
                elif key == ord(' '):
                    track = tracks[current_index]
                    if track in selected_tracks:
                        selected_tracks.remove(track)
                        total_selected_duration -= track['duration']
                        needs_full_redraw = True
                    else:
                        if total_selected_duration + track['duration'] + TRACK_GAP_SECONDS <= TOTAL_DURATION_MINUTES * 60:
                            selected_tracks.append(track)
                            total_selected_duration += track['duration']
                            needs_full_redraw = True
                        else:
                            # Track exceeded capacity - show warning for 2 seconds
                            capacity_warning_until = time.time() + 2.0
                elif key in (ord('c'), ord('C')):
                    # Clear all selected tracks
                    if selected_tracks:
                        selected_tracks.clear()
                        total_selected_duration = 0
                        needs_full_redraw = True
                elif key in (ord('p'), ord('P')):
                    if previewing_index == current_index and playing:
                        # Pause current playback if pressing P on the same track
                        stop_preview()
                    else:
                        # Stop any currently playing track and start the highlighted one
                        if playing:
                            stop_preview()
                        # Reset seek position to 0 since we want to start from beginning
                        seek_position = 0.0
                        start_preview(current_index, seek_position)
                elif key in (ord('x'), ord('X')):
                    stop_preview()
                    seek_position = 0.0
                elif key in (curses.KEY_LEFT, ord('h')):
                    # Rewind 10 seconds in current track
                    if previewing_index >= 0 and ffplay_proc is not None and ffplay_proc.poll() is None:
                        # Calculate current position
                        current_pos = seek_position
                        if play_start_time is not None:
                            current_pos += time.time() - play_start_time
                        # Rewind by 10 seconds
                        new_pos = max(0.0, current_pos - 10.0)
                        seek_position = new_pos
                        track_path = os.path.join(folder, tracks[previewing_index]['name'])
                        play_audio(track_path, new_pos)
                        play_start_time = time.time()
                elif key in (curses.KEY_RIGHT, ord('l')):
                    # Forward 10 seconds in current track
                    if previewing_index >= 0 and ffplay_proc is not None and ffplay_proc.poll() is None:
                        # Calculate current position
                        current_pos = seek_position
                        if play_start_time is not None:
                            current_pos += time.time() - play_start_time
                        # Forward by 10 seconds
                        new_pos = current_pos + 10.0
                        seek_position = new_pos
                        track_path = os.path.join(folder, tracks[previewing_index]['name'])
                        play_audio(track_path, new_pos)
                        play_start_time = time.time()
                elif key in (ord('['), ord('{')):
                    # Previous track
                    if current_index > 0:
                        if ffplay_proc is not None and ffplay_proc.poll() is None:
                            ffplay_proc.terminate()
                            ffplay_proc = None
                        current_index -= 1
                        seek_position = 0.0
                        track_path = os.path.join(folder, tracks[current_index]['name'])
                        # Load and analyze audio for VU meters
                        try:
                            preview_audio_segment = AudioSegment.from_file(track_path)
                            preview_audio_levels = analyze_audio_levels(preview_audio_segment, chunk_duration_ms=50)
                        except:
                            preview_audio_segment = None
                            preview_audio_levels = None
                        play_audio(track_path)
                        previewing_index = current_index
                        play_start_time = time.time()
                elif key in (ord(']'), ord('}')):
                    # Next track
                    if current_index < len(tracks) - 1:
                        if ffplay_proc is not None and ffplay_proc.poll() is None:
                            ffplay_proc.terminate()
                            ffplay_proc = None
                        current_index += 1
                        seek_position = 0.0
                        track_path = os.path.join(folder, tracks[current_index]['name'])
                        # Load and analyze audio for VU meters
                        try:
                            preview_audio_segment = AudioSegment.from_file(track_path)
                            preview_audio_levels = analyze_audio_levels(preview_audio_segment, chunk_duration_ms=50)
                        except:
                            preview_audio_segment = None
                            preview_audio_levels = None
                        play_audio(track_path)
                        previewing_index = current_index
                        play_start_time = time.time()
                elif key in (curses.KEY_ENTER, 10, 13):
                    stdscr.nodelay(False)
                    # Stop ffplay if running before normalization
                    if ffplay_proc is not None and ffplay_proc.poll() is None:
                        ffplay_proc.terminate()
                        ffplay_proc = None
                    if not selected_tracks:
                        stdscr.nodelay(True)
                        continue
                    # Normalize (skips existing normalized wavs)
                    normalized_tracks = normalize_tracks(selected_tracks, folder, stdscr)
                    proceed = show_normalization_summary(stdscr, normalized_tracks)
                    if not proceed:
                        stdscr.nodelay(True)
                        continue
                    # Write tracklist file with unique timestamp
                    output_txt = write_deck_tracklist(normalized_tracks, TRACK_GAP_SECONDS, folder, COUNTER_RATE, LEADER_GAP_SECONDS)
                    # 10-second prep countdown (cancellable)
                    ok = prep_countdown(stdscr, seconds=10)
                    if not ok:
                        stdscr.nodelay(True)
                        continue
                    # Start deck recording/playback
                    playback_deck_recording(stdscr, normalized_tracks, TRACK_GAP_SECONDS, TOTAL_DURATION_MINUTES * 60, LEADER_GAP_SECONDS)
                    stdscr.nodelay(True)
                    continue
            
            time.sleep(0.05)  # Reduce CPU usage

    curses.wrapper(draw_menu)


if __name__ == "__main__":
    # Handle calibration mode
    if args.calibrate_counter:
        calibrate_counter_wizard()
        sys.exit(0)
    
    # Load calibration data if in manual mode
    if COUNTER_MODE == "manual":
        config_path = os.path.join(TARGET_FOLDER, COUNTER_CONFIG_PATH)
        CALIBRATION_DATA = load_calibration_config(config_path)
        if CALIBRATION_DATA is None:
            print("\nError: Manual mode requires calibration file.")
            print("Run with --calibrate-counter to create one, or use --counter-mode static\n")
            sys.exit(1)
        
        print(f"\n✓ Loaded calibration from: {config_path}")
        print(f"  Deck: {CALIBRATION_DATA.get('deck_model', 'Unknown')}")
        print(f"  Tape: {CALIBRATION_DATA.get('tape_type', 'Unknown')}")
        print(f"  Checkpoints: {len(CALIBRATION_DATA.get('checkpoints', []))}")
        print(f"  Date: {CALIBRATION_DATA.get('calibration_date', 'Unknown')}\n")
    
    # Display counter mode info
    mode_names = {
        "manual": "Manual Calibrated",
        "auto": "Auto Physics Simulation",
        "static": "Static Linear Rate"
    }
    print(f"Counter Mode: {mode_names.get(COUNTER_MODE, COUNTER_MODE)}")
    if COUNTER_MODE == "static":
        print(f"Counter Rate: {COUNTER_RATE} counts/second\n")
    
    main_menu(TARGET_FOLDER)

