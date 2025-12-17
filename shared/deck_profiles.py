#!/usr/bin/env python3
"""
Deck Profiles and Tape Type Management Module
Handles deck configuration presets and tape type specifications
"""

import os
import json
import sys


def get_tape_type_info(tape_type):
    """Get detailed information about cassette tape type"""
    tape_info = {
        "Type I": {
            "name": "Normal (Ferric Oxide)",
            "material": "Ferric Oxide",
            "color": "Brown",
            "sound": "Good bass, lacks high-frequency detail",
            "bias": "Standard (120us EQ)",
            "notches": "Standard write-protect only"
        },
        "Type II": {
            "name": "Chrome/High Bias", 
            "material": "Chromium Dioxide (CrO2)",
            "color": "Dark brown/black",
            "sound": "Crisp highs, better dynamics",
            "bias": "High bias (70us EQ)",
            "notches": "Extra detection notches"
        },
        "Type III": {
            "name": "Ferrochrome (Rare)",
            "material": "Ferric + Chrome mix",
            "color": "Varies",
            "sound": "Type I bass + Type II highs",
            "bias": "High bias (70us EQ)", 
            "notches": "Distinct pattern"
        },
        "Type IV": {
            "name": "Metal (Pure Metal)",
            "material": "Pure metal particles",
            "color": "Solid black",
            "sound": "Highest output, best clarity",
            "bias": "Metal bias (70us EQ)",
            "notches": "Third center notch set"
        }
    }
    return tape_info.get(tape_type, tape_info["Type I"])


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
        'audio_latency': 'audio_latency',
        'ffmpeg_path': 'ffmpeg_path',
        'tape_duration': 'duration'  # Allow tape_duration as alias for duration
    }
    
    for k, v in profile.items():
        if k in mapping:
            setattr(args, mapping[k], v)
    
    print(f"\n? Loaded deck profile: {profile_path}")
    if 'deck_model' in profile:
        print(f"  Deck: {profile['deck_model']}")
    if 'tape_type' in profile:
        print(f"  Tape: {profile['tape_type']}")
    print()
    return args


def create_sample_deck_profiles():
    """Create sample deck profile files for reference"""
    profiles_dir = "deck_profiles"
    os.makedirs(profiles_dir, exist_ok=True)
    
    # AIWA AD-F780 (Manual calibrated, Type II optimized)
    aiwa_profile = {
        "deck_model": "AIWA AD-F780",
        "tape_type": "Type II",
        "tape_duration": 45,
        "counter_mode": "manual",
        "counter_config": "counter_calibration_aiwa.json",
        "leader_gap": 10,
        "track_gap": 5,
        "normalization": "lufs",
        "target_lufs": -14.0,
        "audio_latency": 0.2,
        "ffmpeg_path": "/usr/bin/ffmpeg"
    }
    
    # Sony TC-WE475 (Static counter, dual-well)
    sony_profile = {
        "deck_model": "Sony TC-WE475",
        "tape_type": "Type I",
        "tape_duration": 30,
        "counter_mode": "static",
        "counter_rate": 1.42,
        "leader_gap": 8,
        "track_gap": 4,
        "normalization": "peak",
        "audio_latency": 0.1,
        "ffmpeg_path": "/usr/bin/ffmpeg"
    }
    
    # Pioneer CT-R305 (Basic deck, Type I)
    pioneer_profile = {
        "deck_model": "Pioneer CT-R305",
        "tape_type": "Type I",
        "tape_duration": 30,
        "counter_mode": "static",
        "counter_rate": 1.35,
        "leader_gap": 8,
        "track_gap": 4,
        "normalization": "peak",
        "audio_latency": 0.0,
        "ffmpeg_path": "/usr/bin/ffmpeg"
    }
    
    # Technics RS-X205 (Metal capable, Type IV)
    technics_profile = {
        "deck_model": "Technics RS-X205",
        "tape_type": "Type IV",
        "tape_duration": 45,
        "counter_mode": "auto",
        "counter_rate": 1.5,
        "leader_gap": 12,
        "track_gap": 6,
        "normalization": "lufs",
        "target_lufs": -12.0,
        "audio_latency": 0.15,
        "ffmpeg_path": "/usr/bin/ffmpeg"
    }
    
    profiles = [
        ("aiwa_adf780.json", aiwa_profile),
        ("sony_tcwe475.json", sony_profile),
        ("pioneer_ctr305.json", pioneer_profile),
        ("technics_rsx205.json", technics_profile)
    ]
    
    for filename, profile_data in profiles:
        profile_path = os.path.join(profiles_dir, filename)
        if not os.path.exists(profile_path):
            with open(profile_path, 'w') as f:
                json.dump(profile_data, f, indent=2)
            print(f"Created sample profile: {profile_path}")
    
    return profiles_dir


def validate_deck_profile(profile_data):
    """Validate deck profile data for completeness and correctness"""
    errors = []
    warnings = []
    
    # Required fields
    recommended_fields = [
        'deck_model', 'tape_type', 'counter_mode', 'normalization'
    ]
    
    for field in recommended_fields:
        if field not in profile_data:
            warnings.append(f"Missing recommended field: {field}")
    
    # Validate counter mode requirements
    counter_mode = profile_data.get('counter_mode', 'static')
    if counter_mode == 'manual' and 'counter_config' not in profile_data:
        errors.append("Manual counter mode requires 'counter_config' field")
    if counter_mode == 'static' and 'counter_rate' not in profile_data:
        warnings.append("Static counter mode should include 'counter_rate' field")
    
    # Validate tape type
    valid_tape_types = ['Type I', 'Type II', 'Type III', 'Type IV']
    tape_type = profile_data.get('tape_type', 'Type I')
    if tape_type not in valid_tape_types:
        errors.append(f"Invalid tape_type: {tape_type}. Valid options: {valid_tape_types}")
    
    # Validate normalization
    valid_norm_methods = ['peak', 'lufs']
    norm_method = profile_data.get('normalization', 'lufs')
    if norm_method not in valid_norm_methods:
        errors.append(f"Invalid normalization: {norm_method}. Valid options: {valid_norm_methods}")
    
    # Validate LUFS target
    if norm_method == 'lufs':
        target_lufs = profile_data.get('target_lufs')
        if target_lufs is None:
            warnings.append("LUFS normalization should include 'target_lufs' field")
        elif not (-30 <= target_lufs <= -6):
            warnings.append(f"Unusual target_lufs value: {target_lufs}. Typical range: -23 to -14 LUFS")
    
    return errors, warnings