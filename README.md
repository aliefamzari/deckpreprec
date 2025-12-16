# 📼 Tape Deck/Prep/Record

A nostalgic cassette tape recording utility with. Perfect for mixtapes nerd curated playlists to physical cassette tapes with professional-quality preparation and timing control.

```
 ___________________________________________
|  _______________________________________  |
| / .-----------------------------------. \ |
| | | /\ :                        90 min| | |
| | |/--\:....................... NR [ ]| | |
| | `-----------------------------------' | |
| |      //-\\   |         |   //-\\      | |
| |     ||( )||  |_________|  ||( )||     | |
| |      \\-//   :....:....:   \\-//      | |
| |       _ _ ._  _ _ .__|_ _.._  _       | |
| |      (_(_)| |(_(/_|  |_(_||_)(/_      | |
| |               low noise   |           | |
| `______ ____________________ ____ ______' |
|        /    []             []    \        |
|       /  ()                   ()  \       |
!______/_____________________________\______!
```

## ✨ Features

- 🎨 **Retro 80s UI** - Neon colors, clean ASCII cassette art, and authentic tape deck aesthetics
- 🔊 **Audio Normalization** - Consistent volume levels across all tracks (cached for speed)
  - Supports both **Peak** and **LUFS** normalization methods
  - LUFS normalization for broadcast-standard perceived loudness
  - Configurable target LUFS level (default: -14.0 LUFS)
- 📟 **Multi-Mode Tape Counter** - Large 4-digit counter with three calculation modes:
  - **Manual Calibrated**: Uses your actual tape deck measurements with checkpoint interpolation
  - **Auto Physics**: Realistic reel simulation (non-linear rate changes)
  - **Static Linear**: Constant rate throughout tape
- 📊 **Real-Time VU Meters** - Wide 50-character segmented block displays with actual audio waveform analysis (L/R channels)
  - **Persistent display** with dB scale (-60 to 0 dB) always visible
  - Consistent 50-character width across all screens
  - Live audio level tracking during playback and recording
- 🎚️ **Adaptive Level Scaling** - 95th percentile RMS normalization prevents constant peaking
- 📼 **Leader Gap Support** - Configurable pre-roll for non-magnetic leader tape
- ⏱️ **Duration Management** - Ensures tracks fit within cassette tape limits with visual warning
- 🎵 **Advanced Track Preview** - VCR-style playback with seek, play/pause, and track switching
- ⏪ **Seek Controls** - Rewind/forward 10 seconds during playback
- 🎮 **Smart Navigation** - Browse tracks (stops at first/last, no wraparound) while music continues in background
- 📝 **Timestamped Tracklists** - Creates unique reference files with counter positions
- ⏸️ **Configurable Track Gaps** - Set silence between tracks
- 🎬 **Large Digital Countdown** - Massive 7-segment style countdown with recording reminder
- 📈 **Visual Progress Bars** - Real-time progress indicators for both tracks and total recording time
- 🏷️ **Descriptive Labels** - Clear, self-explanatory UI labels (Track Gap, Tape Leader Gap, Total Recording Time, Tape Length)
- 🔧 **Audio Latency Compensation** - Adjustable sync between VU meters and audio output for perfect timing
- 📂 **Folder Path Display** - Shows current working folder in track list header
- 🔴 **Capacity Warning** - Red blinking alert when track selection exceeds tape length

## 📋 Requirements

- Python 3.12+ (Python 3.13 not supported due to pydub compatibility)
- FFmpeg, FFprobe, FFplay
- pydub library
- curses (windows-curses on Windows)

## 🚀 Installation

### Step 0: Get the Code

First, download or clone the repository:

**Option A: Clone with Git (Recommended)**
```bash
# Install git if you don't have it
# Ubuntu/Debian: sudo apt install git
# Arch/Manjaro: sudo pacman -S git

# Clone the repository
git clone https://github.com/yourusername/deckpreprec.git
cd deckpreprec
```

**Option B: Download ZIP**
1. Click the green "Code" button on GitHub
2. Select "Download ZIP"
3. Extract the ZIP file
4. Open terminal and navigate to the extracted folder:
   ```bash
   cd path/to/deckpreprec
   ```

---

### Option 1: Linux (Recommended)

#### Arch Linux / Manjaro
```bash
# Install dependencies
sudo pacman -S python ffmpeg

# Navigate to project (if not already there)
cd deckpreprec

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install Python packages
pip install pydub pyloudnorm numpy

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
pip install pydub pyloudnorm numpy

# Run the application
python decprec.py
```

### Option 2: Windows (WSL - Recommended)

Running in WSL provides the best experience and maintains Linux compatibility:

```powershell
# First, get the code (choose one method):

# Method A: Clone in WSL
wsl
git clone https://github.com/yourusername/deckpreprec.git
cd deckpreprec

# Method B: Access downloaded files from Windows
# If you downloaded/extracted to C:\Users\YourUsername\Downloads\deckpreprec
wsl
cd "/mnt/c/Users/YourUsername/Downloads/deckpreprec"

# Then follow Linux installation steps above
```

See [WSL_SETUP.md](WSL_SETUP.md) for detailed WSL instructions.

### Option 3: Windows (Native - Limited Support)

**⚠️ Note:** Script is designed for Linux. Windows native support is limited.

```powershell
# First, download the code:
# Visit GitHub repository and click "Code" > "Download ZIP"
# Extract to a folder like C:\Users\YourUsername\deckpreprec

# Open PowerShell and navigate to the folder
cd C:\Users\YourUsername\deckpreprec

# Install Python 3.12 (NOT 3.13)
# Download from: https://www.python.org/downloads/

# Install FFmpeg
winget install --id Gyan.FFmpeg -e
# OR download from: https://www.gyan.dev/ffmpeg/builds/

# Create virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# Install dependencies
pip install windows-curses pydub pyloudnorm numpy

# Run the application (must specify ffmpeg.exe location on Windows)
# Find where FFmpeg is installed (common locations):
# - C:\ffmpeg\bin\ffmpeg.exe
# - C:\Program Files\ffmpeg\bin\ffmpeg.exe
# - C:\Users\YourUsername\ffmpeg\bin\ffmpeg.exe

python decprec.py --ffmpeg-path "C:\ffmpeg\bin\ffmpeg.exe"
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
- `--duration N` - Maximum tape duration in minutes (default: `30`)
- `--counter-mode MODE` - Counter calculation mode: `manual`, `auto`, or `static` (default: `static`)
- `--counter-rate N` - Counter increments per second for static mode (default: `1.0`)
- `--counter-config PATH` - Path to counter calibration file for manual mode (default: `counter_calibration.json`)
- `--calibrate-counter` - Run interactive counter calibration wizard
- `--leader-gap N` - Leader gap before first track in seconds (default: `10`)
- `--normalization METHOD` - Normalization method: `peak` or `lufs` (default: `lufs`)
- `--target-lufs N` - Target LUFS level for LUFS normalization (default: `-14.0`)
- `--audio-latency N` - Audio latency compensation in seconds for VU meter sync (default: `0.0`, try `0.1-0.5` if audio lags behind meters)
- `--ffmpeg-path PATH` - Path to ffmpeg binary (default: `/usr/bin/ffmpeg`). Use this on Windows to point to your `ffmpeg.exe` location

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
│   │   ├── song1.mp3.lufs.normalized.wav    # LUFS normalized
│   │   ├── song1.mp3.peak.normalized.wav    # Peak normalized
│   │   └── song2.wav.lufs.normalized.wav
│   ├── deck_tracklist_20241211_143022.txt  # Timestamped tracklists
│   └── deck_tracklist_20241211_151545.txt
├── venv/                      # Virtual environment
├── counter_calibration.json   # Your tape deck calibration (manual mode)
└── README.md
```

## 📟 Tape Counter Calibration

The script supports three counter modes to match your specific tape deck:

### Counter Modes

#### 1. **Static Mode (Default)** - Constant Rate
```bash
python decprec.py --counter-mode static --counter-rate 1.408
```
- Counter increments at a constant rate throughout the tape
- Simplest and most common counter type
- Best for decks with linear/constant counters
- Use `--counter-rate` to set your deck's rate

**Measuring Your Counter Rate:**
1. Reset deck counter to 000
2. Press RECORD and start stopwatch
3. Let it run for 15-30 minutes (longer = more accurate)
4. Note: counter value and time in seconds
5. Calculate: `counter_rate = counter / time_seconds`

Example: 2534 counter at 30 minutes (1800s) → rate = 1.408

---

#### 2. **Manual Calibrated Mode** - Uses Your Deck's Actual Behavior
```bash
# Step 1: Calibrate your deck (one-time setup)
python decprec.py --calibrate-counter

# Step 2: Use calibrated counter
python decprec.py --counter-mode manual
```

This mode uses checkpoints you measure from your actual tape deck and interpolates between them for accuracy throughout the entire tape.

**Calibration Process:**
1. Insert blank tape (C60 or C90)
2. Reset deck counter to 000
3. Press RECORD and use stopwatch
4. Note counter at these checkpoints:
   - 1 minute (60s)
   - 5 minutes (300s)
   - 20 minutes (1200s)
   - 30 minutes (1800s)
   - Optional: End of tape side
5. Enter values in the wizard
6. Configuration saved to `counter_calibration.json`

**Example Calibration Data:**
```json
{
  "tape_type": "C60",
  "deck_model": "Sony TC-D5M",
  "checkpoints": [
    {"time_seconds": 60, "counter": 85},
    {"time_seconds": 300, "counter": 422},
    {"time_seconds": 1200, "counter": 1690},
    {"time_seconds": 1800, "counter": 2534}
  ]
}
```

**Benefits:**
- Most accurate for your specific deck
- Handles non-linear counter behavior
- One-time calibration, reusable forever
- Can calibrate multiple decks with different config files

---

#### 3. **Auto Physics Mode** - Simulates Tape Reel Mechanics
```bash
python decprec.py --counter-mode auto --counter-rate 1.408
```
- Simulates how counter changes with reel radius
- Counter runs faster at start (small radius), slower at end (large radius)
- Based on cassette tape physics:
  - Tape speed: 47.625 mm/s (1⅞ ips)
  - Hub radius: 10mm
  - Tape thickness: 0.016mm
- Useful for decks with mechanically-driven counters

**When to use each mode:**
- **Static**: Your deck counter runs at constant speed (most common)
- **Manual**: You want maximum accuracy for your specific deck
- **Auto**: Your deck's counter is mechanically connected to the reel rotation

---

### Advanced: Multiple Deck Calibrations

Create separate calibration files for different decks:
```bash
# Calibrate deck A
python decprec.py --calibrate-counter --counter-config deck_a.json

# Calibrate deck B
python decprec.py --calibrate-counter --counter-config deck_b.json

# Use specific deck
python decprec.py --counter-mode manual --counter-config deck_a.json
```

## 🎹 Keyboard Controls

### Main Menu (Track Selection)
| Key | Action |
|-----|--------|
| `↑` / `↓` / `K` / `J` | Navigate tracks (stops at first/last, keeps current track playing) |
| `Space` | Select/deselect track for recording |
| `C` | Clear all selected tracks |
| `P` | Play/Pause track (toggle playback) |
| `X` | Stop playback and reset position |
| `←` / `→` | Rewind/Forward 10 seconds (while playing) |
| `[` / `]` | Jump to previous/next track and play (stops at boundaries) |
| `Enter` | Start recording process |
| `Q` | Quit application |

### Normalization Preview Mode
| Key | Action |
|-----|--------|
| `↑` / `↓` / `K` / `J` | Navigate tracks (keeps current track playing) |
| `P` | Play/Pause track (toggle playback) |
| `X` | Stop playback and reset position |
| `←` / `→` | Rewind/Forward 10 seconds (while playing) |
| `[` / `]` | Jump to previous/next track and play |
| `Enter` | Proceed to recording |
| `Q` | Return to main menu |

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
   - Navigate with arrow keys (↑/↓)
   - Preview tracks with `P` key (play/pause toggle)
   - **VU meters display at top with dB scale** - always visible
   - Use `←`/`→` to rewind/forward 10 seconds while playing
   - Use `[`/`]` to quickly jump between tracks
   - Press `Space` to select/deselect tracks for recording
   - Monitor total duration and folder path in header
   - Real-time playback position displayed

3. **Start Recording Process**
   - Press `Enter` when tracks are selected
   - Wait for normalization (LUFS or Peak method, cached for subsequent runs)
   - Review normalized tracks with level info (LUFS/dBFS values)
   - **Preview with persistent VU meters** showing audio levels in real-time
   - Full playback controls available during preview

4. **Deck Preparation**
   - Press `Enter` to start **large digital 7-segment countdown**
   - **Important reminder displayed:** "PRESS RECORD ON YOUR DECK WHEN COUNTDOWN HITS 0"
   - Prepare your cassette deck while countdown runs
   - Watch the massive digital countdown numbers
   - Can cancel with `Q` if needed

5. **Recording**
   - **Press RECORD on your deck when countdown hits 0**
   - Leader gap countdown (default 10s for non-magnetic tape)
   - Large digital tape counter displayed prominently
   - Counter starts incrementing from 0000 during leader gap
   - First track starts after leader gap
   - **Monitor real-time VU meters** (50-character width, L/R channels with dB scale)
   - **Visual progress bars** for current track and total recording time
   - Watch digital tape counter and track progress
   - Timestamped tracklist saved automatically

6. **Reference Your Tracklist**
   - Check `tracks/deck_tracklist_YYYYMMDD_HHMMSS.txt` for:
     - Session timestamp
     - Leader gap counter range
     - Track start/end times
     - Counter positions
     - Track durations

## 📸 Screenshots

### Main Menu - Track Selection
![Main Menu](images/MainMenu.png)
*Browse and select tracks. Preview is also available*

### Track Preview and Normalization summary
![Track Preview](images/Normalization.png)
*Preview tracks order and normalization value*

### Prep Countdown
![Prep Countdown](images/Countdown.png)
*10-second countdown*

### Leader Gap Countdown
![Leader gap Countdown](images/LeaderGap.png)
*leader gap countdown to pass the record head*

### Recording Mode with VU Meters
![Recording Mode](images/DecRecMode.png)
*Real-time VU meters, tape counter, and track progress*

### Tracklist Output
![Recording Mode](images/Tracklist_output.png)
*Real-time VU meters, tape counter, and track progress*

## 🎨 UI Design Details

- **Neon Color Scheme:** Cyan, magenta, yellow, green, red, white
- **Clean ASCII Cassette Art:** Modern, detailed tape graphics with reels and label area
- **Physics-Based Tape Counter:** Large 4-digit display with realistic reel behavior
  - 7-line tall digital 7-segment style digits for excellent visibility
  - Models actual cassette tape reel physics (non-linear counter rate)
  - Counter driven by take-up reel rotation simulation
  - Faster counting at tape beginning (small reel), slower at end (large reel)
  - Matches real-world tape deck behavior
  - "[TAPE COUNTER]" label for clarity
- **Wide Segmented VU Meters:** 50-character block displays (██) with full dB scale (-60 to 0 dB)
  - Consistent width across all screens (normalization, main menu, recording)
  - Always visible during playback and recording
  - Real-time stereo channel monitoring (L/R)
  - Color-coded zones for visual feedback
- **Dynamic Color Zones:** White (0-85%) → Red (85-100%) peak indicators
- **Waveform Analysis:** Pre-computed RMS levels with 50ms chunk resolution
- **Retro Box Drawing:** Double-line borders and frames (╔═╗╚╝)
- **Large Digital Countdown:** Massive 7-segment style numbers (7 lines tall) with blink effect
- **Recording Reminder:** Red blinking text during countdown: "PRESS RECORD ON YOUR DECK WHEN COUNTDOWN HITS 0"
- **Progress Bars:** Color-coded bars (█ and ░) for track and total time
- **Track Preview Indicator:** Musical note (♪) symbol for playing tracks
- **Capacity Warning:** Red blinking highlight when track selection exceeds tape length
- **Clear Labels:** Descriptive text throughout (no cryptic abbreviations)
- **Smart Navigation:** Stops at list boundaries instead of wrapping around

## 📝 Configuration Tips

### Tape Counter Rate

The counter now uses **physics-based simulation** that models real cassette tape reel behavior. The counter rate changes non-linearly as tape moves from supply to take-up reel:
- **Beginning of tape:** Smaller take-up reel = faster counter rate
- **Middle of tape:** Medium reel size = rate matches your `--counter-rate` setting
- **End of tape:** Larger take-up reel = slower counter rate

Configure the base counter rate to match your deck's behavior at the middle of the tape:

```bash
# If counter reaches ~60 at mid-tape after 1 minute
python decprec.py --counter-rate 1.0

# If counter reaches ~120 at mid-tape after 1 minute  
python decprec.py --counter-rate 2.0

# Custom rate (e.g., 1.1) - tune to match your deck
python decprec.py --counter-rate 1.1
```

**Note:** The physics simulation automatically accounts for reel diameter changes, so you only need to set the base rate. The counter will speed up and slow down naturally just like a real tape deck!

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

### Normalization Methods

Choose between peak and LUFS normalization:
```bash
# LUFS normalization (default) - broadcast standard, consistent perceived loudness
python decprec.py --normalization lufs --target-lufs -14.0

# Peak normalization - maximizes amplitude
python decprec.py --normalization peak

# Custom LUFS target (e.g., for louder output)
python decprec.py --normalization lufs --target-lufs -12.0
```

### Audio Latency Compensation

Sync VU meters with audio output (useful in WSL or with audio buffering):
```bash
# No compensation (default)
python decprec.py --audio-latency 0.0

# Delay meters by 0.2 seconds to match audio lag
python decprec.py --audio-latency 0.2

# Fine-tune for perfect sync (try 0.1-0.5)
python decprec.py --audio-latency 0.3
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

### Complete Example

Full configuration for a C90 tape with LUFS normalization and latency compensation:
```bash
python decprec.py \
  --folder ~/tracks \
  --duration 45 \
  --track-gap 5 \
  --leader-gap 10 \
  --counter-rate 1.1 \
  --normalization lufs \
  --target-lufs -14.0 \
  --audio-latency 0.2
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

### LUFS Normalization Not Available
```
ERROR: LUFS normalization requires pyloudnorm
```
**Solution:** Install pyloudnorm for LUFS support:
```bash
pip install pyloudnorm
```
Or use peak normalization instead:
```bash
python decprec.py --normalization peak
```

### VU Meters Not Syncing with Audio
**Symptom:** VU meters appear to move before or after the actual sound

**Solution:** Use audio latency compensation to sync meters with output:
```bash
# If meters are ahead of audio (common in WSL)
python decprec.py --audio-latency 0.2

# Adjust value between 0.1-0.5 until perfectly synced
python decprec.py --audio-latency 0.3
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
