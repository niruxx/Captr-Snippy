# Snippy - Snipping Tool

A Python-based screenshot tool with GUI that works similarly to Windows Snipping Tool. Capture, preview, save, and copy screenshots to clipboard easily.

## Features

- 🎨 **Material You Design**: Dark Material 3 tonal theme with rounded cards, pill buttons, and animated hover states
- ✨ **Modern Transitions**: Window fade-in, sliding view transitions, animated snackbars, and a translucent window
- 🎯 **Crosshair Selection**: Full-screen overlay with live selection dimensions and crosshair cursor
- 👁️ **Live Preview**: View captured screenshots in the preview card
- ⚙️ **Settings**: Choose the export format (PNG, JPEG, WEBP, BMP) and quality; saved automatically to `settings.json`
- 💾 **Save to File**: Export screenshots in your preferred format
- 📋 **Copy to Clipboard**: Quickly copy screenshots to clipboard via the native Windows API
- ⌨️ **Keyboard Control**: Press `ESC` to cancel selection

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

### Keyboard Shortcuts

- **ESC** - Cancel current selection during capture

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
- **Screenshot Capture**: PIL ImageGrab
- **Clipboard**: Windows native clipboard integration
- **Cross-platform**: Windows, Linux, macOS (with minor adjustments)

## Dependencies

- `Pillow` - Image processing and manipulation (clipboard copy uses the Windows API directly, no extra packages needed)

## Troubleshooting

### "No screenshot yet" message
Make sure to capture a screenshot first by clicking the **✚ Capture** button.

### Clipboard copy not working
On Windows, ensure you have write permissions. The tool uses Windows API for clipboard integration.

### Selection not showing
Make sure your overlay window is active (in focus) when selecting.

## Future Enhancements

- [ ] Annotation tools (draw, arrow, text)
- [ ] Image editing features
- [ ] Screenshot history
- [ ] Hotkey support
- [ ] OCR text extraction
- [ ] Cloud upload integration

## License

This project is open source and available under the MIT License.

## Contributing

Contributions are welcome! Feel free to fork, make improvements, and submit pull requests.
