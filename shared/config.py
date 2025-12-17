#!/usr/bin/env python3
"""
Configuration Management Module
Handles argument parsing, settings validation, and global constants
"""

import argparse
import os
from pydub import AudioSegment


# Color constants for curses interface
COLOR_CYAN = 1
COLOR_MAGENTA = 2
COLOR_YELLOW = 3
COLOR_GREEN = 4
COLOR_RED = 5
COLOR_BLUE = 6
COLOR_WHITE = 7


def create_argument_parser():
    """Create and configure argument parser"""
    parser = argparse.ArgumentParser(description="Audio Player for Tape Recording")
    parser.add_argument("--track-gap", type=int, default=5, 
                       help="Gap between tracks in seconds (default: 5)")
    parser.add_argument("--duration", type=int, default=30, 
                       help="Maximum tape duration in minutes per side (default: 30 - C60 cassette side)")
    parser.add_argument("--folder", type=str, default="./tracks", 
                       help="Folder with audio tracks")
    parser.add_argument("--counter-rate", type=float, default=1.0, 
                       help="Tape counter increments per second for static mode (default: 1.0)")
    parser.add_argument("--counter-mode", type=str, default="static", 
                       choices=["manual", "auto", "static"],
                       help="Counter calculation mode: 'manual' (calibrated), 'auto' (physics), 'static' (constant rate) (default: static)")
    parser.add_argument("--calibrate-counter", action="store_true", 
                       help="Run interactive counter calibration wizard")
    parser.add_argument("--counter-config", type=str, default="counter_calibration.json", 
                       help="Path to counter calibration config file for manual mode (default: counter_calibration.json)")
    parser.add_argument("--leader-gap", type=int, default=10, 
                       help="Leader gap before first track in seconds (default: 10)")
    parser.add_argument("--normalization", type=str, default="lufs", choices=["peak", "lufs"], 
                       help="Normalization method: 'peak' or 'lufs' (default: lufs)")
    parser.add_argument("--target-lufs", type=float, default=-14.0, 
                       help="Target LUFS level for LUFS normalization (default: -14.0)")
    parser.add_argument("--audio-latency", type=float, default=0.0, 
                       help="Audio latency compensation in seconds for VU meter sync (default: 0.0, try 0.1-0.5 if audio lags behind meters)")
    parser.add_argument("--tape-type", type=str, default="Type I", 
                       choices=["Type I", "Type II", "Type III", "Type IV"],
                       help="Cassette tape type: Type I (Normal/Ferric), Type II (Chrome/High Bias), Type III (Ferrochrome), Type IV (Metal) (default: Type I)")
    parser.add_argument("--ffmpeg-path", type=str, default="/usr/bin/ffmpeg", 
                       help="Path to ffmpeg binary (default: /usr/bin/ffmpeg)")
    parser.add_argument("--deck-profile", type=str, default=None, 
                       help="Path to deck profile preset JSON (overrides most options)")
    
    return parser


