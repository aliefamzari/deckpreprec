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
  • VU meter-style progress bars with block characters
  • Track selection with duration validation
  • 10-second prep countdown before recording
  • Real-time playback monitoring with track positions
  • Generates detailed tracklist reference file with counter positions

Usage:
  python3 decprec.py --folder ./tracks --track-gap 5 --duration 60 --counter-rate 1.0

Arguments:
  --folder        Path to audio tracks directory (default: ./tracks)
  --track-gap     Gap between tracks in seconds (default: 5)
  --duration      Maximum tape duration in minutes (default: 60)
  --counter-rate  Tape counter increments per second (default: 1.0)

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
from pydub import AudioSegment

# --- Argument parsing ---
parser = argparse.ArgumentParser(description="Audio Player for Tape Recording")
parser.add_argument("--track-gap", type=int, default=5, help="Gap between tracks in seconds (default: 5)")
parser.add_argument("--duration", type=int, default=60, help="Maximum tape duration in minutes (default: 60)")
parser.add_argument("--folder", type=str, default="./tracks", help="Folder with audio tracks")
parser.add_argument("--counter-rate", type=float, default=1.0, help="Tape counter increments per second (default: 1.0)")
args = parser.parse_args()

TRACK_GAP_SECONDS = args.track_gap
TOTAL_DURATION_MINUTES = args.duration
TARGET_FOLDER = args.folder
COUNTER_RATE = args.counter_rate

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
            normalized_tracks.append({'name': track['name'], 'audio': audio, 'path': norm_path, 'dBFS': audio.dBFS})
            continue
        # Show progress in curses (if provided)
        if stdscr:
            stdscr.clear()
            stdscr.addstr(f"Normalizing {i+1}/{len(tracks)}: {track['name']}\n")
            stdscr.addstr("(This may take a few seconds per file)\n")
            stdscr.refresh()
        audio = AudioSegment.from_file(src_path)
        normalized_audio = audio.normalize()
        normalized_audio.export(norm_path, format="wav")
        normalized_tracks.append({'name': track['name'], 'audio': normalized_audio, 'path': norm_path, 'dBFS': normalized_audio.dBFS})
    return normalized_tracks


def write_deck_tracklist(normalized_tracks, track_gap, output_path, counter_rate):
    lines = []
    current_time = 0
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
    with open(output_path, "w") as f:
        f.write("Tape Deck Tracklist Reference\n")
        f.write("="*40 + "\n")
        f.write(f"Counter Rate: {counter_rate} counts/second\n\n")
        for line in lines:
            f.write(line + "\n")


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


