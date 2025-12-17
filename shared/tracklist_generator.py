#!/usr/bin/env python3
"""
Tracklist Generation Module
Handles creation of timestamped tracklist files
"""

import os
from datetime import datetime


def format_duration(seconds):
    """Format duration in MM:SS format"""
    if seconds is None or seconds == "Unknown":
        return "Unknown"
    seconds = int(round(seconds))
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes}:{secs:02d}"


def write_deck_tracklist(normalized_tracks, track_gap, folder, leader_gap, 
                        normalization_method="lufs", target_lufs=-14.0, 
                        tape_type="Type I", counter_mode="static", counter_rate=1.0,
                        calibration_data=None, counter_config_path=None, 
                        total_duration_minutes=30, audio_latency=0.0,
                        calculate_tape_counter=None, get_tape_type_info=None):
    """Generate tracklist file with timestamp to avoid overwriting"""
    
    # Import counter calculation function
    if calculate_tape_counter is None:
        from .counter_engine import calculate_tape_counter as calc_func
        
        def calculate_tape_counter_wrapper(time_sec):
            return calc_func(time_sec, counter_mode, counter_rate, calibration_data)
        calculate_tape_counter = calculate_tape_counter_wrapper
    
    # Import tape type info function
    if get_tape_type_info is None:
        from .deck_profiles import get_tape_type_info as tape_info_func
        get_tape_type_info = tape_info_func
    
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
    norm_info = f"lufs{target_lufs:+.1f}" if normalization_method == "lufs" else "peak"
    output_filename = f"deck_tracklist_{timestamp}_{norm_info}.txt"
    output_path = os.path.join(folder, output_filename)
    
    with open(output_path, "w") as f:
        f.write("Tape Deck Tracklist Reference\n")
        f.write("="*60 + "\n")
        f.write(f"Session: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        # Tape Information
        f.write("TAPE INFORMATION:\n")
        f.write("-" * 17 + "\n")
        tape_info = get_tape_type_info(tape_type)
        f.write(f"Tape Type: {tape_type} - {tape_info['name']}\n")
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
        f.write(f"Counter Mode: {mode_names.get(counter_mode, counter_mode)}\n")
        
        if counter_mode == "static":
            f.write(f"Counter Rate: {counter_rate} counts/second (constant)\n")
        elif counter_mode == "manual" and calibration_data:
            f.write(f"Calibration Source: {counter_config_path}\n")
            deck = calibration_data.get('deck_model', 'Unknown')
            tape = calibration_data.get('tape_type', 'Unknown')
            cal_date = calibration_data.get('calibration_date', 'Unknown')
            f.write(f"Deck Model: {deck}\n")
            f.write(f"Tape Type: {tape}\n")
            f.write(f"Calibration Date: {cal_date}\n")
            checkpoints = calibration_data.get('checkpoints', [])
            if checkpoints:
                f.write(f"Calibration Points: {len(checkpoints)} measured checkpoints\n")
        elif counter_mode == "auto":
            f.write(f"Physics Simulation: Reel-based calculation\n")
            f.write(f"Base Rate: {counter_rate} counts/second (at tape midpoint)\n")
        
        f.write(f"Leader Gap: {leader_gap}s (Counter: 0000 - {calculate_tape_counter(leader_gap):04d})\n\n")
        
        # Audio Configuration
        f.write("AUDIO CONFIGURATION:\n")
        f.write("-" * 20 + "\n")
        f.write(f"Normalization: {normalization_method.upper()}")
        if normalization_method == "lufs":
            f.write(f" (target: {target_lufs:+.1f} LUFS)\n")
        else:
            f.write(" (peak normalization)\n")
        f.write(f"Track Gap: {track_gap}s between tracks\n")
        f.write(f"Tape Duration: {total_duration_minutes} minutes per side\n")
        if audio_latency > 0:
            f.write(f"Audio Latency Compensation: {audio_latency}s\n")
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