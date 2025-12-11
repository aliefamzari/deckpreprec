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
import subprocess
import json
import signal
import argparse
import time
import curses
import random
import math
from datetime import datetime
from pydub import AudioSegment

# --- Argument parsing ---
parser = argparse.ArgumentParser(description="Audio Player for Tape Recording")
parser.add_argument("--track-gap", type=int, default=5, help="Gap between tracks in seconds (default: 5)")
parser.add_argument("--duration", type=int, default=60, help="Maximum tape duration in minutes (default: 60)")
parser.add_argument("--folder", type=str, default="./tracks", help="Folder with audio tracks")
parser.add_argument("--counter-rate", type=float, default=1.0, help="Tape counter increments per second (default: 1.0)")
parser.add_argument("--leader-gap", type=int, default=10, help="Leader gap before first track in seconds (default: 10)")
args = parser.parse_args()

TRACK_GAP_SECONDS = args.track_gap
TOTAL_DURATION_MINUTES = args.duration
TARGET_FOLDER = args.folder
COUNTER_RATE = args.counter_rate
LEADER_GAP_SECONDS = args.leader_gap

# Add /usr/sbin to PATH for ffmpeg/ffprobe/ffplay if present
os.environ["PATH"] += os.pathsep + "/usr/sbin"
AudioSegment.converter = "/usr/bin/ffmpeg"

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
        " /=======================================================q\\",
        "|:@-                                                     #+|",
        "| '   /==============================================\\     |",
        "|   ./                                                \\,   |",
        "|  :'                                                  `;  |",
        "|  |                                                    |  |",
        "|  |                                                    |  |",
        "|  |                                                    |  |",
        "|  |          ._____________________________,           |  |",
        "|  |        ./Lm=\\_   mmmmmr======qmm   _m=\\Jq          |  |",
        "|  |        /W'`' *b  ######      W##  d'`' *bt         |  |",
        "|  |       :\\@'    M, ######|     ### :@!    V/,        |  |",
        "|  |        PW     @! ######b_____### `W_    @@         |  |",
        "|  |        |/#_,LZ! .d_!!! t|,!! !!d  !@L,mZt!         |  |",
        "|  |         `=\\XX___JXX____JXL_____X_____J+='          |  |",
        "|  |                                                    |  |",
        "|  |                                                    |  |",
        "#  |                                                    |  D,",
        "#  |                                                    |  ||",
        "#  `~~~~~~~XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX7~~~~~~~~'  ||",
        "#         /                                    |           ||",
        "#         |                 |#-                 |          ||",
        "#        :'                  '                  t          ||",
        "M        |          /~|              |~|        |          @",
        "|.L      /    |~\\   \\=!              !=!  :~Y,   |       jL|",
        "!(KL_____b____JGL__________________________GK____G_______8*"
    ]
    for i, line in enumerate(art):
        try:
            stdscr.addstr(y + i, x, line, curses.color_pair(COLOR_MAGENTA))
        except:
            pass

def format_duration(seconds):
    if seconds is None or seconds == "Unknown":
        return "Unknown"
    seconds = int(round(seconds))
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes}:{secs:02d}"


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
    """Normalize all tracks and return list of dicts with keys: name, path, audio, dBFS
    Skips normalization if normalized file exists.
    """
    normalized_dir = os.path.join(folder, "normalized")
    os.makedirs(normalized_dir, exist_ok=True)
    normalized_tracks = []
    for i, track in enumerate(tracks):
        src_path = os.path.join(folder, track['name'])
        # normalized filename keeps original name but uses .normalized.wav suffix
        norm_name = f"{track['name']}.normalized.wav"
        norm_path = os.path.join(normalized_dir, norm_name)
        if os.path.exists(norm_path):
            audio = AudioSegment.from_file(norm_path)
            if stdscr:
                stdscr.clear()
                safe_addstr(stdscr, 0, 0, f"Loading {i+1}/{len(tracks)}: {track['name']}", curses.color_pair(COLOR_YELLOW))
                safe_addstr(stdscr, 1, 0, "Analyzing waveform...", curses.color_pair(COLOR_GREEN))
                stdscr.refresh()
            audio_levels = analyze_audio_levels(audio, chunk_duration_ms=50)
            normalized_tracks.append({'name': track['name'], 'audio': audio, 'path': norm_path, 'dBFS': audio.dBFS, 'audio_levels': audio_levels})
            continue
        # Show progress in curses (if provided)
        if stdscr:
            stdscr.clear()
            safe_addstr(stdscr, 0, 0, f"Normalizing {i+1}/{len(tracks)}: {track['name']}", curses.color_pair(COLOR_YELLOW))
            safe_addstr(stdscr, 1, 0, "(This may take a few seconds per file)", curses.color_pair(COLOR_CYAN))
            stdscr.refresh()
        audio = AudioSegment.from_file(src_path)
        normalized_audio = audio.normalize()
        normalized_audio.export(norm_path, format="wav")
        if stdscr:
            safe_addstr(stdscr, 2, 0, "Analyzing waveform...", curses.color_pair(COLOR_GREEN))
            stdscr.refresh()
        audio_levels = analyze_audio_levels(normalized_audio, chunk_duration_ms=50)
        normalized_tracks.append({'name': track['name'], 'audio': normalized_audio, 'path': norm_path, 'dBFS': normalized_audio.dBFS, 'audio_levels': audio_levels})
    return normalized_tracks


