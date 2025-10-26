# 🎵 **MaestroBOT**
Turns your webcam into a **virtual conductor’s baton** — play, pause, and adjust music playback with just your hands.


## 🧩 Overview

This project combines computer vision (MediaPipe), gesture recognition, and audio control to control music via hand gestures.

Gesture -> Action mapping (default):

| Gesture | Action |
|---:|:---|
| 🖐️ Open Hand | ▶️ Play / Resume playback |
| ✊ Closed Fist | ⏸️ Pause playback |
| ☝️ One Finger (Point Up) | 🔊 Volume Up |
| ✌️ Two Fingers | 🔉 Volume Down |
| 🤟 Three Fingers | ⏩ Speed Up |
| 🖖 Four Fingers | ⏪ Slow Down |

A simple Tkinter GUI provides real-time feedback while the hand-tracking runs locally.

## 🗂️ Repository structure

| File | Description |
|---|---|
| `hand-tracking.py` | Captures webcam video, detects hand gestures, and prints recognized actions to stdout. |
| `music_controller.py` | Launches `hand-tracking.py`, parses gesture outputs, and controls an MP3 using `python-vlc`. Includes a Tkinter GUI. |


## ⚙️ Prerequisites

- Python 3.8 → 3.11
- A working webcam
- At least one `.mp3` file in the project folder


## 🚀 Quick install

1) Clone the repository

```bash
git clone https://github.com/baonguy3n/MaestroBOT.git
cd MaestroBOT
```

2) (Recommended) Create and activate a virtual environment (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

3) Install dependencies

```powershell
pip install -r requirements.txt
# or, if you prefer to install individually:
py -m pip install opencv-python mediapipe python-vlc
```

Notes:
- On Windows, install the VLC application from https://www.videolan.org/vlc/ so `python-vlc` can find the runtime.
- If MediaPipe installation fails, try upgrading pip first:

```powershell
python -m pip install --upgrade pip setuptools wheel
pip install mediapipe
```

## ▶️ Run MaestroBOT

A. Test gesture detection only (run the tracker):

```powershell
python .\hand-tracking.py
```

B. Run the full GUI music controller (this spawns the tracker internally):

```powershell
python .\music_controller.py
```

You should see terminal output such as:

```
Hand: Right | Action: Volume Up
```

## 🧰 Troubleshooting

- VLC not found: install the VLC desktop app and ensure its architecture (32/64-bit) matches your Python build.
- Camera not detected: run `hand-tracking.py` alone to confirm webcam and MediaPipe are working.
- MediaPipe install issues: upgrade pip/setuptools/wheel and re-install (see commands above).


## 🔬 Next steps

- Consider refactoring `hand-tracking.py` into an importable Python module so `music_controller.py` can receive events via function calls instead of a subprocess.
- Add playlist navigation and gesture customization.
- Wrap the backend in a small HTTP API (FastAPI/Flask) to make it easy for other frontends (Java, React, mobile) to integrate.


## 📜 License & attribution

This project uses MediaPipe (Google) for hand detection. See MediaPipe licensing for redistribution rules.

The hand gesture tracking we used is from GeeksforGeeks — Right & Left Hand Detection using Python (https://www.geeksforgeeks.org/python/right-and-left-hand-detection-using-python/).
