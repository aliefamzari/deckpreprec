import os
import pygame
import curses
import subprocess
import json
import signal
import argparse
import time
from pydub import AudioSegment

# --- Argument parsing ---
parser = argparse.ArgumentParser(description="Audio Player for Tape Recording")
parser.add_argument("--track-gap", type=int, default=5, help="Gap between tracks in seconds (default: 5)")
parser.add_argument("--duration", type=int, default=60, help="Maximum tape duration in minutes (default: 60)")
parser.add_argument("--folder", type=str, default="/home/almaz/tracks", help="Folder with audio tracks")
args = parser.parse_args()

TRACK_GAP_SECONDS = args.track_gap
TOTAL_DURATION_MINUTES = args.duration
target_folder = args.folder

# Add /usr/sbin to PATH for ffmpeg/ffprobe/ffplay
os.environ["PATH"] += os.pathsep + "/usr/sbin"

# Set ffmpeg as the backend for pydub
AudioSegment.converter = "/usr/sbin/ffmpeg"

# Initialize pygame mixer (still used for normalization)
pygame.mixer.init()

# Global variable to track ffplay process
ffplay_proc = None

def format_duration(seconds):
    if seconds is None or seconds == "Unknown":
        return "Unknown"
    minutes = int(seconds) // 60
    secs = int(seconds) % 60
    return f"{minutes}:{secs:02d}"

