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
    """Finds the first .mp3 file in the script's directory."""
    cwd = Path(__file__).parent
    mp3s = list(cwd.glob('*.mp3'))
    return mp3s[0] if mp3s else None


def parse_action_from_line(line: str):
    """Parses the action string from a line of tracker output."""
    # --- MODIFIED: Look for 'Action:' instead of 'Gesture:' ---
    m = re.search(r'Action:\s*([^|\n]+)', line)
    if m:
        return m.group(1).strip()
    return None


class MusicControllerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title('MaestroBOT - Gesture Music Controller')

        # --- Add audio filter to preserve pitch on rate change ---
        self.instance = vlc.Instance('--audio-filter=scaletempo')
        self.player = self.instance.media_player_new()

        # State
        self.current_file = None
        self.is_playing = False
        self.is_paused = False
        self.volume = 60  # 0-100
        self.playback_rate = 1.0 # 1.0 is normal speed
        self.player.audio_set_volume(self.volume)

        # Cooldowns and step values
        self.ACTION_COOLDOWN = 0.4
        self.VOL_STEP = 8
        self.RATE_STEP = 0.25 # Speed up/down by 25%
        self.last_action_time = {'start': 0, 'pause': 0, 'vol': 0, 'rate': 0}

        # --- Updated instructions ---
        instructions = (
            "Gesture Controls:\n"
            "• Open Hand → Play/Resume playback\n"
            "• Closed Fist → Pause playback\n"
            "• Pointing Up/Thumbs Up → Raise volume\n"
            "• Two Fingers → Lower volume\n"
            "• Three Fingers → Speed up playback\n"
            "• Four Fingers → Slow down playback"
        )
        self.label_instructions = tk.Label(root, text=instructions, 
                                           justify=tk.LEFT, 
                                           font=('Segoe UI', 10),
                                           relief=tk.GROOVE,
                                           padx=10, pady=10)
        self.label_instructions.pack(padx=8, pady=6, fill=tk.X)

        self.label_file = tk.Label(root, text='File: (none)', wraplength=400)
        self.label_file.pack(padx=8, pady=6)

        # --- MODIFIED: Label now shows 'Action' ---
        self.label_action = tk.Label(root, text='Action: (none)', font=('Segoe UI', 14))
        self.label_action.pack(padx=8, pady=6)

        self.label_state = tk.Label(root, text='State: stopped | Volume: 60 | Rate: 1.00x')
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
        """Opens a file dialog to load an MP3 and starts playing it."""
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
        """Manually starts playback, finding a default MP3 if none is loaded."""
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
        self.playback_rate = 1.0
        self.player.set_rate(self.playback_rate)
        self.is_playing = True
        self.is_paused = False
        self._update_state_label()

    def pause_manual(self):
        """Manually pauses playback."""
        if self.is_playing and not self.is_paused:
            self.player.pause()
            self.is_paused = True
            self._update_state_label()

    def stop_manual(self):
        """Manually stops playback and resets rate."""
        self.player.stop()
        self.playback_rate = 1.0 # Reset rate
        self.is_playing = False
        self.is_paused = False
        self._update_state_label()

    def start_hand_tracking_subprocess(self):
        """Finds and runs the hand_tracker.py script as a subprocess."""
        script_path = Path(__file__).parent / 'hand-tracker.py'
        if not script_path.exists():
            messagebox.showerror('Missing Script', f'hand-tracker.py not found at {script_path}')
            return

        cmd = [sys.executable, '-u', str(script_path)]
        try:
            self.subproc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        except Exception as e:
            messagebox.showerror('Subprocess error', f'Failed to start hand-tracker.py: {e}')
            return

        self.reading = True
        self.reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self.reader_thread.start()

    def _reader_loop(self):
        """Thread target to read lines from subprocess stdout and put them in a queue."""
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
        """Periodically checks the queue for new lines from the reader thread."""
        try:
            while not self.queue.empty():
                line = self.queue.get_nowait()
                self._handle_line(line)
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self._poll_queue)

    def _handle_line(self, line: str):
        """Parses a line of output and performs the corresponding media action."""
        # --- MODIFIED: Use parse_action_from_line ---
        action = parse_action_from_line(line)
        if action:
            self.label_action.config(text=f'Action: {action}')
            now = time.time()

            # --- MODIFIED: Check for action strings ---
            if 'Play/Resume' in action:
                if (now - self.last_action_time['start']) > self.ACTION_COOLDOWN:
                    if not self.is_playing or self.is_paused:
                        if self.is_paused:
                            self.player.play() # Resumes
                            self.is_paused = False
                            self.is_playing = True
                            print('Unpaused playback (Open Hand)')
                        else:
                            self.player.play()
                            self.playback_rate = 1.0
                            self.player.set_rate(self.playback_rate)
                            self.is_playing = True
                            self.is_paused = False
                            print('Started playback (Open Hand)')
                        self.last_action_time['start'] = now

            elif 'Pause' in action:
                if (now - self.last_action_time['pause']) > self.ACTION_COOLDOWN:
                    if self.is_playing and not self.is_paused:
                        self.player.pause()
                        self.is_paused = True
                        print('Paused playback (Closed Fist)')
                        self.last_action_time['pause'] = now

            elif 'Volume Up' in action:
                if (now - self.last_action_time['vol']) > self.ACTION_COOLDOWN:
                    self.volume = min(100, self.volume + self.VOL_STEP)
                    self.player.audio_set_volume(self.volume)
                    print(f'Volume up -> {self.volume} ({action})')
                    self.last_action_time['vol'] = now

            elif 'Volume Down' in action:
                if (now - self.last_action_time['vol']) > self.ACTION_COOLDOWN:
                    self.volume = max(0, self.volume - self.VOL_STEP)
                    self.player.audio_set_volume(self.volume)
                    print(f'Volume down -> {self.volume} ({action})')
                    self.last_action_time['vol'] = now
            
            elif 'Speed Up' in action:
                if (now - self.last_action_time['rate']) > self.ACTION_COOLDOWN:
                    self.playback_rate = min(3.0, self.playback_rate + self.RATE_STEP)
                    self.player.set_rate(self.playback_rate)
                    print(f'Speed up -> {self.playback_rate:.2f}x ({action})')
                    self.last_action_time['rate'] = now
            
            elif 'Slow Down' in action:
                if (now - self.last_action_time['rate']) > self.ACTION_COOLDOWN:
                    self.playback_rate = max(0.25, self.playback_rate - self.RATE_STEP)
                    self.player.set_rate(self.playback_rate)
                    print(f'Speed down -> {self.playback_rate:.2f}x ({action})')
                    self.last_action_time['rate'] = now

            # Update state label after any action
            self._update_state_label()

    def _update_state_label(self):
        """Updates the state label with current status, volume, and rate."""
        state = 'playing' if self.is_playing and not self.is_paused else ('paused' if self.is_paused else 'stopped')
        rate_str = f"{self.playback_rate:.2f}x"
        self.label_state.config(text=f'State: {state} | Volume: {self.volume} | Rate: {rate_str}')

    def _on_close(self):
        """Handles window close event, terminating subprocess and stopping player."""
        try:
            if self.subproc and self.subproc.poll() is None:
                self.subproc.terminate() # Kill the hand-tracker.py process
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

