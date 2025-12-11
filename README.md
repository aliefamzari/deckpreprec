# 📼 Retro 80s Tape Deck Recording CLI

A nostalgic cassette tape recording utility with authentic 80s aesthetics. Perfect for audiophiles recording curated playlists to physical cassette tapes with professional-quality preparation and timing control.

```
  ╔═══════════════════════════════╗
  ║  ┌─────┐         ┌─────┐      ║
  ║  │ ∞∞∞ │    A    │ ∞∞∞ │      ║
  ║  └─────┘         └─────┘      ║
  ╚═══════════════════════════════╝
```

## ✨ Features

- 🎨 **Retro 80s UI** - Neon colors, ASCII art, and authentic cassette tape aesthetics
- 🔊 **Audio Normalization** - Consistent volume levels across all tracks (cached for speed)
- 📟 **4-Digit Tape Counter** - Digital counter with configurable rate matching your deck
- 📊 **Real-Time VU Meters** - Segmented block displays with actual audio waveform analysis (L/R channels)
- 🎚️ **Adaptive Level Scaling** - 95th percentile RMS normalization prevents constant peaking
- 📼 **Leader Gap Support** - Configurable pre-roll for non-magnetic leader tape
- ⏱️ **Duration Management** - Ensures tracks fit within cassette tape limits
- 🎵 **Track Preview** - Listen before recording with visual indicators
- 📝 **Timestamped Tracklists** - Creates unique reference files with counter positions
- ⏸️ **Configurable Track Gaps** - Set silence between tracks
- 🎬 **10-Second Prep Countdown** - Time to press record on your deck

## 📋 Requirements

- Python 3.12+ (Python 3.13 not supported due to pydub compatibility)
- FFmpeg, FFprobe, FFplay
- pydub library
- curses (windows-curses on Windows)

## 🚀 Installation

### Option 1: Linux (Recommended)

#### Arch Linux / Manjaro
```bash
# Install dependencies
sudo pacman -S python ffmpeg

# Clone or navigate to project
cd deckpreprec

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install Python packages
pip install pydub

# Run the application
python decprec.py
```

#### Ubuntu / Debian
```bash
# Install dependencies
sudo apt update
sudo apt install python3 python3-pip python3-venv ffmpeg

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python packages
pip install pydub

# Run the application
python decprec.py
```

### Option 2: Windows (WSL - Recommended)

Running in WSL provides the best experience and maintains Linux compatibility:

```powershell
# Start WSL (Ubuntu or Arch)
wsl -d archlinux

# Navigate to project
cd "/mnt/c/Users/YourUsername/path/to/deckpreprec"

# Follow Linux installation steps above
```

See [WSL_SETUP.md](WSL_SETUP.md) for detailed WSL instructions.

### Option 3: Windows (Native - Limited Support)

**⚠️ Note:** Script is designed for Linux. Windows native support is limited.

```powershell
# Install Python 3.12 (NOT 3.13)
# Download from: https://www.python.org/downloads/

# Install FFmpeg
winget install --id Gyan.FFmpeg -e
# OR download from: https://www.gyan.dev/ffmpeg/builds/

# Create virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# Install dependencies
pip install windows-curses pydub

# Update script paths to point to your FFmpeg installation
# Edit line ~36 in decprec.py to point to your ffmpeg.exe location

# Run the application
python decprec.py
```

## 📖 Usage

### Basic Usage

```bash
python decprec.py
```

### Advanced Options

```bash
python decprec.py --folder ./tracks --track-gap 5 --duration 60 --counter-rate 1.0 --leader-gap 10
```

**Arguments:**
- `--folder PATH` - Audio tracks directory (default: `./tracks`)
- `--track-gap N` - Gap between tracks in seconds (default: `5`)
- `--duration N` - Maximum tape duration in minutes (default: `60`)
- `--counter-rate N` - Counter increments per second (default: `1.0`)
- `--leader-gap N` - Leader gap before first track in seconds (default: `10`)

### Supported Audio Formats

MP3, WAV, FLAC, WebM, M4A, AAC, OGG

### Folder Structure

