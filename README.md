🎵 MaestroBOT
Turns your webcam into a virtual conductor’s baton — play, pause, and adjust music playback with just your hands.

🧩 Overview
This project combines computer vision (MediaPipe), two-handed gesture recognition, and audio control to manage music playback.

Gesture -> Action mapping:

Dual-Hand Actions (Play/Stop):

Left Hand	Right Hand	Action
🖐️ Open Hand	🖐️ Open Hand	▶️ Play / Resume
✊ Closed Fist	✊ Closed Fist	⏹️ Stop Playback

Export to Sheets

Left Hand (Volume):

Gesture	Action
☝️ One Finger	🔉 Set Volume to 25%
✌️ Two Fingers	🔉 Set Volume to 50%
🤟 Three Fingers	🔊 Set Volume to 75%
🖖 Four Fingers	🔊 Set Volume to 100%

Export to Sheets

Right Hand (Speed):

Gesture	Action
☝️ One Finger	⏪ Set Speed to 0.50x
✌️ Two Fingers	⏪ Set Speed to 0.75x
🤟 Three Fingers	▶️ Set Speed to 1.00x (Normal)
🖖 Four Fingers	⏩ Set Speed to 1.50x

Export to Sheets

A restyled Tkinter GUI (dark mode) provides real-time feedback while the hand-tracking runs locally.

Note: Gestures are only registered when hands are relatively still and centered in the frame to prevent accidental commands.

🗂️ Repository structure
File	Description
hand-tracking.py	Captures webcam video, detects hand gestures, and prints recognized actions to stdout.
music_controller.py	Launches hand-tracking.py, parses gesture outputs, and controls an MP3 using python-vlc. Includes a Tkinter GUI.

Export to Sheets

⚙️ Prerequisites
Python 3.8 → 3.11

A working webcam

At least one .mp3 file in the project folder

🚀 Quick install
Clone the repository

Bash

git clone https://github.com/baonguy3n/MaestroBOT.git
cd MaestroBOT
(Recommended) Create and activate a virtual environment (PowerShell)

PowerShell

python -m venv .venv
.\.venv\Scripts\Activate.ps1
Install dependencies

PowerShell

pip install -r requirements.txt
# or, if you prefer to install individually:
py -m pip install opencv-python mediapipe python-vlc
Notes:

On Windows, install the VLC application from https://www.videolan.org/vlc/ so python-vlc can find the runtime.

If MediaPipe installation fails, try upgrading pip first:

PowerShell

python -m pip install --upgrade pip setuptools wheel
pip install mediapipe
▶️ Run MaestroBOT
A. Test gesture detection only (run the tracker):

PowerShell

python .\hand-tracking.py
B. Run the full GUI music controller (this spawns the tracker internally):

PowerShell

python .\music_controller.py
You should see terminal output such as:

Left: One Finger | Right: No Hand
Left: Open Hand | Right: Open Hand
No hands detected.
🧰 Troubleshooting
VLC not found: install the VLC desktop app and ensure its architecture (32/64-bit) matches your Python build.

Camera not detected: run hand-tracking.py alone to confirm webcam and MediaPipe are working.

MediaPipe install issues: upgrade pip/setuptools/wheel and re-install (see commands above).

🔬 Next steps
Consider refactoring hand-tracking.py into an importable Python module so music_controller.py can receive events via function calls instead of a subprocess.

Add playlist navigation and gesture customization.

Wrap the backend in a small HTTP API (FastAPI/Flask) to make it easy for other frontends (Java, React, mobile) to integrate.

📜 License & attribution
This project uses MediaPipe (Google) for hand detection. See MediaPipe licensing for redistribution rules.

The hand gesture tracking we used is from GeeksforGeeks — Right & Left Hand Detection using Python (https://www.geeksforgeeks.org/python/right-and-left-hand-detection-using-python/).