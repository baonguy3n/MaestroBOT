import os
import sys
import subprocess
import time
import re
import threading
import queue
from pathlib import Path

try:
    import vlc
except Exception:
    print("Module 'python-vlc' is required. Install with: pip install python-vlc")
    raise

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox
except Exception:
    print("Tkinter not available - it's required for the GUI (usually included with standard Python).")
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


class MusicControllerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title('MaestroBOT - VLC Music Controller')

        # VLC player
        self.instance = vlc.Instance()
        self.player = self.instance.media_player_new()

        # State
        self.current_file = None
        self.is_playing = False
        self.is_paused = False
        self.volume = 60  # 0-100
        self.player.audio_set_volume(self.volume)

        self.ACTION_COOLDOWN = 0.4
        self.VOL_STEP = 8
        self.last_action_time = {'start': 0, 'pause': 0, 'vol': 0}

        # GUI elements
        instructions = (
            "Gesture Controls:\n"
            "• Open Hand → Start/Resume playback\n"
            "• Closed Fist → Pause playback\n"
            "• Pointing Up/Thumbs Up → Raise volume\n"
            "• Two Fingers → Lower volume"
        )
        self.label_instructions = tk.Label(root, text=instructions, 
                                         justify=tk.LEFT, 
                                         font=('Segoe UI', 10),
                                         relief=tk.GROOVE,
                                         padx=10, pady=10)
        self.label_instructions.pack(padx=8, pady=6, fill=tk.X)

        self.label_file = tk.Label(root, text='File: (none)', wraplength=400)
        self.label_file.pack(padx=8, pady=6)

        self.label_gesture = tk.Label(root, text='Gesture: (none)', font=('Segoe UI', 14))
        self.label_gesture.pack(padx=8, pady=6)

        self.label_state = tk.Label(root, text='State: stopped | Volume: 60')
        self.label_state.pack(padx=8, pady=6)

        btn_frame = tk.Frame(root)
        btn_frame.pack(padx=8, pady=6)

        tk.Button(btn_frame, text='Load MP3', command=self.load_file).grid(row=0, column=0, padx=4)
        tk.Button(btn_frame, text='Play', command=self.play_manual).grid(row=0, column=1, padx=4)
        tk.Button(btn_frame, text='Pause', command=self.pause_manual).grid(row=0, column=2, padx=4)
        tk.Button(btn_frame, text='Stop', command=self.stop_manual).grid(row=0, column=3, padx=4)

        # Threading: queue for lines from hand-tracking
        self.queue = queue.Queue()
        self.subproc = None
        self.reader_thread = None
        self.reading = False

        # Start hand-tracking subprocess automatically
        self.start_hand_tracking_subprocess()

        # Poll queue periodically
        self.root.after(100, self._poll_queue)

        # Handle closing
        self.root.protocol('WM_DELETE_WINDOW', self._on_close)

    def load_file(self):
        file = filedialog.askopenfilename(filetypes=[('MP3 files', '*.mp3'), ('All files', '*.*')])
        if not file:
            return
        self.current_file = file
        self.label_file.config(text=f'File: {file}')
        media = self.instance.media_new(str(file))
        self.player.set_media(media)
        # Auto play when file loaded
        self.play_manual()

    def play_manual(self):
        if not self.current_file:
            default = find_default_mp3()
            if default:
                self.current_file = str(default)
                media = self.instance.media_new(self.current_file)
                self.player.set_media(media)
                self.label_file.config(text=f'File: {self.current_file}')
            else:
                messagebox.showinfo('No MP3', 'No MP3 chosen and none found in project folder.')
                return
        self.player.play()
        self.is_playing = True
        self.is_paused = False
        self._update_state_label()

    def pause_manual(self):
        if self.is_playing and not self.is_paused:
            self.player.pause()
            self.is_paused = True
            self._update_state_label()

    def stop_manual(self):
        self.player.stop()
        self.is_playing = False
        self.is_paused = False
        self._update_state_label()

    def start_hand_tracking_subprocess(self):
        script_path = Path(__file__).parent / 'hand-tracking.py'
        if not script_path.exists():
            messagebox.showerror('Missing Script', f'hand-tracking.py not found at {script_path}')
            return

        cmd = [sys.executable, '-u', str(script_path)]
        try:
            self.subproc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        except Exception as e:
            messagebox.showerror('Subprocess error', f'Failed to start hand-tracking.py: {e}')
            return

        self.reading = True
        self.reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self.reader_thread.start()

    def _reader_loop(self):
        # Read lines from subprocess and push them to queue
        try:
            for raw in self.subproc.stdout:
                if raw is None:
                    break
                line = raw.strip()
                if line:
                    self.queue.put(line)
        except Exception:
            pass

    def _poll_queue(self):
        try:
            while not self.queue.empty():
                line = self.queue.get_nowait()
                self._handle_line(line)
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self._poll_queue)

    def _handle_line(self, line: str):
        # Update label with raw line for debug
        # parse gesture
        gesture = parse_gesture_from_line(line)
        if gesture:
            self.label_gesture.config(text=f'Gesture: {gesture}')
            now = time.time()

            # Start (Open Hand)
            if 'Open Hand' in gesture:
                if (now - self.last_action_time['start']) > self.ACTION_COOLDOWN:
                    if not self.is_playing or self.is_paused:
                        if self.is_paused:
                            self.player.play()
                            self.is_paused = False
                            self.is_playing = True
                            print('Unpaused playback (Open Hand)')
                        else:
                            self.player.play()
                            self.is_playing = True
                            self.is_paused = False
                            print('Started playback (Open Hand)')
                    self.last_action_time['start'] = now

            # Pause (Closed Fist)
            elif 'Closed Fist' in gesture:
                if (now - self.last_action_time['pause']) > self.ACTION_COOLDOWN:
                    if self.is_playing and not self.is_paused:
                        self.player.pause()
                        self.is_paused = True
                        print('Paused playback (Closed Fist)')
                    self.last_action_time['pause'] = now

            # Volume up (Pointing Up or Thumbs Up)
            elif ('Pointing Up' in gesture) or ('Thumbs Up' in gesture):
                if (now - self.last_action_time['vol']) > self.ACTION_COOLDOWN:
                    self.volume = min(100, self.volume + self.VOL_STEP)
                    self.player.audio_set_volume(self.volume)
                    print(f'Volume up -> {self.volume} ({gesture})')
                    self._update_state_label()
                    self.last_action_time['vol'] = now

            # Volume down (Two Fingers)
            elif 'Two Fingers' in gesture:
                if (now - self.last_action_time['vol']) > self.ACTION_COOLDOWN:
                    self.volume = max(0, self.volume - self.VOL_STEP)
                    self.player.audio_set_volume(self.volume)
                    print(f'Volume down -> {self.volume} (Two Fingers)')
                    self._update_state_label()
                    self.last_action_time['vol'] = now

            # Update state label after handling
            self._update_state_label()

    def _update_state_label(self):
        state = 'playing' if self.is_playing and not self.is_paused else ('paused' if self.is_paused else 'stopped')
        self.label_state.config(text=f'State: {state} | Volume: {self.volume}')

    def _on_close(self):
        # Cleanup
        try:
            if self.subproc and self.subproc.poll() is None:
                self.subproc.terminate()
        except Exception:
            pass
        try:
            self.player.stop()
        except Exception:
            pass
        self.root.destroy()


def main():
    root = tk.Tk()
    app = MusicControllerGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()