```
deckpreprec/
├── decprec.py
├── tracks/                    # Your audio files go here
│   ├── song1.mp3
│   ├── song2.wav
│   ├── song3.flac
│   ├── normalized/            # Auto-generated normalized files
│   │   ├── song1.mp3.normalized.wav
│   │   └── song2.wav.normalized.wav
│   ├── deck_tracklist_20241211_143022.txt  # Timestamped tracklists
│   └── deck_tracklist_20241211_151545.txt
├── venv/                      # Virtual environment
└── README.md
```

## 🎹 Keyboard Controls

### Main Menu
| Key | Action |
|-----|--------|
| `↑` / `↓` | Navigate tracks |
| `Space` | Select/deselect track |
| `P` | Preview track |
| `X` | Stop preview |
| `Enter` | Normalize and start recording |
| `Q` | Quit application |

### Recording Mode
| Key | Action |
|-----|--------|
| `Q` | Return to main menu |

## 🎯 Workflow

1. **Launch Application**
   ```bash
   python decprec.py
   ```

2. **Select Tracks**
   - Navigate with arrow keys
   - Press `Space` to select/deselect
   - Preview with `P` key
   - Monitor total duration

3. **Start Recording Process**
   - Press `Enter` when tracks are selected
   - Wait for normalization (cached for subsequent runs)
   - Review track summary

4. **Deck Preparation**
   - Press `Enter` to start 10-second countdown
   - Set your cassette deck to RECORD mode
   - Wait for countdown to complete

5. **Recording**
   - Leader gap countdown (default 10s for non-magnetic tape)
   - Tape counter starts at 0000 during leader gap
   - First track starts after leader gap
   - Monitor real-time VU meters (L/R channels)
   - Watch tape counter and track progress
   - Timestamped tracklist saved automatically

6. **Reference Your Tracklist**
   - Check `tracks/deck_tracklist_YYYYMMDD_HHMMSS.txt` for:
     - Session timestamp
     - Leader gap counter range
     - Track start/end times
     - Counter positions
     - Track durations

## 🎨 80s Aesthetic Features

- **Neon Color Scheme:** Cyan, magenta, yellow, green
- **ASCII Cassette Art:** Authentic tape graphics in menu and recording mode
- **Digital Counter Display:** 4-digit LED-style counter with real-time updates
- **Segmented VU Meters:** Block character displays (██) with spacing between L/R channels
- **Dynamic Color Zones:** White (0-85%) → Red (85-100%) peak indicators
- **Waveform Analysis:** Pre-computed RMS levels with 50ms chunk resolution
- **Retro Box Drawing:** Double-line borders and frames
- **Blinking Countdown:** 80s digital clock effect
- **Track Preview Indicator:** Musical note (♪) symbol for playing tracks

## 📝 Configuration Tips

### Tape Counter Rate

Match your deck's counter behavior:
```bash
# If counter reaches 60 after 1 minute
python decprec.py --counter-rate 1.0

# If counter reaches 120 after 1 minute
python decprec.py --counter-rate 2.0
```

### Leader Gap Configuration

Adjust leader gap for non-magnetic tape at beginning:
```bash
# Short leader (5 seconds)
python decprec.py --leader-gap 5

# Standard leader (10 seconds - default)
python decprec.py --leader-gap 10

# Long leader (15 seconds)
python decprec.py --leader-gap 15
```

### Common Tape Lengths

```bash
# C60 cassette (30 minutes per side)
python decprec.py --duration 30

# C90 cassette (45 minutes per side)
python decprec.py --duration 45

# C120 cassette (60 minutes per side)
python decprec.py --duration 60
```

## 🐛 Troubleshooting

### Python 3.13 Compatibility Error
```
ModuleNotFoundError: No module named 'audioop'
```
**Solution:** Use Python 3.12 or earlier. Python 3.13 removed the `audioop` module.

### FFmpeg Not Found
```
RuntimeWarning: Couldn't find ffmpeg or avconv
```
**Solution:** Install FFmpeg and ensure it's in your PATH.

### No Audio Tracks Found
**Solution:** Place audio files in the `tracks/` folder.

### Curses Issues on Windows
**Solution:** Use WSL or install `windows-curses`:
```bash
pip install windows-curses
```

## 📄 License

MIT License

## 🤝 Contributing

Contributions welcome! Feel free to submit issues or pull requests.

## 🙏 Acknowledgments

- Inspired by classic tape deck recording workflows
- 80s home recording studio aesthetics
- Mixtape culture and physical media preservation

---

**Made with 💜 for cassette tape enthusiasts**
