#!/usr/bin/env python3
"""
Counter Engine Module
Handles all tape counter calculation modes and calibration
"""

import os
import json
import math
import time
from datetime import datetime


def calculate_tape_counter(elapsed_seconds, counter_mode="static", counter_rate=1.0, 
                          calibration_data=None, tape_length=None, hub_radius=10.0, 
                          tape_speed=47.625, tape_thickness=0.016):
    """
    Calculate tape counter based on selected mode.
    
    Modes:
    - 'manual': Uses user-calibrated checkpoints with interpolation
    - 'auto': Physics-based simulation using reel mechanics
    - 'static': Constant linear rate
    
    Args:
        elapsed_seconds: Time elapsed in seconds
        counter_mode: Mode selection
        counter_rate: Rate for static mode
        calibration_data: Calibration data for manual mode
        tape_length: Total tape length for auto mode
        hub_radius: Hub radius for physics calculation
        tape_speed: Tape speed for physics calculation
        tape_thickness: Tape thickness for physics calculation
    
    Returns:
        Integer counter value
    """
    if counter_mode == "manual":
        return calculate_counter_manual(elapsed_seconds, calibration_data, counter_rate)
    elif counter_mode == "auto":
        return calculate_counter_auto(elapsed_seconds, counter_rate, tape_length, 
                                    hub_radius, tape_speed, tape_thickness)
    else:  # static
        return calculate_counter_static(elapsed_seconds, counter_rate)


def calculate_counter_static(elapsed_seconds, counter_rate):
    """
    Static counter: constant rate throughout tape.
    Simple linear calculation.
    """
    return int(elapsed_seconds * counter_rate)


def calculate_counter_manual(elapsed_seconds, calibration_data, fallback_rate):
    """
    Manual calibrated counter: interpolates between user-measured checkpoints.
    Uses linear interpolation between calibration points.
    """
    if calibration_data is None:
        # Fallback to static if no calibration data
        return calculate_counter_static(elapsed_seconds, fallback_rate)
    
    checkpoints = calibration_data.get('checkpoints', [])
    if not checkpoints:
        return calculate_counter_static(elapsed_seconds, fallback_rate)
    
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
    return calculate_counter_static(elapsed_seconds, fallback_rate)


def calculate_counter_auto(elapsed_seconds, counter_rate, tape_length, hub_radius, tape_speed, tape_thickness):
    """
    Auto physics-based counter: simulates tape reel mechanics.
    Counter rate varies with reel radius (faster at start, slower at end).
    """
    if tape_length is None:
        # Fallback to static if no tape length provided
        return calculate_counter_static(elapsed_seconds, counter_rate)
    
    # Calculate how much tape has been consumed
    tape_consumed = min(elapsed_seconds * tape_speed, tape_length)
    
    # Calculate take-up reel radius based on tape wound onto it
    tape_area_on_takeup = tape_consumed * tape_thickness
    takeup_radius = math.sqrt(hub_radius**2 + (tape_area_on_takeup / math.pi))
    
    # Normalize to match counter_rate at middle of tape
    mid_tape_length = tape_length / 2
    mid_tape_area = mid_tape_length * tape_thickness
    mid_radius = math.sqrt(hub_radius**2 + (mid_tape_area / math.pi))
    
    # Counter scales inversely with radius
    counter_scale = mid_radius / takeup_radius
    counter_value = elapsed_seconds * counter_rate * counter_scale
    
    return int(counter_value)


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


def calibrate_counter_wizard(target_folder="./tracks", counter_config_path="counter_calibration.json"):
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
        print(f"  ? Let tape run to {minutes} minute(s) on your stopwatch")
        
        while True:
            counter_input = input(f"  ? Enter counter value at {label}: ").strip()
            
            if not counter_input:
                print("    Skipped.")
                break
            
            try:
                counter_value = int(counter_input)
                checkpoints.append({
                    "time_seconds": time_sec,
                    "counter": counter_value,
                    "note": label
                })
                print(f"    ? Recorded: {counter_value} at {label}")
                break
            except ValueError:
                print("    Invalid input. Please enter a number or press Enter to skip.")
    
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
                print("    Skipped end-of-tape measurement.")
                break
            
            try:
                if ':' in time_input:
                    parts = time_input.split(':')
                    if len(parts) == 2:
                        minutes, seconds = map(int, parts)
                        total_seconds = minutes * 60 + seconds
                    else:
                        raise ValueError("Invalid format")
                else:
                    total_seconds = int(time_input)
                
                counter_input = input("Enter final counter value: ").strip()
                if counter_input:
                    counter_value = int(counter_input)
                    checkpoints.append({
                        "time_seconds": total_seconds,
                        "counter": counter_value,
                        "note": "End of tape"
                    })
                    print(f"    ? Recorded end: {counter_value} at {total_seconds}s")
                break
            except ValueError:
                print("    Invalid format. Use seconds (e.g., 1800) or MM:SS (e.g., 30:00)")
    
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
        print(f"    {cp['note']:20s} ? {cp['counter']:4d} (rate: {rate:.3f} counts/sec)")
    
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
    config_path = os.path.join(target_folder, counter_config_path)
    os.makedirs(os.path.dirname(config_path) if os.path.dirname(config_path) else '.', exist_ok=True)
    
    try:
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        print("\n" + "="*70)
        print(f"? Calibration saved to: {config_path}")
        print("\nTo use this calibration:")
        print(f"  python3 decprec.py --counter-mode manual --folder {target_folder}")
        print("\nYou can edit the JSON file manually if needed.")
        print("="*70 + "\n")
    except Exception as e:
        print(f"\nError saving calibration file: {e}")