def write_deck_tracklist(normalized_tracks, track_gap, folder, counter_rate, leader_gap):
    """Generate tracklist file with timestamp to avoid overwriting"""
    lines = []
    current_time = leader_gap  # Start after leader gap
    for idx, track in enumerate(normalized_tracks):
        start_time = current_time
        duration = int(round(track['audio'].duration_seconds))
        end_time = start_time + duration
        counter_start = int(start_time * counter_rate)
        counter_end = int(end_time * counter_rate)
        lines.append(
            f"{idx+1:02d}. {track['name']}\n"
            f"    Start: {format_duration(start_time)}   End: {format_duration(end_time)}   Duration: {format_duration(duration)}\n"
            f"    Counter: {counter_start:04d} - {counter_end:04d}"
        )
        current_time = end_time + (track_gap if idx < len(normalized_tracks)-1 else 0)
    
    # Generate unique filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"deck_tracklist_{timestamp}.txt"
    output_path = os.path.join(folder, output_filename)
    
    with open(output_path, "w") as f:
        f.write("Tape Deck Tracklist Reference\n")
        f.write("="*40 + "\n")
        f.write(f"Session: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Counter Rate: {counter_rate} counts/second\n")
        f.write(f"Leader Gap: {leader_gap}s (Counter: 0000 - {int(leader_gap * counter_rate):04d})\n\n")
        for line in lines:
            f.write(line + "\n")
    
    return output_path


def show_normalization_summary(stdscr, normalized_tracks):
    stdscr.clear()
    stdscr.refresh()
    stdscr.erase()
    safe_addstr(stdscr, 0, 0, "═" * 70, curses.color_pair(COLOR_CYAN))
    safe_addstr(stdscr, 1, 20, "NORMALIZATION COMPLETE", curses.color_pair(COLOR_GREEN) | curses.A_BOLD)
    safe_addstr(stdscr, 2, 0, "═" * 70, curses.color_pair(COLOR_CYAN))
    safe_addstr(stdscr, 4, 0, "TRACK LIST AND dBFS LEVELS:", curses.color_pair(COLOR_YELLOW))
    for i, track in enumerate(normalized_tracks):
        track_line = f"  {i+1:02d}. {track['name']} - dBFS: {track['dBFS']:.2f}"
        safe_addstr(stdscr, 5 + i, 0, track_line, curses.color_pair(COLOR_CYAN))
    
    footer_y = 6 + len(normalized_tracks)
    safe_addstr(stdscr, footer_y, 0, "─" * 70, curses.color_pair(COLOR_CYAN))
    safe_addstr(stdscr, footer_y + 1, 0, "Press ENTER to start prep countdown, or Q to cancel...", curses.color_pair(COLOR_WHITE))
    stdscr.refresh()
    while True:
        key = stdscr.getch()
        if key in (curses.KEY_ENTER, 10, 13):
            return True
        elif key in (ord('q'), ord('Q')):
            return False


