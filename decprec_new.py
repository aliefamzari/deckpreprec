#!/usr/bin/env python3
"""
Enhanced Tape Deck Recording Utility
Supports both Curses and Textual interfaces
"""

import sys
import os

# Add shared modules to path
sys.path.append(os.path.join(os.path.dirname(__file__)))

from shared.config import create_argument_parser, validate_dependencies
from shared.counter_engine import calibrate_counter_wizard


def main():
    """Main entry point with UI selection"""
    
    # Create argument parser
    parser = create_argument_parser()
    parser.add_argument("--ui", type=str, default="textual", 
                       choices=["curses", "textual"],
                       help="User interface type: 'curses' (original) or 'textual' (modern) (default: textual)")
    
    args = parser.parse_args()
    
    # Handle calibration mode (works with any UI)
    if args.calibrate_counter:
        calibrate_counter_wizard(args.folder, args.counter_config)
        return
    
    # Check dependencies
    missing, optional_missing = validate_dependencies()
    if missing:
        print(f"ERROR: Missing required dependencies: {', '.join(missing)}")
        print("\nInstallation instructions:")
        print("  Ubuntu/Debian: sudo apt install ffmpeg")
        print("  Python packages: pip install pydub numpy")
        if "curses" in missing:
            print("  Windows: pip install windows-curses")
        sys.exit(1)
    
    if optional_missing:
        print(f"Warning: Optional dependencies missing: {', '.join(optional_missing)}")
        print("  For LUFS normalization: pip install pyloudnorm")
        print()
    
    # Launch selected UI
    if args.ui == "curses":
        print("???  Starting Curses interface...")
        from ui.curses_ui import main as curses_main
        curses_main()
    else:
        print("???  Starting Textual interface...")
        try:
            from ui.textual_ui import main as textual_main
            textual_main()
        except ImportError as e:
            print(f"ERROR: Textual interface not available: {e}")
            print("Install with: pip install textual rich")
            print("Falling back to curses interface...")
            from ui.curses_ui import main as curses_main
            curses_main()


if __name__ == "__main__":
    main()