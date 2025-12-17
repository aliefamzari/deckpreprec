#!/usr/bin/env python3
"""
Audio Processing Module
Handles audio normalization, level analysis, and file operations
"""

import os
import json
import subprocess
import numpy as np
from pydub import AudioSegment

# Try to import pyloudnorm for LUFS normalization
try:
    import pyloudnorm as pyln
    PYLOUDNORM_AVAILABLE = True
except ImportError:
    PYLOUDNORM_AVAILABLE = False
    pyln = None


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
                pass
        # Find first audio stream
        for s in info.get("streams", []):
            if s.get("codec_type") == "audio":
                codec = s.get("codec_name", "Unknown").upper()
                if s.get("bit_rate"):
                    bitrate = f"{int(s['bit_rate'])//1000}k"
                break
        return duration, codec, bitrate
    except Exception:
        return None, "Unknown", "Unknown"


def list_tracks(folder):
    """Scan folder for audio files and return track information."""
    tracks = []
    if not os.path.isdir(folder):
        return tracks
    for file in sorted(os.listdir(folder)):
        if file.lower().endswith(('.mp3', '.wav', '.flac', '.webm', '.m4a', '.aac', '.ogg')):
            filepath = os.path.join(folder, file)
            duration, codec, quality = get_ffprobe_info(filepath)
            if duration is None:
                print(f"Warning: Could not get duration for {file}")
                duration = 0
            tracks.append({'name': file, 'duration': duration, 'codec': codec, 'quality': quality})
    return tracks


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


def normalize_tracks(tracks, folder, normalization_method="lufs", target_lufs=-14.0, stdscr=None):
    """Normalize all tracks and return list of dicts with keys: name, path, audio, dBFS, loudness, method
    Skips normalization if normalized file exists.
    Supports both peak and LUFS normalization.
    """
    # Check if LUFS normalization is requested but not available
    if normalization_method == "lufs" and not PYLOUDNORM_AVAILABLE:
        if stdscr:
            import curses
            from .config import COLOR_RED, COLOR_YELLOW, COLOR_CYAN, COLOR_WHITE
            
            def safe_addstr(stdscr, y, x, text, attr=0):
                try:
                    max_y, max_x = stdscr.getmaxyx()
                    if y < max_y - 1 and x < max_x - 1:
                        available_width = max_x - x - 1
                        if len(text) > available_width:
                            text = text[:available_width]
                        stdscr.addstr(y, x, text, attr)
                except:
                    pass
            
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
        method = normalization_method
    
    normalized_dir = os.path.join(folder, "normalized")
    os.makedirs(normalized_dir, exist_ok=True)
    normalized_tracks = []
    
    for i, track in enumerate(tracks):
        src_path = os.path.join(folder, track['name'])
        # normalized filename includes method and target value to distinguish between normalizations
        if method == "lufs":
            norm_name = f"{track['name']}.lufs{target_lufs:+.1f}.normalized.wav"
        else:
            norm_name = f"{track['name']}.peak.normalized.wav"
        norm_path = os.path.join(normalized_dir, norm_name)
        
        if os.path.exists(norm_path):
            audio = AudioSegment.from_file(norm_path)
            if stdscr:
                import curses
                from .config import COLOR_GREEN
                
                def safe_addstr(stdscr, y, x, text, attr=0):
                    try:
                        max_y, max_x = stdscr.getmaxyx()
                        if y < max_y - 1 and x < max_x - 1:
                            available_width = max_x - x - 1
                            if len(text) > available_width:
                                text = text[:available_width]
                            stdscr.addstr(y, x, text, attr)
                    except:
                        pass
                
                safe_addstr(stdscr, 2, 0, f"Loaded cached: {track['name']}", curses.color_pair(COLOR_GREEN))
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
            import curses
            from .config import COLOR_YELLOW, COLOR_CYAN
            
            def safe_addstr(stdscr, y, x, text, attr=0):
                try:
                    max_y, max_x = stdscr.getmaxyx()
                    if y < max_y - 1 and x < max_x - 1:
                        available_width = max_x - x - 1
                        if len(text) > available_width:
                            text = text[:available_width]
                        stdscr.addstr(y, x, text, attr)
                except:
                    pass
            
            stdscr.clear()
            method_name = "LUFS" if method == "lufs" else "Peak"
            safe_addstr(stdscr, 0, 0, f"Normalizing ({method_name}) {i+1}/{len(tracks)}: {track['name']}", curses.color_pair(COLOR_YELLOW))
            safe_addstr(stdscr, 1, 0, "(This may take a few seconds per file)", curses.color_pair(COLOR_CYAN))
            if method == "lufs":
                safe_addstr(stdscr, 2, 0, f"Target: {target_lufs:+.1f} LUFS", curses.color_pair(COLOR_CYAN))
            stdscr.refresh()
        
        audio = AudioSegment.from_file(src_path)
        
        # Apply normalization based on method
        if method == "lufs" and PYLOUDNORM_AVAILABLE:
            normalized_audio = normalize_lufs(audio, target_lufs)
            loudness = calculate_loudness(normalized_audio)
        else:
            normalized_audio = audio.normalize()
            loudness = None
        
        normalized_audio.export(norm_path, format="wav")
        
        if stdscr:
            import curses
            from .config import COLOR_GREEN
            
            def safe_addstr(stdscr, y, x, text, attr=0):
                try:
                    max_y, max_x = stdscr.getmaxyx()
                    if y < max_y - 1 and x < max_x - 1:
                        available_width = max_x - x - 1
                        if len(text) > available_width:
                            text = text[:available_width]
                        stdscr.addstr(y, x, text, attr)
                except:
                    pass
            
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