def get_ffprobe_info(filepath):
    """Return duration, codec, and bitrate using ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error", "-show_entries",
                "format=duration:stream=codec_name,bit_rate",
                "-of", "json", filepath
            ],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        info = json.loads(result.stdout)
        duration = float(info["format"]["duration"])
        # Find the first audio stream
        codec = "Unknown"
        bitrate = "Unknown"
        for stream in info.get("streams", []):
            if stream.get("codec_name"):
                codec = stream["codec_name"]
            if stream.get("bit_rate"):
                bitrate = int(stream["bit_rate"]) // 1000  # kbps
        return duration, codec, bitrate
    except Exception:
        return None, "Unknown", "Unknown"

def list_tracks(folder):
    tracks = []
    for file in os.listdir(folder):
        if file.endswith(('.mp3', '.wav', '.flac', '.webm')):
            filepath = os.path.join(folder, file)
            duration, codec, quality = get_ffprobe_info(filepath)
            if duration is None:
                continue
            tracks.append({'name': file, 'duration': duration, 'codec': codec, 'quality': quality})
    return tracks

def normalize_tracks(tracks, folder):
    normalized_dir = os.path.join(folder, "normalized")
    os.makedirs(normalized_dir, exist_ok=True)
    normalized_tracks = []
    for track in tracks:
        src_path = os.path.join(folder, track['name'])
        norm_path = os.path.join(normalized_dir, track['name'] + ".normalized.wav")
        if os.path.exists(norm_path):
            audio = AudioSegment.from_file(norm_path)
            normalized_tracks.append({'name': track['name'], 'audio': audio, 'path': norm_path, 'dBFS': audio.dBFS})
            continue
        audio = AudioSegment.from_file(src_path)
        normalized_audio = audio.normalize()
        normalized_audio.export(norm_path, format="wav")
        normalized_tracks.append({'name': track['name'], 'audio': normalized_audio, 'path': norm_path, 'dBFS': normalized_audio.dBFS})
    return normalized_tracks

def write_deck_tracklist(normalized_tracks, track_gap, output_path):
    """
    Write a text file with track number, name, start time, end time, and duration.
    """
    lines = []
    current_time = 0
    for idx, track in enumerate(normalized_tracks):
        start_time = current_time
        duration = int(track['audio'].duration_seconds)
        end_time = start_time + duration
        lines.append(
            f"{idx+1:02d}. {track['name']}\n"
            f"    Start: {format_duration(start_time)}   "
            f"End: {format_duration(end_time)}   "
            f"Duration: {format_duration(duration)}"
        )
        current_time = end_time + (track_gap if idx < len(normalized_tracks)-1 else 0)
    with open(output_path, "w") as f:
        f.write("Tape Deck Tracklist Reference\n")
        f.write("="*32 + "\n")
        for line in lines:
            f.write(line + "\n")

def show_normalization_summary(stdscr, normalized_tracks):
    stdscr.clear()
    stdscr.addstr("Normalization complete!\n\n")
    stdscr.addstr("Track list and dBFS levels:\n")
    for i, track in enumerate(normalized_tracks):
        stdscr.addstr(f"{i+1}. {track['name']} - dBFS: {track['dBFS']:.2f}\n")
    stdscr.addstr("\nPress Enter to prepare for deck recording, or Q to quit to main menu...")
    stdscr.refresh()
    while True:
        key = stdscr.getch()
        if key in (curses.KEY_ENTER, 10, 13):
            return True   # Continue to deck recording
        elif key in (ord('q'), ord('Q')):
            return False  # Quit to main menu

def playback_deck_recording(stdscr, normalized_tracks, track_gap, total_duration):
    stdscr.clear()
    total_tracks = len(normalized_tracks)
    total_time = sum([t['audio'].duration_seconds for t in normalized_tracks]) + (track_gap * (total_tracks - 1))
    start_time = time.time()
    elapsed = 0
    # Precompute start/end/duration for display
    track_times = []
    current_time = 0
    for t in normalized_tracks:
        duration = int(t['audio'].duration_seconds)
        start_time_track = current_time
        end_time_track = start_time_track + duration
        track_times.append((start_time_track, end_time_track, duration))
        current_time = end_time_track + track_gap
    # Calculate average dBFS
    avg_dbfs = sum(t['dBFS'] for t in normalized_tracks) / len(normalized_tracks) if normalized_tracks else 0
    for idx, track in enumerate(normalized_tracks):
        track_duration = track_times[idx][2]
        track_start = time.time()
        # Start playback
        proc = subprocess.Popen(["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", track['path']])
        stdscr.nodelay(True)
        quit_to_menu = False
        while True:
            now = time.time()
            elapsed = now - start_time
            track_elapsed = now - track_start
            stdscr.clear()
            stdscr.addstr(f"Deck Recording Mode\n\n")
            stdscr.addstr(f"[Normalized] = Average dBFS: {avg_dbfs:.2f}\n")
            stdscr.addstr(f"[Track Gap] = {track_gap} seconds\n\n")
            stdscr.addstr("Tracks:\n")
            # Show tracklist in deck_tracklist.txt format
            for i, t in enumerate(normalized_tracks):
                wav_name = os.path.basename(t['path'])
                start_time_track, end_time_track, duration = track_times[i]
                marker = ">>" if i == idx else "  "
                stdscr.addstr(
                    f"{marker} {i+1:02d}. {wav_name}\n"
                    f"    Start: {format_duration(start_time_track)}   "
                    f"End: {format_duration(end_time_track)}   "
                    f"Duration: {format_duration(duration)}\n"
                )
            stdscr.addstr(f"\nPlaying: {os.path.basename(track['path'])} [{format_duration(track_elapsed)}/{format_duration(track_duration)}]\n")
            # Progress bar
            bar_len = 40
            progress = min(int(bar_len * track_elapsed / track_duration), bar_len)
            stdscr.addstr("[" + "#" * progress + "-" * (bar_len - progress) + "]\n")
            stdscr.addstr(f"\nTotal: {format_duration(elapsed)}/{format_duration(total_time)}\n")
            stdscr.addstr("\nPress Q to quit to main menu.\n")
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

def main_menu(folder):
    tracks = list_tracks(folder)
    if not tracks:
        print("No audio tracks found in the folder!")
        input("Press Enter to exit...")
        return
    selected_tracks = []
    total_selected_duration = 0
    current_index = 0  # Track navigation index
    paused = False

    def draw_menu(stdscr):
        nonlocal current_index, selected_tracks, total_selected_duration, paused
        global ffplay_proc
        curses.curs_set(0)
        stdscr.nodelay(False)
        while True:
            stdscr.clear()
            stdscr.addstr("[Audio Player Menu]\n")
            stdscr.addstr("Tracks in folder:\n")
            for i, track in enumerate(tracks):
                selected_marker = "*" if track in selected_tracks else " "
                highlight_marker = ">" if i == current_index else " "
                duration_str = format_duration(track['duration'])
                stdscr.addstr(f"{highlight_marker} {selected_marker} {i + 1}. {track['name']} - {duration_str} - {track['codec']} - {track['quality']}\n")
            stdscr.addstr("\nSelected Tracks:\n")
            for i, track in enumerate(selected_tracks):
                duration_str = format_duration(track['duration'])
                stdscr.addstr(f"{i + 1}. {track['name']} - {duration_str}\n")
            total_duration_str = format_duration(total_selected_duration)
            stdscr.addstr(f"\nTotal Duration: {total_duration_str}\n")
            stdscr.addstr(f"Track Gap: {TRACK_GAP_SECONDS} sec\n")
            stdscr.addstr(f"Max Duration: {format_duration(TOTAL_DURATION_MINUTES * 60)}\n")
            stdscr.addstr("\n[Keyboard Shortcuts]\n")
            stdscr.addstr("Up/Down: Navigate  Space: Select/Deselect  Enter: Normalize\n")
            stdscr.addstr("P: Play  S: Pause/Resume  X: Stop  Q: Quit\n")
            if paused:
                stdscr.addstr("[Paused]\n")
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
                paused = False
            elif key in (ord('s'), ord('S')):
                # Pause/Resume ffplay
                if ffplay_proc is not None and ffplay_proc.poll() is None:
                    if not paused:
                        ffplay_proc.send_signal(signal.SIGSTOP)
                        paused = True
                    else:
                        ffplay_proc.send_signal(signal.SIGCONT)
                        paused = False
            elif key in (ord('x'), ord('X')):
                # Stop playback
                if ffplay_proc is not None and ffplay_proc.poll() is None:
                    ffplay_proc.terminate()
                    ffplay_proc = None
                    paused = False
            elif key in (curses.KEY_ENTER, 10, 13):
                # Stop ffplay if running before normalization
                if ffplay_proc is not None and ffplay_proc.poll() is None:
                    ffplay_proc.terminate()
                    ffplay_proc = None
                # Normalize and show summary
                normalized_tracks = normalize_tracks(selected_tracks, folder)
                proceed = show_normalization_summary(stdscr, normalized_tracks)
                if not proceed:
                    continue  # Go back to main menu
                # Write deck tracklist file
                output_txt = os.path.join(folder, "deck_tracklist.txt")
                write_deck_tracklist(normalized_tracks, TRACK_GAP_SECONDS, output_txt)
                # Prep for deck recording
                playback_deck_recording(stdscr, normalized_tracks, TRACK_GAP_SECONDS, TOTAL_DURATION_MINUTES * 60)
                continue  # Return to main menu after deck recording

    curses.wrapper(draw_menu)

if __name__ == "__main__":
    main_menu(target_folder)