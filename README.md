# MaestroBOT

REQUIRED INSTALLATION:
- py -m pip install opencv-python mediapipe
- py -m pip install python-vlc

Also required: cv2

This repository currently contains:
- `hand-tracking.py` — captures webcam video, recognizes hand gestures, and prints gesture info.
- `music_controller.py` — launches `hand-tracking.py`, parses its printed gestures, and controls an MP3 using python-vlc; it also provides a small Tkinter GUI.

## Overview

We have 6 gestures encoding 6 instructions to the vlc-player.
- Open Hand: start playback (or unpause if paused)
- Closed Fist: pause playback
- One Finger pointed: raise volume
- Two Fingers: lower volume
- Three Fingers: Increase playback speed
- Four Fingers: Decrease playback speed

An MP3 file can be selected via the vlc-popout.

Important libraries:
- mediapipe (hand tracking)
- opencv-python (video capture / display)
- python-vlc (VLC bindings for audio playback)

## Prepare an MP3

Run the GUI controller and then load an MP3 from the GUI (or place an MP3 in the project folder and the controller will use the first one it finds):
