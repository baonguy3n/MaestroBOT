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
    from tkinter import ttk, font, filedialog, messagebox
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
    m = re.search(r'Action:\s*([^|\n]+)', line)
    if m:
        return m.group(1).strip()
    return None


class MusicControllerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title('MaestroBOT - Gesture Music Controller')
        self.root.geometry("480x600") # Set a default size
        self.root.configure(bg='#f0f0f0') # Set a light background color

        # --- Style Configuration ---
        self.style = ttk.Style(self.root)
        self.style.theme_use('clam') # Use a more modern theme

        # Define fonts
        self.font_normal = font.Font(family='Segoe UI', size=10)
        self.font_bold = font.Font(family='Segoe UI', size=11, weight='bold')
        self.font_action = font.Font(family='Segoe UI', size=16, weight='bold')
        self.font_state = font.Font(family='Segoe UI', size=14, weight='bold')

        # Style widgets
        self.style.configure('TFrame', background='#f0f0f0')
        self.style.configure('TLabel', background='#f0f0f0', font=self.font_normal)
        self.style.configure('TButton', font=self.font_bold, padding=(10, 5))
        self.style.configure('Instructions.TLabel', background='#ffffff', relief='solid', borderwidth=1, padding=(10, 10))
        
        # State-specific label styles
        self.style.configure('Playing.TLabel', background='#f0f0f0', font=self.font_state, foreground='green')
        self.style.configure('Paused.TLabel', background='#f0f0f0', font=self.font_state, foreground='#FF8C00') # Dark Orange
        self.style.configure('Stopped.TLabel', background='#f0f0f0', font=self.font_state, foreground='red')

        # --- VLC player ---
        self.instance = vlc.Instance('--audio-filter=scaletempo')
        self.player = self.instance.media_player_new()

        # --- State ---
        self.current_file = None
        self.is_playing = False
        self.is_paused = False
        self.camera_on = False # Will be toggled to True on start
        self.volume = 60
        self.playback_rate = 1.0
        self.player.audio_set_volume(self.volume)

        # Cooldowns and step values
        self.ACTION_COOLDOWN = 0.4
        self.VOL_STEP = 8
        self.RATE_STEP = 0.25
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
        # Use a Frame for better padding
        instr_frame = ttk.Frame(root, padding=(10, 10))
        instr_frame.pack(fill='x')
        
        self.label_instructions = ttk.Label(instr_frame, text=instructions, 
                                           justify=tk.LEFT, 
                                           style='Instructions.TLabel')
        self.label_instructions.pack(fill='x')

        # --- Status Labels Frame ---
        status_frame = ttk.Frame(root, padding=(10, 10))
        status_frame.pack(fill='x')

        self.label_file = ttk.Label(status_frame, text='File: (none)', wraplength=450)
        self.label_file.pack(pady=(5, 10))

        self.label_action = ttk.Label(status_frame, text='Action: (waiting)', font=self.font_action, style='TLabel')
        self.label_action.pack(pady=(10, 10))

        self.label_state = ttk.Label(status_frame, text='State: stopped | Volume: 60 | Rate: 1.00x', style='Stopped.TLabel')
        self.label_state.pack(pady=(10, 10))

        # --- Manual Controls Frame ---
        btn_frame = ttk.Frame(root, padding=(10, 10))
        btn_frame.pack()
        btn_frame.columnconfigure((0, 1, 2, 3), weight=1) # Make buttons space out evenly

        ttk.Button(btn_frame, text='Load MP3', command=self.load_file).grid(row=0, column=0, padx=5, sticky='ew')
        ttk.Button(btn_frame, text='Play', command=self.play_manual).grid(row=0, column=1, padx=5, sticky='ew')
        ttk.Button(btn_frame, text='Pause', command=self.pause_manual).grid(row=0, column=2, padx=5, sticky='ew')
        ttk.Button(btn_frame, text='Stop', command=self.stop_manual).grid(row=0, column=3, padx=5, sticky='ew')

        # --- NEW: Camera/Crash Controls ---
        cam_frame = ttk.Frame(root, padding=(10, 15))
        cam_frame.pack(fill='x')
        self.btn_camera_toggle = ttk.Button(cam_frame, text='Turn Camera OFF', command=self.toggle_camera, width=25)
        self.btn_camera_toggle.pack(pady=5)
        
        # --- Threading ---
        self.queue = queue.Queue()
        self.subproc = None
        self.reader_thread = None
        self.reading = False

        # Start hand-tracking subprocess automatically
        self.toggle_camera() # This will turn it ON
        
        # --- Bottom frame for crash button ---
        bottom_frame = ttk.Frame(root, padding=(10, 10))
        bottom_frame.pack(fill='x', side='bottom')
        
        self.style.configure('Crash.TButton', background='#a00', foreground='white', font=self.font_bold)
        self.style.map('Crash.TButton', background=[('active', '#c00')])
        
        self.btn_crash = ttk.Button(bottom_frame, text='Force Crash', 
                                    command=self.force_crash, style='Crash.TButton')
        self.btn_crash.pack(side='right', padx=10, pady=10)


        # Poll queue periodically
        self.root.after(100, self._poll_queue)
        # Handle closing
        self.root.protocol('WM_DELETE_WINDOW', self._on_close)

    def force_crash(self):
        """Intentionally raises an exception."""
        print("Force crash button clicked. Raising exception.")
        raise Exception("Forced crash as requested by user.")

    def toggle_camera(self):
        """Toggles the hand-tracking subprocess on and off."""
        if self.camera_on:
            # Turn it OFF
            self.stop_hand_tracking_subprocess()
            self.camera_on = False
            self.btn_camera_toggle.config(text='Turn Camera ON')
            self.label_action.config(text='Action: Camera OFF')
        else:
            # Turn it ON
            self.start_hand_tracking_subprocess()
            if self.subproc: # Check if start was successful
                self.camera_on = True
                self.btn_camera_toggle.config(text='Turn Camera OFF')
                self.label_action.config(text='Action: (waiting)')

    def load_file(self):
        """Opens a file dialog to load an MP3 and starts playing it."""
        file = filedialog.askopenfilename(filetypes=[('MP3 files', '*.mp3'), ('All files', '*.*')])
        if not file: return
        self.current_file = file
        self.label_file.config(text=f'File: {os.path.basename(file)}')
        media = self.instance.media_new(str(file))
        self.player.set_media(media)
        self.play_manual()

    def play_manual(self):
        """Manually starts playback, finding a default MP3 if none is loaded."""
        if not self.current_file:
            default = find_default_mp3()
            if default:
                self.current_file = str(default)
                media = self.instance.media_new(self.current_file)
                self.player.set_media(media)
                self.label_file.config(text=f'File: {os.path.basename(self.current_file)}')
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
        self.playback_rate = 1.0
        self.is_playing = False
        self.is_paused = False
        self._update_state_label()

    def start_hand_tracking_subprocess(self):
        """Finds and runs the hand_tracker.py script as a subprocess."""
        if self.subproc and self.subproc.poll() is None:
            print("Hand tracking is already running.")
            return

        script_path = Path(__file__).parent / 'hand-tracker.py'
        if not script_path.exists():
            messagebox.showerror('Missing Script', f'hand-tracker.py not found at {script_path}')
            self.subproc = None
            return

        cmd = [sys.executable, '-u', str(script_path)]
        try:
            self.subproc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception as e:
            messagebox.showerror('Subprocess error', f'Failed to start hand-tracker.py: {e}')
            self.subproc = None
            return

        self.reading = True
        self.reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self.reader_thread.start()
        print("Hand tracking subprocess started.")

    def stop_hand_tracking_subprocess(self):
        """Stops the hand-tracking subprocess."""
        self.reading = False
        if self.subproc and self.subproc.poll() is None:
            try:
                self.subproc.terminate()
                self.subproc.wait(timeout=2)
                print("Hand tracking subprocess terminated.")
            except (subprocess.TimeoutExpired, Exception) as e:
                print(f"Forcing kill on subprocess: {e}")
                self.subproc.kill()
        
        if self.reader_thread and self.reader_thread.is_alive():
            self.reader_thread.join(timeout=1)
            
        self.subproc = None
        self.reader_thread = None
        # Clear the queue
        while not self.queue.empty():
            try: self.queue.get_nowait()
            except queue.Empty: break
            
        print("Hand tracking stopped.")


    def _reader_loop(self):
        """Thread target to read lines from subprocess stdout and put them in a queue."""
        while self.reading and self.subproc and self.subproc.stdout:
            try:
                raw = self.subproc.stdout.readline()
                if raw:
                    line = raw.strip()
                    if line:
                        self.queue.put(line)
                else:
                    # Subprocess closed
                    break
            except Exception:
                break # Exit loop if process dies
        print("Reader loop exited.")

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
        if not self.camera_on: # Don't process gestures if camera is off
            return
            
        action = parse_action_from_line(line)
        if action:
            self.label_action.config(text=f'Action: {action}')
            now = time.time()

            if 'Play/Resume' in action:
                if (now - self.last_action_time['start']) > self.ACTION_COOLDOWN:
                    if not self.is_playing or self.is_paused:
                        if self.is_paused:
                            self.player.play()
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
            
            self._update_state_label()
        elif "No hands detected" in line:
            self.label_action.config(text='Action: (no hands)')


    def _update_state_label(self):
        """Updates the state label with current status, volume, and rate."""
        state_style = 'Stopped.TLabel'
        if self.is_playing and not self.is_paused:
            state = 'playing'
            state_style = 'Playing.TLabel'
        elif self.is_paused:
            state = 'paused'
            state_style = 'Paused.TLabel'
        else:
            state = 'stopped'
            state_style = 'Stopped.TLabel'
            
        rate_str = f"{self.playback_rate:.2f}x"
        self.label_state.config(text=f'State: {state} | Volume: {self.volume} | Rate: {rate_str}', 
                                style=state_style)

    def _on_close(self):
        """Handles window close event, terminating subprocess and stopping player."""
        self.stop_hand_tracking_subprocess()
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