class TapeConfig:
    """Configuration container for tape deck settings"""
    
    def __init__(self, args=None):
        if args is None:
            parser = create_argument_parser()
            args = parser.parse_args()
        
        # Apply deck profile if specified
        if args.deck_profile:
            from .deck_profiles import load_deck_profile
            args = load_deck_profile(args.deck_profile, args)
        
        # Core settings
        self.track_gap_seconds = args.track_gap
        self.total_duration_minutes = args.duration
        self.target_folder = args.folder
        self.counter_rate = args.counter_rate
        self.counter_mode = args.counter_mode
        self.counter_config_path = args.counter_config
        self.leader_gap_seconds = args.leader_gap
        self.normalization_method = args.normalization
        self.target_lufs = args.target_lufs
        self.audio_latency = args.audio_latency
        self.tape_type = args.tape_type
        self.ffmpeg_path = args.ffmpeg_path
        self.calibrate_counter = getattr(args, 'calibrate_counter', False)
        
        # Derived settings
        self.tape_duration = self.total_duration_minutes * 60  # seconds
        
        # Tape reel physics constants for realistic counter behavior
        self.tape_thickness = 0.016  # mm - standard cassette tape thickness
        self.hub_radius = 10.0  # mm - radius of empty hub/spool
        self.tape_speed = 47.625  # mm/s - standard cassette speed (1 7/8 ips)
        self.tape_length = self.total_duration_minutes * 60 * self.tape_speed  # Total tape length in mm
        
        # Initialize environment
        self._setup_environment()
        
        # Calibration data (loaded if needed)
        self.calibration_data = None
    
    def _setup_environment(self):
        """Setup environment variables and paths"""
        # Add /usr/sbin to PATH for ffmpeg/ffprobe/ffplay if present
        os.environ["PATH"] += os.pathsep + "/usr/sbin"
        
        # Add ffmpeg directory to PATH (for ffprobe/ffplay) and set converter
        ffmpeg_dir = os.path.dirname(self.ffmpeg_path)
        if ffmpeg_dir and ffmpeg_dir not in os.environ["PATH"]:
            os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ["PATH"]
        AudioSegment.converter = self.ffmpeg_path
    
    def load_calibration_data(self):
        """Load calibration data if in manual mode"""
        if self.counter_mode == "manual":
            from .counter_engine import load_calibration_config
            config_path = os.path.join(self.target_folder, self.counter_config_path)
            self.calibration_data = load_calibration_config(config_path)
            
            if self.calibration_data is None:
                print(f"\nERROR: Manual counter mode requires calibration file.")
                print(f"File not found: {config_path}")
                print("Run with --calibrate-counter to create calibration file.\n")
                return False
            
            print(f"\n? Loaded calibration from: {config_path}")
            print(f"  Deck: {self.calibration_data.get('deck_model', 'Unknown')}")
            print(f"  Tape: {self.calibration_data.get('tape_type', 'Unknown')}")
            print(f"  Checkpoints: {len(self.calibration_data.get('checkpoints', []))}")
            print(f"  Date: {self.calibration_data.get('calibration_date', 'Unknown')}\n")
        
        return True
    
    def calculate_tape_counter(self, elapsed_seconds):
        """Calculate tape counter value for given elapsed time"""
        from .counter_engine import calculate_tape_counter
        
        return calculate_tape_counter(
            elapsed_seconds=elapsed_seconds,
            counter_mode=self.counter_mode,
            counter_rate=self.counter_rate,
            calibration_data=self.calibration_data,
            tape_length=self.tape_length,
            hub_radius=self.hub_radius,
            tape_speed=self.tape_speed,
            tape_thickness=self.tape_thickness
        )
    
    def get_mode_display_name(self):
        """Get human-readable counter mode name"""
        mode_names = {
            "manual": "Manual Calibrated",
            "auto": "Auto Physics Simulation",
            "static": "Static Linear Rate"
        }
        return mode_names.get(self.counter_mode, self.counter_mode)
    
    def validate_settings(self):
        """Validate configuration settings"""
        errors = []
        warnings = []
        
        # Check tape duration
        if self.total_duration_minutes not in [30, 45, 60]:
            warnings.append(f"Unusual tape duration: {self.total_duration_minutes} minutes. Common values: 30 (C60), 45 (C90), 60 (C120)")
        
        # Check counter rate for static mode
        if self.counter_mode == "static" and not (0.5 <= self.counter_rate <= 5.0):
            warnings.append(f"Unusual counter rate: {self.counter_rate}. Typical range: 0.8-2.0 counts/second")
        
        # Check LUFS target
        if self.normalization_method == "lufs" and not (-30 <= self.target_lufs <= -6):
            warnings.append(f"Unusual LUFS target: {self.target_lufs}. Broadcast standard: -23 LUFS, Music: -14 LUFS")
        
        # Check audio latency
        if self.audio_latency > 1.0:
            warnings.append(f"High audio latency compensation: {self.audio_latency}s. Typical range: 0.1-0.5s")
        
        return errors, warnings


def validate_dependencies():
    """Check if required dependencies are available"""
    missing = []
    
    # Check ffmpeg tools
    import subprocess
    for tool in ['ffmpeg', 'ffprobe', 'ffplay']:
        try:
            subprocess.run([tool, '-version'], 
                         stdout=subprocess.DEVNULL, 
                         stderr=subprocess.DEVNULL, 
                         check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            missing.append(tool)
    
    # Check Python libraries
    try:
        import pydub
    except ImportError:
        missing.append('pydub')
    
    try:
        import numpy
    except ImportError:
        missing.append('numpy')
    
    try:
        import curses
    except ImportError:
        missing.append('curses (try: pip install windows-curses on Windows)')
    
    # Check optional libraries
    optional_missing = []
    try:
        import pyloudnorm
    except ImportError:
        optional_missing.append('pyloudnorm (required for LUFS normalization)')
    
    return missing, optional_missing