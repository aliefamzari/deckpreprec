#!/usr/bin/env python3
"""
Textual UI for Tape Deck Recording
Modern TUI implementation using Textual framework
"""

import asyncio
import time
import subprocess
from pathlib import Path
from textual.app import App, ComposeResult
from textual.containers import Container, Vertical, Horizontal, ScrollableContainer
from textual.widgets import (
    DataTable, ProgressBar, Static, Footer, Header, 
    Button, Input, Tree, Log, Label, LoadingIndicator
)
from textual.reactive import reactive, var
from textual.message import Message
from textual.binding import Binding
from rich.text import Text
from rich.panel import Panel
from rich.align import Align
from rich.console import Console
from rich.table import Table as RichTable

# Import shared modules
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from shared.config import TapeConfig, validate_dependencies
from shared.audio_processor import list_tracks, normalize_tracks, get_audio_level_at_time
from shared.deck_profiles import get_tape_type_info
from shared.counter_engine import calibrate_counter_wizard
from shared.tracklist_generator import format_duration


class TapeCounter(Static):
    """Large 7-segment style tape counter display"""
    
    counter_value = reactive(0)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.counter_value = 0
    
    def render(self) -> Text:
        # Create large 7-segment style display
        counter_str = f"{self.counter_value:04d}"
        
        # Simple large text representation
        display = Text()
        display.append("???????????????????\n", style="cyan")
        display.append("?  TAPE COUNTER   ?\n", style="cyan bold")
        display.append("???????????????????\n", style="cyan")
        display.append(f"?      {counter_str}      ?\n", style="yellow bold")
        display.append("???????????????????", style="cyan")
        
        return display
    
    def update_counter(self, value: int):
        """Update counter value"""
        self.counter_value = value


class VUMeter(ProgressBar):
    """Custom VU meter widget with retro styling"""
    
    def __init__(self, channel: str = "L", **kwargs):
        super().__init__(**kwargs)
        self.channel = channel
        self.total = 100
        self.show_eta = False
        self.show_percentage = False
    
    def render_bar(self) -> Text:
        """Custom bar rendering for VU meter style"""
        # Override to create segmented VU meter look
        progress = self.progress
        
        # Create segments (each segment is 2 characters)
        segments = 25  # 50 char width / 2
        filled_segments = int((progress / 100) * segments)
        
        # Color zones: green (0-70%), yellow (70-85%), red (85-100%)
        bar = Text()
        
        for i in range(segments):
            if i < filled_segments:
                if i < segments * 0.7:
                    bar.append("??", style="green")
                elif i < segments * 0.85:
                    bar.append("??", style="yellow")
                else:
                    bar.append("??", style="red bold blink")
            else:
                bar.append("??", style="blue dim")
        
        return Text.assemble(
            Text(f"{self.channel} [", style="cyan"),
            bar,
            Text("]", style="cyan")
        )


class ConfigPanel(Static):
    """Configuration display panel"""
    
    def __init__(self, config: TapeConfig, **kwargs):
        super().__init__(**kwargs)
        self.config = config
        self.selected_tracks = []
        self.show_warning = False
    
    def render(self) -> Panel:
        """Render configuration information"""
        table = RichTable.grid(padding=(0, 1))
        table.add_column(style="cyan")
        table.add_column(style="white")
        
        # Counter configuration
        mode_name = self.config.get_mode_display_name()
        counter_info = f"Counter: {mode_name}"
        if self.config.counter_mode == "static":
            counter_info += f" ({self.config.counter_rate} counts/sec)"
        elif self.config.counter_mode == "manual" and self.config.calibration_data:
            deck = self.config.calibration_data.get('deck_model', 'Unknown')
            counter_info += f" ({deck})"
        
        table.add_row("???", counter_info)
        
        # Tape type information
        tape_info = get_tape_type_info(self.config.tape_type)
        tape_line = f"Tape: {self.config.tape_type} - {tape_info['name']} ({tape_info['bias']})"
        table.add_row("??", tape_line)
        
        # Audio settings
        norm_info = f"Audio: {self.config.normalization_method.upper()} normalization"
        if self.config.normalization_method == "lufs":
            norm_info += f" (target: {self.config.target_lufs:+.1f} LUFS)"
        table.add_row("??", norm_info)
        
        # Timing
        timing_info = f"Timing: {self.config.leader_gap_seconds}s leader + {self.config.track_gap_seconds}s gaps"
        table.add_row("??", timing_info)
        
        # Recording time and capacity
        if self.selected_tracks:
            total_duration = sum(track.get('duration', 0) for track in self.selected_tracks)
            total_with_gaps = total_duration + (self.config.track_gap_seconds * (len(self.selected_tracks) - 1)) + self.config.leader_gap_seconds
        else:
            total_with_gaps = 0
        
        time_style = "red bold blink" if self.show_warning else "white"
        table.add_row("??", Text(f"Total Recording Time: {format_duration(total_with_gaps)}", style=time_style))
        
        # Tape length
        tape_type_indicator = ""
        if self.config.total_duration_minutes == 30:
            tape_type_indicator = " (C60)"
        elif self.config.total_duration_minutes == 45:
            tape_type_indicator = " (C90)"
        elif self.config.total_duration_minutes == 60:
            tape_type_indicator = " (C120)"
        
        tape_length_text = f"Tape Length: {self.config.total_duration_minutes}min{tape_type_indicator}"
        table.add_row("??", Text(tape_length_text, style=time_style))
        
        if self.config.audio_latency > 0:
            table.add_row("??", f"Audio latency compensation: {self.config.audio_latency}s")
        
        return Panel(table, title="[bold magenta]CONFIGURATION[/bold magenta]", border_style="cyan")
    
    def update_tracks(self, selected_tracks, show_warning=False):
        """Update selected tracks and warning status"""
        self.selected_tracks = selected_tracks
        self.show_warning = show_warning
        self.refresh()


