# MaestroBOT

A small project that uses MediaPipe hand-tracking to control music playback with gestures.

This repository currently contains:
- `hand-tracking.py` — captures webcam video, recognizes hand gestures, and prints gesture info to stdout.
- `music_controller.py` — launches `hand-tracking.py`, parses its printed gestures, and controls an MP3 using pygame.mixer.
- `requirements.txt` — dependencies to install (see notes below).

## Overview

Gesture -> action mapping (default):
- Open Hand: start playback (or unpause if paused)
- Closed Fist: pause playback
- Pointing Up OR Thumbs Up: raise volume
- Two Fingers: lower volume

The controller script (`music_controller.py`) runs `hand-tracking.py` as a subprocess and listens to its stdout lines to detect gestures. This keeps `hand-tracking.py` unchanged while allowing a quick integration.

## Prerequisites

- Windows (instructions below use PowerShell)
- Python 3.8+ (3.11 is fine)
- A working webcam
- An MP3 file to play (place it in the project root or supply via `--file`)

Important libraries:
- mediapipe (hand tracking)
- opencv-python (video capture / display)
- pygame (audio playback)

Note: MediaPipe on Windows may require a compatible protobuf wheel and a supported Python version. If you run into installation errors, see the Troubleshooting section below.

## Setup (recommended: virtual environment)

Open PowerShell in the project folder (`C:\Users\tighe\OneDrive\Desktop\hackathon\MaestroBOT`) and run:

```powershell
# Create and activate a virtual environment (PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

If you prefer not to use a virtual environment, install the dependencies globally with `pip install -r requirements.txt`.

## Prepare an MP3

Place the MP3 you want to control in the repository folder. The controller will pick the first `*.mp3` in the folder if you don't pass `--file`.

You can also pass an MP3 explicitly:

```powershell
python .\music_controller.py --file .\your_song.mp3
```

Or simply let it pick a file automatically:

```powershell
python .\music_controller.py
```

## Running the system

1. (Optional) Open a terminal and run `hand-tracking.py` to test the hand detection alone:

```powershell
python .\hand-tracking.py
```

You should see a webcam window and terminal prints when gestures change, e.g.:

```
Hand: Right | Gesture: Open Hand
Hand: Right | Gesture: Closed Fist
```

2. Start the controller (this will spawn `hand-tracking.py` internally and control playback):

```powershell
python .\music_controller.py --file .\your_song.mp3
```

While running, use the gestures above in front of your webcam. The controller prints actions it takes (start/pause/volume changes).

## Troubleshooting

- If `pygame` reports audio backend issues, ensure your system audio is working and try installing `pygame` via `pip` again. On Windows, using the official Python installer and matching bitness (x64) often avoids issues.
- If `mediapipe` installation fails, install the wheel directly matching your Python version and platform, or try upgrading `pip` first:

```powershell
python -m pip install --upgrade pip setuptools wheel
pip install mediapipe
```

- If `hand-tracking.py` prints nothing or the controller appears stuck, try running `hand-tracking.py` by itself (see above) to verify the webcam and MediaPipe are working.
- If gestures trigger too often or not at all, you can tune the cooldown or change detection logic inside `music_controller.py`. The defaults are conservative to avoid rapid repeated actions.

## Notes & next steps

- Current architecture uses a subprocess and text parsing for quick integration. For lower latency and better control, I can refactor `hand-tracking.py` to expose a Python API (generator/callback) so `music_controller.py` can import and receive events directly.
- You can easily add more gestures or change mapping in `music_controller.py` by editing how parsed gesture strings are handled.

## License / Attribution

This project uses MediaPipe (Google) for hand tracking. Check MediaPipe licensing and attribution requirements when redistributing.