def playback_deck_recording(stdscr, normalized_tracks, track_gap, total_duration):
    stdscr.clear()
    total_tracks = len(normalized_tracks)
    total_time = sum(int(round(t['audio'].duration_seconds)) for t in normalized_tracks) + (track_gap * (total_tracks - 1))
    overall_start_time = time.time()

    # Precompute start/end/duration for display
    track_times = []
    current_time = 0
    for t in normalized_tracks:
        duration = int(round(t['audio'].duration_seconds))
        start_time_track = current_time
        end_time_track = start_time_track + duration
        track_times.append((start_time_track, end_time_track, duration))
        current_time = end_time_track + track_gap

    avg_dbfs = sum(t['dBFS'] for t in normalized_tracks) / len(normalized_tracks) if normalized_tracks else 0

    for idx, track in enumerate(normalized_tracks):
        track_duration = track_times[idx][2]
        track_start_time = time.time()
        # launch ffplay for each track
        proc = subprocess.Popen(["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", track['path']])
        stdscr.nodelay(True)
        quit_to_menu = False
        while True:
            now = time.time()
            elapsed = now - overall_start_time
            track_elapsed = now - track_start_time
            current_counter = int(elapsed * COUNTER_RATE)
            stdscr.clear()
            # Title
            stdscr.addstr(0, 0, "╔" + "═" * 78 + "╗", curses.color_pair(COLOR_CYAN))
            stdscr.addstr(1, 30, "DECK RECORDING MODE", curses.color_pair(COLOR_MAGENTA) | curses.A_BOLD)
            stdscr.addstr(2, 0, "╚" + "═" * 78 + "╝", curses.color_pair(COLOR_CYAN))
            # Counter and stats - use full string for alignment
            stdscr.addstr(4, 2, "┌─ TAPE COUNTER ──┐", curses.color_pair(COLOR_YELLOW))
            counter_line = f"│     {current_counter:04d}        │"
            stdscr.addstr(5, 2, counter_line[:6], curses.color_pair(COLOR_YELLOW))
            stdscr.addstr(f"{current_counter:04d}", curses.color_pair(COLOR_GREEN) | curses.A_BOLD)
            stdscr.addstr(counter_line[10:], curses.color_pair(COLOR_YELLOW))
            stdscr.addstr(6, 2, "└─────────────────┘", curses.color_pair(COLOR_YELLOW))
            stdscr.addstr(4, 25, f"AVG dBFS: {avg_dbfs:+.2f}", curses.color_pair(COLOR_CYAN))
            stdscr.addstr(5, 25, f"TRACK GAP: {track_gap}s", curses.color_pair(COLOR_CYAN))
            stdscr.addstr(8, 0, "[TRACKS]:", curses.color_pair(COLOR_MAGENTA) | curses.A_BOLD)
            for i, t in enumerate(normalized_tracks):
                wav_name = os.path.basename(t['path'])
                start_time_track, end_time_track, duration = track_times[i]
                counter_start = int(start_time_track * COUNTER_RATE)
                counter_end = int(end_time_track * COUNTER_RATE)
                is_current = i == idx
                marker = "▶▶" if is_current else "  "
                color = COLOR_GREEN if is_current else COLOR_CYAN
                line_y = 9 + (i * 3)
                stdscr.addstr(line_y, 0, marker, curses.color_pair(COLOR_GREEN) | curses.A_BOLD if is_current else curses.color_pair(COLOR_WHITE))
                stdscr.addstr(f" {i+1:02d}. ", curses.color_pair(color))
                stdscr.addstr(f"{wav_name}\n", curses.color_pair(COLOR_YELLOW) if is_current else curses.color_pair(COLOR_WHITE))
                stdscr.addstr(line_y + 1, 5, f"Start: {format_duration(start_time_track)}   End: {format_duration(end_time_track)}   Duration: {format_duration(duration)}\n", curses.color_pair(color))
                stdscr.addstr(line_y + 2, 5, f"Counter: ", curses.color_pair(color))
                stdscr.addstr(f"{counter_start:04d}", curses.color_pair(COLOR_YELLOW))
                stdscr.addstr(" - ", curses.color_pair(color))
                stdscr.addstr(f"{counter_end:04d}\n", curses.color_pair(COLOR_YELLOW))
            play_y = 9 + (len(normalized_tracks) * 3) + 1
            stdscr.addstr(play_y, 0, "─" * 78, curses.color_pair(COLOR_CYAN))
            stdscr.addstr(play_y + 1, 0, "NOW PLAYING: ", curses.color_pair(COLOR_MAGENTA) | curses.A_BOLD)
            stdscr.addstr(f"{os.path.basename(track['path'])}", curses.color_pair(COLOR_YELLOW))
            stdscr.addstr(play_y + 2, 0, f"[{format_duration(track_elapsed)}/{format_duration(track_duration)}]", curses.color_pair(COLOR_GREEN))
            # Progress bar with VU meter style
            bar_len = 60
            progress = min(int(bar_len * (track_elapsed / max(1, track_duration))), bar_len)
            stdscr.addstr(play_y + 3, 0, "[", curses.color_pair(COLOR_CYAN))
            stdscr.addstr("█" * progress, curses.color_pair(COLOR_GREEN))
            stdscr.addstr("░" * (bar_len - progress), curses.color_pair(COLOR_BLUE))
            stdscr.addstr("]\n", curses.color_pair(COLOR_CYAN))
            stdscr.addstr(play_y + 5, 0, f"TOTAL: {format_duration(elapsed)}/{format_duration(total_time)}", curses.color_pair(COLOR_YELLOW))
            stdscr.addstr(play_y + 7, 0, "Press ", curses.color_pair(COLOR_WHITE))
            stdscr.addstr("Q", curses.color_pair(COLOR_RED) | curses.A_BOLD)
            stdscr.addstr(" to quit to main menu.", curses.color_pair(COLOR_WHITE))
            stdscr.refresh()
            key = stdscr.getch()
            if key in (ord('q'), ord('Q')):
                if proc.poll() is None:
                    proc.terminate()
                quit_to_menu = True
                break
            if proc.poll() is not None:
                break
            time.sleep(0.1)
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
                info_line = f"Total: {total_duration_str} | Gap: {TRACK_GAP_SECONDS}s | Max: {format_duration(TOTAL_DURATION_MINUTES * 60)}"
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
                # Write tracklist file
                output_txt = os.path.join(folder, "deck_tracklist.txt")
                write_deck_tracklist(normalized_tracks, TRACK_GAP_SECONDS, output_txt, COUNTER_RATE)
                # 10-second prep countdown (cancellable)
                ok = prep_countdown(stdscr, seconds=10)
                if not ok:
                    continue
                # Start deck recording/playback
                playback_deck_recording(stdscr, normalized_tracks, TRACK_GAP_SECONDS, TOTAL_DURATION_MINUTES * 60)
                continue

    curses.wrapper(draw_menu)


if __name__ == "__main__":
    main_menu(TARGET_FOLDER)

