import os
import sys
import subprocess
import time
import re
from pathlib import Path

try:
    import pygame
except Exception:
    print("Module 'pygame' is required. Install with: pip install pygame")
    raise


def find_default_mp3():
    cwd = Path(__file__).parent
    mp3s = list(cwd.glob('*.mp3'))
    return mp3s[0] if mp3s else None


def parse_gesture_from_line(line: str):
    # Expect lines like: "Hand: Right | Gesture: Open Hand | Motion: Moving Up"
    m = re.search(r'Gesture:\s*([^|\n]+)', line)
    if m:
        return m.group(1).strip()
    return None


def clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


def main():
    # Parse command-line arg for mp3
    import argparse
    p = argparse.ArgumentParser(description='Music controller using hand-tracking.py outputs')
    p.add_argument('--file', '-f', help='Path to mp3 file to play')
    args = p.parse_args()

    mp3_path = None
    if args.file:
        mp3_path = Path(args.file)
        if not mp3_path.exists():
            print(f"MP3 file not found: {mp3_path}")
            return
    else:
        mp3_path = find_default_mp3()
        if mp3_path is None:
            print("No mp3 passed and none found in project folder. Provide one with --file <path>")
            return

    mp3_path = str(mp3_path)
    print(f"Using MP3: {mp3_path}")

    # Initialize pygame mixer
    pygame.mixer.init()
    pygame.mixer.music.load(mp3_path)
    volume = 0.6
    pygame.mixer.music.set_volume(volume)

    # Playback state bookkeeping
    is_playing = False
    is_paused = False

    # cooldowns to avoid repeated rapid actions
    last_action_time = {
        'start': 0,
        'pause': 0,
        'vol': 0
    }
    ACTION_COOLDOWN = 0.4  # seconds
    VOL_STEP = 0.08

    # Launch hand-tracking.py as subprocess and read its stdout
    script_path = Path(__file__).parent / 'hand-tracking.py'
    if not script_path.exists():
        print(f"hand-tracking.py not found at {script_path}")
        return

    # Use unbuffered mode to try to get live output
    cmd = [sys.executable, '-u', str(script_path)]
    print('Starting hand-tracking subprocess...')
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)

    try:
        # Read lines from hand-tracking script
        for raw in proc.stdout:
            line = raw.strip()
            if not line:
                continue
            # Echo the raw line for debugging (optional)
            # print(f"[HAND] {line}")

            gesture = parse_gesture_from_line(line)
            if not gesture:
                continue

            now = time.time()

            # Start (Open Hand)
            if 'Open Hand' in gesture:
                if (now - last_action_time['start']) > ACTION_COOLDOWN:
                    if not is_playing or is_paused:
                        # If paused, unpause; else start from beginning
                        if is_paused:
                            pygame.mixer.music.unpause()
                            is_paused = False
                            is_playing = True
                            print('Unpaused playback (Open Hand)')
                        else:
                            pygame.mixer.music.play()
                            is_playing = True
                            is_paused = False
                            print('Started playback (Open Hand)')
                    last_action_time['start'] = now

            # Pause (Closed Fist)
            elif 'Closed Fist' in gesture:
                if (now - last_action_time['pause']) > ACTION_COOLDOWN:
                    if is_playing and not is_paused:
                        pygame.mixer.music.pause()
                        is_paused = True
                        print('Paused playback (Closed Fist)')
                    last_action_time['pause'] = now

            # Volume up (Pointing Up or Thumbs Up)
            elif ('Pointing Up' in gesture) or ('Thumbs Up' in gesture):
                if (now - last_action_time['vol']) > ACTION_COOLDOWN:
                    volume = clamp(volume + VOL_STEP)
                    pygame.mixer.music.set_volume(volume)
                    print(f'Volume up -> {volume:.2f} ({gesture})')
                    last_action_time['vol'] = now

            # Volume down (Two Fingers)
            elif 'Two Fingers' in gesture:
                if (now - last_action_time['vol']) > ACTION_COOLDOWN:
                    volume = clamp(volume - VOL_STEP)
                    pygame.mixer.music.set_volume(volume)
                    print(f'Volume down -> {volume:.2f} (Two Fingers)')
                    last_action_time['vol'] = now

            # Optionally, you can print or handle other gestures here

    except KeyboardInterrupt:
        print('Interrupted by user, shutting down...')
    finally:
        try:
            proc.terminate()
        except Exception:
            pass
        pygame.mixer.music.stop()
        pygame.mixer.quit()


if __name__ == '__main__':
    main()
