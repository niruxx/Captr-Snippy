# Snippy - Snipping Tool

A Python-based screenshot tool with GUI that works similarly to Windows Snipping Tool. Capture, preview, save, and copy screenshots to clipboard easily.

## Features

- 🎨 **Material You Design**: Dark Material 3 tonal theme with rounded cards, pill buttons, and animated hover states
- ✨ **Modern Transitions**: Window fade-in, sliding view transitions, animated snackbars, and a translucent window
- 🎯 **Crosshair Selection**: Full-screen overlay with live selection dimensions and crosshair cursor
- 👁️ **Live Preview**: View captured screenshots in the preview card
- ⚙️ **Settings**: Choose the export format (PNG, JPEG, WEBP, BMP) and quality; saved automatically to `settings.json`
- 💾 **Save to File**: Export screenshots in your preferred format
- 📋 **Copy to Clipboard**: Quickly copy screenshots to the system clipboard (native API on Windows, `osascript` on macOS, `xclip`/`wl-copy` on Linux)
- ⌨️ **Keyboard Control**: Press `ESC` to cancel selection
- 🎥 **Screen Recording**: Record the full (multi-monitor) screen to MP4, MKV, FLV or WebM, with pause/resume and a floating recording-controls bar that never appears in the recording itself
- ⌨️ **Global Recording Hotkeys**: `Ctrl+Alt+R` starts/stops and `Ctrl+Alt+P` pauses/resumes recording from anywhere, even while Snippy isn't focused (Windows only, see [Platform Notes](#platform-notes))
- 🖥️ **High Refresh Rate Capture**: Pick a capture frame rate (15/30/60/120/144 fps) in Settings to match high refresh-rate displays

## Installation

### Prerequisites
- Python 3.7+
- pip (Python package manager)

### Setup

1. Clone or download this repository:
   ```bash
   cd Snippy-Renewed
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Running the Application

```bash
python main.py
```

### How to Use

1. **Launch the Tool**: Run `python main.py` to open the Snippy window
2. **Capture Screenshot**:
   - Click the **＋ New capture** button
   - A dimmed fullscreen overlay will appear with a crosshair cursor
   - Click and drag to select the area (the selection shows its size in pixels)
   - Release the mouse to capture
3. **Preview**: The captured image will appear in the preview card
4. **Save**: Click **💾 Save** to export in the format chosen in Settings (timestamped filename by default)
5. **Copy**: Click **📋 Copy** to copy to clipboard
6. **Clear**: Click **Clear** to remove the current screenshot
7. **Settings**: Click the **⚙** icon to pick the export format (PNG, JPEG, WEBP, BMP) and quality for lossy formats

### Screen Recording

1. Click **⏺ Record** (or press `Ctrl+Alt+R`) to start recording the full screen
2. Snippy's window hides and a small floating control bar appears with a timer, pause/resume, and stop buttons
3. Use the bar's pause button, or `Ctrl+Alt+P`, to pause and resume — paused time is not included in the recording
4. Click stop, or `Ctrl+Alt+R` again, to finish; the recording is saved into your Quick save folder
5. Pick the output container (MP4, MKV, FLV, WebM) and capture frame rate in **Settings → Screen Recording**

### Keyboard Shortcuts

- **ESC** - Cancel current selection during capture
- **Ctrl+Alt+R** - Start / stop screen recording (global, works even when Snippy isn't focused)
- **Ctrl+Alt+P** - Pause / resume screen recording (global)

## Features Explained

### Capture Button (✚)
Activates the screenshot mode with a fullscreen overlay. Simply drag to select the area you want.

### Preview Window
Shows a live preview of your captured screenshot (scaled to fit).

### Save Button (💾)
Saves the screenshot with an auto-generated timestamp filename or choose a custom location/name.

### Copy Button (📋)
Copies the screenshot directly to your clipboard for pasting into other applications.

### Clear Button (🗑️)
Removes the current screenshot from the preview.

### Status Bar
Displays real-time status messages about operations (Ready, capturing, saved, etc.)

## Technical Details

- **GUI Framework**: tkinter (built-in with Python)
- **Image Processing**: Pillow (PIL)
- **Screenshot Capture**: PIL ImageGrab (native on Windows/macOS; uses `gnome-screenshot`, `grim`, or `spectacle` on Linux if Pillow wasn't built with XCB support)
- **Clipboard**: native Win32 API on Windows, `osascript` on macOS, `xclip`/`wl-copy` on Linux
- **Cross-platform**: Windows, macOS, Linux — see [Platform Notes](#platform-notes) for what's Windows-exclusive

## Dependencies

- `Pillow` - Image processing, screenshot capture, and manipulation
- `imageio-ffmpeg` - Bundles a per-OS static ffmpeg binary used to encode screen recordings (no system ffmpeg install required)

On Linux you'll also want one CLI tool from each pair on your `PATH` (install via your package manager):
- **Screenshot capture**: `gnome-screenshot`, `grim` (Wayland), or `spectacle` — only needed if your Pillow build lacks XCB support
- **Clipboard copy**: `xclip` (X11) or `wl-clipboard` for `wl-copy` (Wayland)

macOS needs nothing extra — capture and clipboard both go through built-in `screencapture`/`osascript`.

## Platform Notes

A few conveniences rely on Win32 APIs and only work on Windows; everywhere else Snippy degrades gracefully to the platform default instead of failing:

- **Global hotkeys** (`Ctrl+Alt+R` / `Ctrl+Alt+P` from anywhere, even unfocused) — Windows only, via `RegisterHotKey`. Use the in-app buttons on macOS/Linux.
- **Frameless window with custom traffic-light controls** — Windows only; other platforms use the native title bar.
- **Automatic light/dark theme following the OS setting** — reads the Windows registry; macOS/Linux always use the light theme.
- **Hiding the floating recording bar from the recording itself** — uses `SetWindowDisplayAffinity`; on macOS/Linux the control bar may appear in recordings, so move it off-screen or to a second monitor if that matters.
- **Multi-monitor region capture math** assumes Windows' virtual-screen coordinate system; single-monitor setups work everywhere.

## Troubleshooting

### "No screenshot yet" message
Make sure to capture a screenshot first by clicking the **✚ Capture** button.

### Clipboard copy not working
- **Windows**: ensure you have the necessary permissions; the app uses the Win32 clipboard API directly.
- **macOS**: requires `osascript` (ships with macOS).
- **Linux**: install `xclip` (X11) or `wl-clipboard` (Wayland) — see [Dependencies](#dependencies).

### Selection not showing
Make sure your overlay window is active (in focus) when selecting.

## Future Enhancements

- [x] Annotation tools (draw, arrow, text)
- [x] Image editing features
- [x] Screenshot history
- [x] Hotkey support
- [x] Screen recording (pause/resume, multi-format export, global hotkeys)
- [ ] OCR text extraction
- [ ] Cloud upload integration

## License

This project is open source and available under the MIT License.

## Contributing

Contributions are welcome! Feel free to fork, make improvements, and submit pull requests.