class TrackTable(DataTable):
    """Enhanced track table with selection and playback info"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cursor_type = "row"
        self.zebra_stripes = True
        
        # Add columns
        self.add_columns("Track", "Duration", "Format", "Status")
        
        self.tracks = []
        self.selected_tracks = []
        self.playing_track = -1
    
    def load_tracks(self, tracks):
        """Load track data into table"""
        # Preserve cursor position
        current_cursor = self.cursor_row if hasattr(self, 'cursor_row') else 0
        
        self.clear()
        self.tracks = tracks
        
        for i, track in enumerate(tracks):
            duration_str = format_duration(track['duration'])
            format_str = f"{track['codec']}"
            if track['quality'] != "Unknown":
                format_str += f" {track['quality']}"
            
            # Show selection order number
            if track in self.selected_tracks:
                selection_order = self.selected_tracks.index(track) + 1
                status = f"#{selection_order:02d}"
            else:
                status = ""
            
            if i == self.playing_track:
                status = "? Playing"
            
            self.add_row(
                track['name'],
                duration_str, 
                format_str,
                status,
                key=str(i)
            )
        
        # Restore cursor position
        if current_cursor is not None and current_cursor < len(tracks):
            self.move_cursor(row=current_cursor)
    
    def _refresh_table(self):
        """Refresh the table display while preserving cursor position"""
        current_cursor = self.cursor_row
        self.load_tracks(self.tracks)
        
        # The load_tracks method already preserves cursor position,
        # but let's ensure it's set correctly
        if current_cursor is not None and current_cursor < len(self.tracks):
            try:
                self.move_cursor(row=current_cursor)
            except:
                pass  # Ignore any cursor positioning errors
    
    def toggle_selection(self, track_index: int):
        """Toggle track selection while maintaining order"""
        if 0 <= track_index < len(self.tracks):
            track = self.tracks[track_index]
            if track in self.selected_tracks:
                self.selected_tracks.remove(track)
            else:
                self.selected_tracks.append(track)
            
            # Refresh table to show selection changes
            self._refresh_table()
    
    def clear_selection(self):
        """Clear all selected tracks"""
        self.selected_tracks.clear()
        self._refresh_table()
    
    def set_playing_track(self, track_index: int):
        """Set which track is currently playing"""
        self.playing_track = track_index
        self._refresh_table()


class CassetteArt(Static):
    """ASCII cassette tape art display"""
    
    def render(self) -> Panel:
        art_text = Text()
        art_lines = [
            " ___________________________________________",
            "|  _______________________________________  |",
            "| / .-----------------------------------. \\ |",
            "| | | /\\ :                        90 min| | |",
            "| | |/--\\:....................... NR [ ]| | |",
            "| | `-----------------------------------' | |",
            "| |      //-\\\\   |         |   //-\\\\      | |",
            "| |     ||( )||  |_________|  ||( )||     | |",
            "| |      \\\\-//   :....:....:   \\\\-//      | |",
            "| |       _ _ ._  _ _ .__|_ _.._  _       | |",
            "| |      (_(_)| |(_(/_|  |_(_||_)(/_      | |",
            "| |               low noise   |           | |",
            "| `______ ____________________ ____ ______' |",
            "|        /    []             []    \\        |",
            "|       /  ()                   ()  \\       |",
            "!______/_____________________________\\______!"
        ]
        
        for line in art_lines:
            art_text.append(line + "\n", style="magenta")
        
        return Panel(
            Align.center(art_text), 
            title="[bold cyan]?? Retro Tape Deck Recording[/bold cyan]",
            border_style="cyan"
        )


class TapeDeckApp(App):
    """Main Tape Deck Application using Textual"""
    
    CSS_PATH = None  # We'll set this dynamically
    
    TITLE = "?? Retro Tape Deck Recording"
    SUB_TITLE = "Modern TUI for Cassette Recording"
    
    # Reactive variables for real-time updates
    counter_value = reactive(0)
    playback_position = reactive(0.0)
    vu_level_l = reactive(0.0)
    vu_level_r = reactive(0.0)
    
    # Bindings
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("space", "toggle_selection", "Select Track"),
        Binding("c", "clear_selection", "Clear All"),
        Binding("p", "play_pause", "Play/Pause"),
        Binding("x", "stop", "Stop"),
        Binding("left", "rewind", "Rewind 10s"),
        Binding("right", "forward", "Forward 10s"),
        Binding("enter", "start_recording", "Record"),
        Binding("ctrl+c", "calibrate", "Calibrate Counter"),
    ]
    
    def __init__(self, config_args=None):
        super().__init__()
        
        # Set CSS path dynamically
        css_path = os.path.join(os.path.dirname(__file__), "tape_deck.css")
        if os.path.exists(css_path):
            self.CSS_PATH = css_path
        
        # Initialize configuration
        self.config = TapeConfig(config_args)
        self.tracks = []
        self.normalized_tracks = []
        self.selected_tracks = []
        self.current_track_index = 0
        self.playing = False
        self.ffplay_proc = None
        
        # Load calibration data if needed
        if not self.config.load_calibration_data():
            self.exit(1)
    
    def compose(self) -> ComposeResult:
        """Create the UI layout"""
        yield Header()
        
        with Container(id="main-container"):
            # Top section: Cassette art and configuration
            with Horizontal(id="top-section"):
                yield CassetteArt(id="cassette-art")
                yield ConfigPanel(self.config, id="config-panel")
            
            # Counter and VU meters section
            with Horizontal(id="meters-section"):
                yield TapeCounter(id="tape-counter")
                with Vertical(id="vu-section"):
                    yield VUMeter("L", id="vu-left")
                    yield Label("    -60  -40  -30  -20  -12   -6   -3    0 dB", id="db-scale")
                    yield VUMeter("R", id="vu-right")
            
            # Track selection table
            yield TrackTable(id="track-table")
            
            # Selected tracks display
            with ScrollableContainer(id="selected-section"):
                yield Static("", id="selected-tracks-display")
            
            # Status and controls
            yield Static("Ready - Load tracks from folder", id="status-bar")
        
        yield Footer()
    
    async def on_mount(self) -> None:
        """Initialize the application"""
        # Check dependencies
        missing, optional_missing = validate_dependencies()
        if missing:
            self.notify(f"Missing dependencies: {', '.join(missing)}", severity="error")
            return
        
        if optional_missing:
            self.notify(f"Optional dependencies missing: {', '.join(optional_missing)}", severity="warning")
        
        # Load tracks
        await self.load_tracks()
        
        # Start update timer
        self.set_timer(0.05, self.update_realtime_data)
    
    async def load_tracks(self):
        """Load audio tracks from configured folder"""
        status_bar = self.query_one("#status-bar", Static)
        status_bar.update("Loading tracks...")
        
        # Load tracks in background
        self.tracks = list_tracks(self.config.target_folder)
        
        if not self.tracks:
            status_bar.update(f"No audio tracks found in {self.config.target_folder}")
            return
        
        # Update track table
        track_table = self.query_one("#track-table", TrackTable)
        track_table.load_tracks(self.tracks)
        
        status_bar.update(f"Loaded {len(self.tracks)} tracks from {self.config.target_folder}")
    
    def update_realtime_data(self):
        """Update real-time data like VU meters and counter"""
        # Update VU meters based on playback
        if self.playing and self.ffplay_proc:
            # Simulate VU meter activity (in real implementation, get from audio analysis)
            import random
            self.vu_level_l = random.uniform(0.0, 0.8)
            self.vu_level_r = random.uniform(0.0, 0.8)
        else:
            self.vu_level_l = 0.0
            self.vu_level_r = 0.0
        
        # Update VU meter widgets
        try:
            vu_left = self.query_one("#vu-left", VUMeter)
            vu_right = self.query_one("#vu-right", VUMeter)
            vu_left.update(progress=self.vu_level_l * 100)
            vu_right.update(progress=self.vu_level_r * 100)
        except:
            pass
        
        # Update tape counter
        if self.playing:
            # Calculate counter based on playback position
            counter_val = self.config.calculate_tape_counter(self.playback_position)
            try:
                tape_counter = self.query_one("#tape-counter", TapeCounter)
                tape_counter.update_counter(counter_val)
            except:
                pass
        
        # Schedule next update
        self.set_timer(0.05, self.update_realtime_data)
    
    def action_toggle_selection(self):
        """Toggle selection of current track"""
        track_table = self.query_one("#track-table", TrackTable)
        if track_table.cursor_row is not None:
            track_table.toggle_selection(track_table.cursor_row)
            self.selected_tracks = track_table.selected_tracks
            self.update_config_panel()
    
    def action_clear_selection(self):
        """Clear all track selections"""
        track_table = self.query_one("#track-table", TrackTable)
        track_table.clear_selection()
        self.selected_tracks = []
        self.update_config_panel()
    
    def action_play_pause(self):
        """Toggle playback of current track"""
        track_table = self.query_one("#track-table", TrackTable)
        status_bar = self.query_one("#status-bar", Static)
        
        if track_table.cursor_row is None:
            status_bar.update("No track selected for playback")
            return
        
        current_track = self.tracks[track_table.cursor_row]
        
        if self.playing:
            # Stop playback
            if self.ffplay_proc:
                self.ffplay_proc.terminate()
                self.ffplay_proc = None
            self.playing = False
            track_table.set_playing_track(-1)
            status_bar.update("Playback stopped")
        else:
            # Start playback
            track_path = os.path.join(self.config.target_folder, current_track['name'])
            try:
                self.ffplay_proc = subprocess.Popen([
                    "ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", track_path
                ])
                self.playing = True
                self.playback_position = 0.0
                track_table.set_playing_track(track_table.cursor_row)
                status_bar.update(f"Playing: {current_track['name']}")
            except Exception as e:
                status_bar.update(f"Error playing track: {e}")
    
    def action_stop(self):
        """Stop playback"""
        if self.ffplay_proc:
            self.ffplay_proc.terminate()
            self.ffplay_proc = None
        self.playing = False
        self.playback_position = 0.0
        
        track_table = self.query_one("#track-table", TrackTable)
        track_table.set_playing_track(-1)
        
        status_bar = self.query_one("#status-bar", Static)
        status_bar.update("Playback stopped")
    
    def action_rewind(self):
        """Rewind 10 seconds"""
        if self.playing:
            # In real implementation, seek in ffplay
            self.notify("Rewind 10s (seek functionality to be implemented)")
    
    def action_forward(self):
        """Forward 10 seconds"""
        if self.playing:
            # In real implementation, seek in ffplay
            self.notify("Forward 10s (seek functionality to be implemented)")
    
    async def action_start_recording(self):
        """Start the recording process"""
        if not self.selected_tracks:
            self.notify("No tracks selected for recording", severity="warning")
            return
        
        status_bar = self.query_one("#status-bar", Static)
        status_bar.update("Normalizing tracks for recording...")
        
        # Normalize tracks (this should be async in real implementation)
        self.normalized_tracks = normalize_tracks(
            self.selected_tracks,
            self.config.target_folder,
            self.config.normalization_method,
            self.config.target_lufs
        )
        
        status_bar.update("Ready to record! (Recording simulation to be implemented)")
        self.notify("Recording process would start here", severity="info")
    
    def action_calibrate(self):
        """Run counter calibration wizard"""
        # This would need to be implemented as a separate screen/dialog
        self.notify("Counter calibration wizard (to be implemented as separate screen)")
    
    def update_selected_tracks_display(self):
        """Update the selected tracks display section"""
        selected_display = self.query_one("#selected-tracks-display", Static)
        
        if not self.selected_tracks:
            selected_display.update("")
            return
        
        # Build the selected tracks display
        lines = [f"SELECTED TRACKS ({len(self.selected_tracks)}):"]
        
        for i, track in enumerate(self.selected_tracks):
            duration_str = format_duration(track['duration'])
            track_line = f"  {i+1:02d}. {track['name']} - {duration_str}"
            lines.append(track_line)
        
        selected_display.update("\n".join(lines))
    
    def update_config_panel(self):
        """Update configuration panel with current selection"""
        config_panel = self.query_one("#config-panel", ConfigPanel)
        
        # Check for capacity warning
        if self.selected_tracks:
            total_duration = sum(track.get('duration', 0) for track in self.selected_tracks)
            total_with_gaps = total_duration + (self.config.track_gap_seconds * (len(self.selected_tracks) - 1)) + self.config.leader_gap_seconds
            show_warning = total_with_gaps >= self.config.total_duration_minutes * 60
        else:
            show_warning = False
        
        config_panel.update_tracks(self.selected_tracks, show_warning)
        
        # Also update selected tracks display
        self.update_selected_tracks_display()


def main():
    """Run the Textual tape deck application"""
    import argparse
    
    # Create argument parser (reuse from shared config)
    from shared.config import create_argument_parser
    parser = create_argument_parser()
    args = parser.parse_args()
    
    # Handle calibration mode
    if args.calibrate_counter:
        calibrate_counter_wizard(args.folder, args.counter_config)
        return
    
    # Run the app
    app = TapeDeckApp(args)
    app.run()


if __name__ == "__main__":
    main()