def prep_countdown(stdscr, seconds=10):
    """Show a cancellable countdown. Return True to proceed, False to cancel."""
    stdscr.nodelay(True)
    max_y, max_x = stdscr.getmaxyx()
    
    for s in range(seconds, 0, -1):
        # Aggressive clearing
        stdscr.erase()
        stdscr.clear()
        stdscr.refresh()
        
        # Simple countdown without cassette art to avoid overlap
        countdown_y = max_y // 2 - 3
        box_width = min(70, max_x - 2)
        
        # Draw top border
        safe_addstr(stdscr, countdown_y, 0, "╔" + "═" * (box_width - 2) + "╗", curses.color_pair(COLOR_MAGENTA))
        
        # Draw countdown text centered in box
        count_str = f"DECK PREP COUNTDOWN: {s:02d}"
        x_pos = max(1, (box_width - len(count_str)) // 2)
        safe_addstr(stdscr, countdown_y + 1, 0, "║" + " " * (box_width - 2) + "║", curses.color_pair(COLOR_MAGENTA))
        safe_addstr(stdscr, countdown_y + 1, x_pos, count_str, curses.color_pair(COLOR_YELLOW) | curses.A_BOLD | curses.A_BLINK)
        
        # Draw bottom border
        safe_addstr(stdscr, countdown_y + 2, 0, "╚" + "═" * (box_width - 2) + "╝", curses.color_pair(COLOR_MAGENTA))
        
        # Instructions
        instr_str = "Press Q to cancel and return to menu."
        instr_x = max(0, (box_width - len(instr_str)) // 2)
        safe_addstr(stdscr, countdown_y + 4, instr_x, instr_str, curses.color_pair(COLOR_WHITE))
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
    overall_start_time = time.time()

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

    # Leader gap countdown before first track
    if leader_gap > 0:
        stdscr.nodelay(True)
        leader_start_time = time.time()
        quit_to_menu = False
        while True:
            elapsed = time.time() - overall_start_time
            leader_elapsed = time.time() - leader_start_time
            current_counter = int(elapsed * COUNTER_RATE)
            
            if leader_elapsed >= leader_gap:
                break
            
            stdscr.clear()
            draw_cassette_art(stdscr, 0, 10)
            
            title_y = 27
            stdscr.addstr(title_y, 0, "╔" + "═" * 78 + "╗", curses.color_pair(COLOR_CYAN))
            stdscr.addstr(title_y + 1, 28, "LEADER GAP - STAND BY", curses.color_pair(COLOR_MAGENTA) | curses.A_BOLD)
            stdscr.addstr(title_y + 2, 0, "╚" + "═" * 78 + "╝", curses.color_pair(COLOR_CYAN))
            
            stdscr.addstr(title_y + 4, 2, "┌─ TAPE COUNTER ──┐", curses.color_pair(COLOR_YELLOW))
            counter_line = f"│     {current_counter:04d}        │"
            stdscr.addstr(title_y + 5, 2, counter_line[:6], curses.color_pair(COLOR_YELLOW))
            stdscr.addstr(f"{current_counter:04d}", curses.color_pair(COLOR_GREEN) | curses.A_BOLD)
            stdscr.addstr(counter_line[10:], curses.color_pair(COLOR_YELLOW))
            stdscr.addstr(title_y + 6, 2, "└─────────────────┘", curses.color_pair(COLOR_YELLOW))
            
            leader_remaining = int(leader_gap - leader_elapsed)
            stdscr.addstr(title_y + 8, 10, f"Waiting for leader tape to pass... {leader_remaining}s", 
                         curses.color_pair(COLOR_YELLOW) | curses.A_BLINK)
            stdscr.addstr(title_y + 10, 10, f"First track will start at counter {int(leader_gap * COUNTER_RATE):04d}", 
                         curses.color_pair(COLOR_CYAN))
            
            footer_y = title_y + 15
            safe_addstr(stdscr, footer_y, 0, "Press ", curses.color_pair(COLOR_WHITE))
            safe_addstr(stdscr, footer_y, 6, "Q", curses.color_pair(COLOR_RED) | curses.A_BOLD)
            safe_addstr(stdscr, footer_y, 7, " to quit to main menu.", curses.color_pair(COLOR_WHITE))
            
            stdscr.refresh()
            
            key = stdscr.getch()
            if key in (ord('q'), ord('Q')):
                quit_to_menu = True
                break
            
            time.sleep(0.05)
        
        stdscr.nodelay(False)
        if quit_to_menu:
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
            current_counter = int(elapsed * COUNTER_RATE)
            current_progress = int(60 * (track_elapsed / max(1, track_duration)))
            
            # Only redraw if something changed or first draw
            if first_draw or current_counter != last_counter or current_progress != last_progress:
                if first_draw:
                    stdscr.clear()
                    first_draw = False
                else:
                    # Don't clear entire screen, just update changed areas
                    pass
            # Draw cassette art at top
            draw_cassette_art(stdscr, 0, 10)
            
            # Title below cassette
            title_y = 27
            stdscr.addstr(title_y, 0, "╔" + "═" * 78 + "╗", curses.color_pair(COLOR_CYAN))
            stdscr.addstr(title_y + 1, 30, "DECK RECORDING MODE", curses.color_pair(COLOR_MAGENTA) | curses.A_BOLD)
            stdscr.addstr(title_y + 2, 0, "╚" + "═" * 78 + "╝", curses.color_pair(COLOR_CYAN))
            # Counter and stats - use full string for alignment
            stdscr.addstr(title_y + 4, 2, "┌─ TAPE COUNTER ──┐", curses.color_pair(COLOR_YELLOW))
            counter_line = f"│     {current_counter:04d}        │"
            stdscr.addstr(title_y + 5, 2, counter_line[:6], curses.color_pair(COLOR_YELLOW))
            stdscr.addstr(f"{current_counter:04d}", curses.color_pair(COLOR_GREEN) | curses.A_BOLD)
            stdscr.addstr(counter_line[10:], curses.color_pair(COLOR_YELLOW))
            stdscr.addstr(title_y + 6, 2, "└─────────────────┘", curses.color_pair(COLOR_YELLOW))
            stdscr.addstr(title_y + 4, 25, f"AVG dBFS: {avg_dbfs:+.2f}", curses.color_pair(COLOR_CYAN))
            stdscr.addstr(title_y + 5, 25, f"TRACK GAP: {track_gap}s", curses.color_pair(COLOR_CYAN))
            
            # VU Meters - real audio levels from waveform analysis (below counter)
            meter_y = title_y + 8
            elapsed_ms = int(track_elapsed * 1000)
            level_l, level_r = get_audio_level_at_time(track['audio_levels'], elapsed_ms)
            stdscr.addstr(meter_y, 0, "─" * 78, curses.color_pair(COLOR_CYAN))
            draw_vu_meter(stdscr, meter_y + 1, 2, level_l, max_width=50, label="L")
            stdscr.addstr(meter_y + 2, 0, " " * 78, curses.color_pair(COLOR_CYAN))  # Space between channels
            draw_vu_meter(stdscr, meter_y + 3, 2, level_r, max_width=50, label="R")
            stdscr.addstr(meter_y + 4, 0, "─" * 78, curses.color_pair(COLOR_CYAN))
            
            # NOW PLAYING section (after VU meters)
            play_y = meter_y + 6
            stdscr.addstr(play_y, 0, "NOW PLAYING: ", curses.color_pair(COLOR_MAGENTA) | curses.A_BOLD)
            stdscr.addstr(f"{os.path.basename(track['path'])}", curses.color_pair(COLOR_YELLOW))
            # Progress bar with duration time on the right
            bar_len = 60
            progress = min(int(bar_len * (track_elapsed / max(1, track_duration))), bar_len)
            stdscr.addstr(play_y + 1, 0, "[", curses.color_pair(COLOR_CYAN))
            stdscr.addstr("█" * progress, curses.color_pair(COLOR_GREEN))
            stdscr.addstr("░" * (bar_len - progress), curses.color_pair(COLOR_BLUE))
            stdscr.addstr("]", curses.color_pair(COLOR_CYAN))
            stdscr.addstr(f" [{format_duration(track_elapsed)}/{format_duration(track_duration)}]", curses.color_pair(COLOR_GREEN))
            
            # Track list
            tracks_y = play_y + 3
            stdscr.addstr(tracks_y, 0, "[TRACKS]:", curses.color_pair(COLOR_MAGENTA) | curses.A_BOLD)
            for i, t in enumerate(normalized_tracks):
                wav_name = os.path.basename(t['path'])
                start_time_track, end_time_track, duration = track_times[i]
                counter_start = int(start_time_track * COUNTER_RATE)
                counter_end = int(end_time_track * COUNTER_RATE)
                is_current = i == idx
                marker = "▶▶" if is_current else "  "
                color = COLOR_GREEN if is_current else COLOR_CYAN
                line_y = tracks_y + 1 + (i * 3)
                stdscr.addstr(line_y, 0, marker, curses.color_pair(COLOR_GREEN) | curses.A_BOLD if is_current else curses.color_pair(COLOR_WHITE))
                stdscr.addstr(f" {i+1:02d}. ", curses.color_pair(color))
                stdscr.addstr(f"{wav_name}\n", curses.color_pair(COLOR_YELLOW) if is_current else curses.color_pair(COLOR_WHITE))
                stdscr.addstr(line_y + 1, 5, f"Start: {format_duration(start_time_track)}   End: {format_duration(end_time_track)}   Duration: {format_duration(duration)}\n", curses.color_pair(color))
                stdscr.addstr(line_y + 2, 5, f"Counter: ", curses.color_pair(color))
                stdscr.addstr(f"{counter_start:04d}", curses.color_pair(COLOR_YELLOW))
                stdscr.addstr(" - ", curses.color_pair(color))
                stdscr.addstr(f"{counter_end:04d}\n", curses.color_pair(COLOR_YELLOW))
            
            # Footer (with boundary checking)
            footer_y = tracks_y + 1 + (len(normalized_tracks) * 3) + 1
            max_y, max_x = stdscr.getmaxyx()
            if footer_y < max_y - 4:
                safe_addstr(stdscr, footer_y, 0, "─" * 78, curses.color_pair(COLOR_CYAN))
                safe_addstr(stdscr, footer_y + 1, 0, f"TOTAL: {format_duration(elapsed)}/{format_duration(total_time)}", curses.color_pair(COLOR_YELLOW))
                safe_addstr(stdscr, footer_y + 3, 0, "Press ", curses.color_pair(COLOR_WHITE))
                safe_addstr(stdscr, footer_y + 3, 6, "Q", curses.color_pair(COLOR_RED) | curses.A_BOLD)
                safe_addstr(stdscr, footer_y + 3, 7, " to quit to main menu.", curses.color_pair(COLOR_WHITE))
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
            return
        # Track gap countdown
        if idx < total_tracks - 1:
            for gap_sec in range(track_gap, 0, -1):
                stdscr.addstr(f"\nNext track in {gap_sec} seconds... (Press Q to quit to main menu)\n")
                stdscr.refresh()
                stdscr.nodelay(True)
                key = stdscr.getch()
                if key in (ord('q'), ord('Q')):
                    return
                time.sleep(1)
            stdscr.nodelay(False)
    stdscr.addstr("\nRecording complete! Press any key to exit.")
    stdscr.refresh()
    stdscr.getch()


def play_audio(path):
    """Start ffplay for quick preview. Uses global ffplay_proc so main menu can stop it."""
    global ffplay_proc
    # stop existing if running
    try:
        if ffplay_proc is not None and ffplay_proc.poll() is None:
            ffplay_proc.terminate()
    except Exception:
        pass
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
    paused = False

    def draw_menu(stdscr):
        nonlocal current_index, selected_tracks, total_selected_duration, paused
        global ffplay_proc
        init_colors()
        curses.curs_set(0)
        stdscr.nodelay(False)
        previewing_index = -1  # Track which file is being previewed
        while True:
            max_y, max_x = stdscr.getmaxyx()
            stdscr.clear()
            
            # Only draw cassette if there's enough room
            if max_y > 35:
                draw_cassette_art(stdscr, 1, 5)
                header_y = 28
            else:
                header_y = 0
            
            safe_addstr(stdscr, header_y, 0, "═" * min(70, max_x - 2), curses.color_pair(COLOR_CYAN))
            safe_addstr(stdscr, header_y + 1, 20, "AUDIO PLAYER MENU", curses.color_pair(COLOR_MAGENTA) | curses.A_BOLD)
            safe_addstr(stdscr, header_y + 2, 0, "═" * min(70, max_x - 2), curses.color_pair(COLOR_CYAN))
            safe_addstr(stdscr, header_y + 3, 0, "TRACKS IN FOLDER:", curses.color_pair(COLOR_YELLOW) | curses.A_BOLD)
            # Check if preview is still playing
            if previewing_index >= 0:
                if ffplay_proc is None or ffplay_proc.poll() is not None:
                    previewing_index = -1  # Preview ended
            
            track_start_y = header_y + 4
            for i, track in enumerate(tracks):
                track_y = track_start_y + i
                if track_y >= max_y - 10:  # Leave room for footer
                    break
                selected_marker = "●" if track in selected_tracks else "○"
                highlight_marker = "▶" if i == current_index else " "
                preview_marker = " ♪" if i == previewing_index else ""  # Musical note for playing track
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
                
                track_line = f"{highlight_marker} {selected_marker} {i + 1:02d}. {track['name']} - {duration_str}{preview_marker}"
                safe_addstr(stdscr, track_y, 0, track_line, curses.color_pair(text_color) | attr)
            sel_y = track_start_y + min(len(tracks), max_y - header_y - 15) + 1
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
                
                # Footer info
                footer_y = current_y + 1
                total_duration_str = format_duration(total_selected_duration)
                info_line = f"Total: {total_duration_str} | Leader: {LEADER_GAP_SECONDS}s | Gap: {TRACK_GAP_SECONDS}s | Max: {format_duration(TOTAL_DURATION_MINUTES * 60)}"
                safe_addstr(stdscr, footer_y, 0, "─" * min(70, max_x - 2), curses.color_pair(COLOR_CYAN))
                safe_addstr(stdscr, footer_y + 1, 0, info_line, curses.color_pair(COLOR_CYAN))
                
                safe_addstr(stdscr, footer_y + 2, 0, "─" * min(70, max_x - 2), curses.color_pair(COLOR_CYAN))
                safe_addstr(stdscr, footer_y + 3, 0, "Up/Down:Nav Space:Select Enter:Record P:Play X:Stop Q:Quit", curses.color_pair(COLOR_WHITE))
                if paused:
                    safe_addstr(stdscr, footer_y + 4, 0, "[Paused]", curses.color_pair(COLOR_RED) | curses.A_BLINK)
            stdscr.refresh()

            key = stdscr.getch()
            if key in (ord('q'), ord('Q')):
                # Stop ffplay if running
                if ffplay_proc is not None and ffplay_proc.poll() is None:
                    ffplay_proc.terminate()
                    ffplay_proc = None
                break
            elif key in (curses.KEY_UP, ord('k')):
                current_index = (current_index - 1) % len(tracks)
            elif key in (curses.KEY_DOWN, ord('j')):
                current_index = (current_index + 1) % len(tracks)
            elif key == ord(' '):
                track = tracks[current_index]
                if track in selected_tracks:
                    selected_tracks.remove(track)
                    total_selected_duration -= track['duration']
                else:
                    if total_selected_duration + track['duration'] + TRACK_GAP_SECONDS <= TOTAL_DURATION_MINUTES * 60:
                        selected_tracks.append(track)
                        total_selected_duration += track['duration']
                    else:
                        max_y, _ = stdscr.getmaxyx()
                        stdscr.move(max_y - 2, 0)
                        stdscr.clrtoeol()
                        stdscr.addstr("[Warning] Total duration exceeded! Press any key to continue.")
                        stdscr.refresh()
                        stdscr.getch()
            elif key in (ord('p'), ord('P')):
                track_path = os.path.join(folder, tracks[current_index]['name'])
                play_audio(track_path)
                previewing_index = current_index
                paused = False
            elif key in (ord('x'), ord('X')):
                if ffplay_proc is not None and ffplay_proc.poll() is None:
                    ffplay_proc.terminate()
                    ffplay_proc = None
                    previewing_index = -1
                    paused = False
            elif key in (curses.KEY_ENTER, 10, 13):
                # Stop ffplay if running before normalization
                if ffplay_proc is not None and ffplay_proc.poll() is None:
                    ffplay_proc.terminate()
                    ffplay_proc = None
                if not selected_tracks:
                    continue
                # Normalize (skips existing normalized wavs)
                normalized_tracks = normalize_tracks(selected_tracks, folder, stdscr)
                proceed = show_normalization_summary(stdscr, normalized_tracks)
                if not proceed:
                    continue
                # Write tracklist file with unique timestamp
                output_txt = write_deck_tracklist(normalized_tracks, TRACK_GAP_SECONDS, folder, COUNTER_RATE, LEADER_GAP_SECONDS)
                # 10-second prep countdown (cancellable)
                ok = prep_countdown(stdscr, seconds=10)
                if not ok:
                    continue
                # Start deck recording/playback
                playback_deck_recording(stdscr, normalized_tracks, TRACK_GAP_SECONDS, TOTAL_DURATION_MINUTES * 60, LEADER_GAP_SECONDS)
                continue

    curses.wrapper(draw_menu)


if __name__ == "__main__":
    main_menu(TARGET_FOLDER)

