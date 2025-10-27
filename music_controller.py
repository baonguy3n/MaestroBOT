import os
import sys
import subprocess
import time
import re
import threading
import queue
# from pathlib import Path # os.path is fine

try:
    # Ensure standard 4-space indentation and no leading non-breaking spaces
    import vlc
except Exception:
    print("!!! need 'python-vlc'. 'pip install python-vlc' !!!")
    raise

try:
    # Ensure standard 4-space indentation and no leading non-breaking spaces
    import tkinter as tk
    from tkinter import ttk, font, filedialog, messagebox
except Exception:
    print("!!! tkinter is busted. how?? it should come with python. !!!")
    raise


# finds the first .mp3 file in this folder
def find_default_mp3():
    script_dir = os.path.dirname(os.path.realpath(__file__))
    mp3s = [f for f in os.listdir(script_dir) if f.endswith('.mp3')]
    return os.path.join(script_dir, mp3s[0]) if mp3s else None


class MusicControllerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title('MaestroBOT')
        self.root.geometry("480x600")
        self.root.configure(bg='#2E2E2E') # Dark background

        # --- Style Config ---
        self.style = ttk.Style(self.root)
        self.style.theme_use('clam') # 'clam' looks okay

        self.font_normal = font.Font(family='Segoe UI', size=10)
        self.font_bold = font.Font(family='Segoe UI', size=11, weight='bold')
        self.font_action = font.Font(family='Segoe UI', size=16, weight='bold')
        self.font_state = font.Font(family='Segoe UI', size=14, weight='bold')

        # --- Define Colors ---
        BG_COLOR = '#2E2E2E'; FRAME_COLOR = '#3A3A3A'; TEXT_COLOR = '#E0E0E0'
        BTN_COLOR = '#5C5C5C'; BTN_TEXT = '#FFFFFF'; BTN_ACTIVE = '#6F6F6F'
        INSTR_BG = '#454545'
        PLAY_COLOR = '#40FF40'; PAUSE_COLOR = '#FFB833'; STOP_COLOR = '#FF4040'

        # Style widgets
        self.style.configure('TFrame', background=FRAME_COLOR)
        self.style.configure('TLabel', background=FRAME_COLOR, foreground=TEXT_COLOR, font=self.font_normal)
        self.style.configure('TButton', font=self.font_bold, padding=(10, 5), background=BTN_COLOR, foreground=BTN_TEXT)
        self.style.map('TButton', background=[('active', BTN_ACTIVE)])
        self.style.configure('Instructions.TLabel', background=INSTR_BG, foreground=TEXT_COLOR, relief='solid', borderwidth=1, padding=(10, 10))
        self.style.configure('Playing.TLabel', background=FRAME_COLOR, font=self.font_state, foreground=PLAY_COLOR)
        self.style.configure('Paused.TLabel', background=FRAME_COLOR, font=self.font_state, foreground=PAUSE_COLOR)
        self.style.configure('Stopped.TLabel', background=FRAME_COLOR, font=self.font_state, foreground=STOP_COLOR)

        # --- VLC player ---
        self.instance = vlc.Instance('--audio-filter=scaletempo', '--quiet')
        self.player = self.instance.media_player_new()

        # --- State vars ---
        self.current_file = None
        self.is_playing = False; self.is_paused = False
        self.camera_on = False
        self.volume = 60 # Current actual volume
        self.playback_rate = 1.0 # Current actual rate
        self.target_volume = 60 # Target for smoothing
        self.target_rate = 1.0  # Target for smoothing
        self.player.audio_set_volume(self.volume)

        # --- Fading State ---
        self.is_fading = False
        self.original_volume_on_fade = 60
        self._fade_after_id = None

        # --- Tab Control State ---
        self.control_mode = "static"
        self.prev_slider_data = {'R_X': None, 'R_Y': None}
        self.SLIDER_DEADZONE_X = 15; self.SLIDER_DEADZONE_Y = 10

        # --- Smoothing Loop ---
        self._smooth_update_id = None # Store ID for cancellation

        # --- Tabbed GUI ---
        self.notebook = ttk.Notebook(root)
        self.static_tab = ttk.Frame(self.notebook, style='TFrame', padding=(10, 10))
        self.notebook.add(self.static_tab, text='Static Gestures')
        static_instructions = ("...") # Same as before
        self.label_static_instr = ttk.Label(self.static_tab, text=static_instructions, justify=tk.LEFT, style='Instructions.TLabel')
        self.label_static_instr.pack(fill='x')

        self.slider_tab = ttk.Frame(self.notebook, style='TFrame', padding=(10, 10))
        self.notebook.add(self.slider_tab, text='Slider Controls')
        slider_instructions = ("...") # Same as before
        self.label_slider_instr = ttk.Label(self.slider_tab, text=slider_instructions, justify=tk.LEFT, style='Instructions.TLabel')
        self.label_slider_instr.pack(fill='x')

        self.notebook.pack(fill='x', padx=10, pady=(10,0)) # Add padding
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        # --- Status Labels Frame ---
        status_frame = ttk.Frame(root, padding=(10, 10)); status_frame.pack(fill='x')
        self.label_file = ttk.Label(status_frame, text='File: (none)', wraplength=450); self.label_file.pack(pady=(5, 10))
        self.label_action = ttk.Label(status_frame, text='Action: (waiting)', font=self.font_action, style='TLabel'); self.label_action.pack(pady=(10, 10))
        self.label_state = ttk.Label(status_frame, text='State: stopped | Volume: 60 | Rate: 1.00x', style='Stopped.TLabel'); self.label_state.pack(pady=(10, 10))

        # --- Manual Controls Frame ---
        btn_frame = ttk.Frame(root, padding=(10, 10)); btn_frame.pack()
        btn_frame.columnconfigure((0, 1, 2, 3), weight=1)
        ttk.Button(btn_frame, text='Load MP3', command=self.load_file).grid(row=0, column=0, padx=5, sticky='ew')
        ttk.Button(btn_frame, text='Play', command=self.play_manual).grid(row=0, column=1, padx=5, sticky='ew')
        ttk.Button(btn_frame, text='Pause', command=self.pause_manual).grid(row=0, column=2, padx=5, sticky='ew')
        ttk.Button(btn_frame, text='Stop', command=self.stop_manual).grid(row=0, column=3, padx=5, sticky='ew')

        # --- Camera/Crash Controls ---
        cam_frame = ttk.Frame(root, padding=(10, 15)); cam_frame.pack(fill='x')
        self.btn_camera_toggle = ttk.Button(cam_frame, text='Turn Camera OFF', command=self.toggle_camera, width=25); self.btn_camera_toggle.pack(pady=5)

        # --- Threading stuff ---
        self.queue = queue.Queue(); self.subproc = None; self.reader_thread = None; self.reading = False
        self._poll_after_id = None

        # --- Bottom frame for crash button ---
        bottom_frame = ttk.Frame(root, padding=(10, 10)); bottom_frame.pack(fill='x', side='bottom')
        self.style.configure('Crash.TButton', background='#a00', foreground='white', font=self.font_bold)
        self.style.map('Crash.TButton', background=[('active', '#c00')])
        self.btn_crash = ttk.Button(bottom_frame, text='Force Crash', command=self.force_crash, style='Crash.TButton'); self.btn_crash.pack(side='right', padx=10, pady=10)

        # Start subprocess automatically
        self.toggle_camera()
        # Start loops
        self._poll_after_id = self.root.after(100, self._poll_queue)
        self._smooth_update_id = self.root.after(50, self._smooth_update_loop) # Start smoothing loop
        # Handle closing
        self.root.protocol('WM_DELETE_WINDOW', self._on_close)

    def _on_tab_changed(self, event):
        current_tab_name = self.notebook.tab(self.notebook.select(), "text")
        if current_tab_name == "Static Gestures":
            self.control_mode = "static"
            # When switching TO static, set targets to current actual values
            self.target_volume = self.volume
            self.target_rate = self.playback_rate
        else:
            self.control_mode = "slider"
            # When switching TO slider, ensure targets match current for smooth start if needed
            self.target_volume = self.volume
            self.target_rate = self.playback_rate
        self.prev_slider_data = {'R_X': None, 'R_Y': None} # Reset slider memory
        print(f"INFO: Control mode changed to: {self.control_mode}")

    def force_crash(self):
        print("INFO: Stopping camera before crashing...")
        self.stop_hand_tracking_subprocess()
        print("INFO: Crashing as requested!")
        raise Exception("Forced crash.")

    def toggle_camera(self):
        if self.camera_on:
            self.stop_hand_tracking_subprocess()
            self.camera_on = False
            self.btn_camera_toggle.config(text='Turn Camera ON')
            self.label_action.config(text='Action: Camera OFF')
        else:
            self.start_hand_tracking_subprocess()
            if self.subproc:
                self.camera_on = True
                self.btn_camera_toggle.config(text='Turn Camera OFF')
                self.label_action.config(text='Action: (waiting)')
            else: # Start failed
                 self.camera_on = False
                 self.btn_camera_toggle.config(text='Turn Camera ON')
                 self.label_action.config(text='Action: Start Failed')

    def load_file(self):
        file = filedialog.askopenfilename(filetypes=[('MP3 files', '*.mp3'), ('All files', '*.*')])
        if not file: return
        self.current_file = file
        self.label_file.config(text=f'File: {os.path.basename(file)}')
        media = self.instance.media_new(str(file))
        self.player.set_media(media)
        print(f"INFO: File loaded: {os.path.basename(file)}, attempting to play...")
        self.play_manual()

    def play_manual(self):
        if self.is_fading: return
        try: player_state = self.player.get_state()
        except Exception: player_state = None
        if player_state == vlc.State.Playing: return

        if not self.current_file:
            default = find_default_mp3();
            if default: self.current_file = str(default); media = self.instance.media_new(self.current_file); self.player.set_media(media); self.label_file.config(text=f'File: {os.path.basename(self.current_file)}')
            else: return # Silently fail

        print("INFO: Calling self.player.play()")
        success = self.player.play()
        if success == 0:
            self.is_playing = True; self.is_paused = False
            # Ensure actual volume/rate match internal targets immediately on play
            self.volume = self.target_volume
            self.playback_rate = self.target_rate
            self.player.audio_set_volume(self.volume)
            self.player.set_rate(self.playback_rate)
            self._update_state_label()
        else: print(f"WARNING: self.player.play() returned {success}.")

    def pause_manual(self):
        if self.is_fading: return
        try: player_state = self.player.get_state()
        except Exception: player_state = None
        if player_state != vlc.State.Playing: return

        print("INFO: Calling self.player.pause()")
        self.player.pause()
        self.is_paused = True; self.is_playing = False
        self._update_state_label()

    def stop_manual(self):
        # Manually stops playback (HARD stop, for the button)
        print("INFO: Stop button pressed.")
        if self.is_fading:
            print("INFO: Cancelling fade due to stop.")
            # --- CORRECTED SECTION ---
            if self._fade_after_id:
                try:
                    self.root.after_cancel(self._fade_after_id)
                except tk.TclError: # Handle case where ID might be invalid
                    # print("INFO: Error cancelling fade (already cancelled or invalid ID).") # Optional
                    pass
                except Exception as e:
                    print(f"ERROR: Unexpected error cancelling fade: {e}")
                finally:
                    self._fade_after_id = None # Clear ID regardless

        print("INFO: Calling self.player.stop()")
        self.player.stop()
        print("INFO: Resetting state after stop.")
        self.is_playing = False; self.is_paused = False
        # Reset targets and actual values on stop
        self.volume = 60; self.target_volume = 60
        self.playback_rate = 1.0; self.target_rate = 1.0
        self.player.audio_set_volume(self.volume)
        self.player.set_rate(self.playback_rate)
        self._update_state_label()

    def fade_and_pause(self):
        try: player_state = self.player.get_state()
        except Exception: player_state = None
        if player_state != vlc.State.Playing or self.is_fading: return

        print("INFO: Starting fade to pause...")
        self.is_fading = True
        self.original_volume_on_fade = self.player.audio_get_volume()
        if self._fade_after_id: 
            try: self.root.after_cancel(self._fade_after_id); 
            except: pass
        self._fade_after_id = self.root.after(50, self._fade_loop_pause)

    def _fade_loop_pause(self):
        self._fade_after_id = None
        if not self.is_fading or not self.root.winfo_exists():
            if not self.is_fading and self.player.is_playing():
                 try: self.player.audio_set_volume(self.original_volume_on_fade)
                 except Exception: pass
            return

        current_vol = self.player.audio_get_volume()
        step_down = max(1, self.original_volume_on_fade // 10 if self.original_volume_on_fade > 0 else 1)
        new_vol = max(0, current_vol - step_down)
        self.player.audio_set_volume(new_vol)

        if new_vol > 0:
            if self.is_fading and self.root.winfo_exists():
                self._fade_after_id = self.root.after(50, self._fade_loop_pause)
            elif not self.is_fading: # Fade cancelled
                self.player.audio_set_volume(self.original_volume_on_fade)
        else: # Fade complete
            self.player.pause()
            self.player.audio_set_volume(self.original_volume_on_fade)
            self.is_paused = True; self.is_playing = False; self.is_fading = False
            self._update_state_label()

    def start_hand_tracking_subprocess(self):
        if self.subproc and self.subproc.poll() is None: return
        script_dir = os.path.dirname(os.path.realpath(__file__))
        script_path = os.path.join(script_dir, 'hand-tracker.py')
        if not os.path.exists(script_path):
            messagebox.showerror('Missing Script', f'hand-tracker.py not found at {script_path}'); return
        cmd = [sys.executable, '-u', str(script_path)]
        try:
            print("INFO: Starting hand-tracking subprocess...")
            self.subproc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, # Hide stderr
                                            text=True, bufsize=1, creationflags=subprocess.CREATE_NO_WINDOW,
                                            encoding='utf-8', errors='ignore')
        except Exception as e:
            messagebox.showerror('Subprocess error', f'Failed to start hand-tracker.py: {e}'); self.subproc = None; return
        self.reading = True
        self.reader_thread = threading.Thread(target=self._reader_loop, daemon=True); self.reader_thread.start()
        print("INFO: Hand tracking subprocess started.")

    def stop_hand_tracking_subprocess(self):
        print("INFO: Stopping hand tracking...")
        self.reading = False; sub = self.subproc
        if sub and sub.poll() is None:
            try:
                sub.terminate()
                try: sub.wait(timeout=1)
                except subprocess.TimeoutExpired: sub.kill()
            except Exception as e: print(f"ERROR: Error terminating subprocess: {e}"); sub.kill()
        if hasattr(self, 'reader_thread') and self.reader_thread and self.reader_thread.is_alive(): self.reader_thread.join(timeout=1)
        self.subproc = None; self.reader_thread = None
        while not self.queue.empty(): 
            try: self.queue.get_nowait(); 
            except queue.Empty: break
        print("INFO: Hand tracking stopped.")

    def _reader_loop(self):
        while self.reading:
            sub = self.subproc
            if not sub or not sub.stdout or sub.stdout.closed: break
            try:
                raw = sub.stdout.readline()
                if raw: line = raw.strip();
                if line: self.queue.put(line)
                else: break # EOF
            except Exception: break # Error or pipe closed

    def _poll_queue(self):
        try:
            for _ in range(10): # Process up to 10 messages per cycle
                if self.queue.empty(): break
                line = self.queue.get_nowait()
                self._handle_line(line)
        except queue.Empty: pass
        except Exception as e: print(f"ERROR: Error processing queue: {e}")
        finally:
             if hasattr(self.root, 'winfo_exists') and self.root.winfo_exists():
                 self._poll_after_id = self.root.after(50, self._poll_queue) # Poll faster

    # --- (NEW) Smoothing Loop ---
    def _smooth_update_loop(self):
        """Periodically adjusts volume and rate towards target values."""
        if not self.root.winfo_exists(): return # Stop if window closed

        vol_changed = False
        rate_changed = False
        current_vlc_vol = self.player.audio_get_volume() # Get actual current vol
        current_vlc_rate = self.player.get_rate() # Get actual current rate

        # Smooth Volume (only adjust if not fading out)
        if not self.is_fading and abs(self.target_volume - self.volume) > 1: # Check internal 'actual' volume
            step = 2 if self.target_volume > self.volume else -2
            self.volume += step
            # Clamp value just in case
            self.volume = max(0, min(100, self.volume))
            # Only call VLC if the new internal value is different from VLC's actual
            if self.volume != current_vlc_vol:
                # print(f"Smooth Vol: Target={self.target_volume}, Current={current_vlc_vol}, Stepping to {self.volume}") # DEBUG
                self.player.audio_set_volume(self.volume)
                vol_changed = True

        # Smooth Rate
        if abs(self.target_rate - self.playback_rate) > 0.02: # Check internal 'actual' rate
            step = 0.05 if self.target_rate > self.playback_rate else -0.05
            self.playback_rate += step
            # Clamp value
            self.playback_rate = max(0.25, min(3.0, self.playback_rate))
             # Only call VLC if the new internal value is different from VLC's actual
            if abs(self.playback_rate - current_vlc_rate) > 0.01:
                # print(f"Smooth Rate: Target={self.target_rate:.2f}, Current={current_vlc_rate:.2f}, Stepping to {self.playback_rate:.2f}") # DEBUG
                self.player.set_rate(self.playback_rate)
                rate_changed = True

        # Update label if changes occurred via smoothing
        if vol_changed or rate_changed:
            self._update_state_label()

        # Schedule next run
        self._smooth_update_id = self.root.after(50, self._smooth_update_loop)

    # --- Parsing and Logic Dispatcher ---

    def _parse_tracker_data(self, line: str) -> dict | None:
        data = {}
        if not line or '|' not in line or ':' not in line or "_Gesture:" not in line: return None
        try:
            parts = line.split('|'); valid_keys = {"L_Gesture", "L_X", "L_Y", "R_Gesture", "R_X", "R_Y"}
            has_hand = False
            for part in parts:
                key, val = part.split(':', 1); key, val = key.strip(), val.strip()
                if key in valid_keys:
                    if '_X' in key or '_Y' in key: data[key] = int(val) if val != 'None' else None
                    else: data[key] = val; has_hand |= (val != "No Hand")
            if not has_hand: return None
            data.setdefault("L_Gesture", "No Hand"); data.setdefault("L_X", None); data.setdefault("L_Y", None)
            data.setdefault("R_Gesture", "No Hand"); data.setdefault("R_X", None); data.setdefault("R_Y", None)
            return data
        except Exception: return None

    def _handle_line(self, line: str):
        if not self.camera_on or self.is_fading: return
        if line == "No hands detected.":
            self.label_action.config(text='Action: (no hands)')
            self.prev_slider_data = {'R_X': None, 'R_Y': None}
            return

        data = self._parse_tracker_data(line)
        if not data: return # Ignore invalid lines

        lg = data.get('L_Gesture', 'N/A'); rg = data.get('R_Gesture', 'N/A')
        self.label_action.config(text=f"L: {lg} | R: {rg}")

        if self.control_mode == "static": self._handle_static_mode(data)
        else: self._handle_slider_mode(data)

        # Update label immediately after handling line if not smoothing
        # If smoothing, the loop will update the label as values change
        # if self.control_mode == "slider": # Slider updates volume/rate directly
        if self.root.winfo_exists(): self._update_state_label()


    def _handle_static_mode(self, data: dict):
        left_gesture = data.get('L_Gesture'); right_gesture = data.get('R_Gesture')

        # Play/Pause
        if left_gesture == "Open Hand" and right_gesture == "Open Hand":
            if not self.is_playing or self.is_paused: self.play_manual()
        elif left_gesture == "Closed Fist" and right_gesture == "Closed Fist":
             if self.is_playing and not self.is_paused: self.fade_and_pause()

        # Set TARGET Volume (loop will handle smoothing)
        target_vol = self.target_volume # Keep current target if no gesture matches
        vol_gesture_detected = False
        if left_gesture == "One Finger": target_vol = 25; vol_gesture_detected=True
        elif left_gesture == "Two Fingers": target_vol = 50; vol_gesture_detected=True
        elif left_gesture == "Three Fingers": target_vol = 75; vol_gesture_detected=True
        elif left_gesture == "Four Fingers": target_vol = 100; vol_gesture_detected=True
        if vol_gesture_detected and target_vol != self.target_volume:
            print(f"INFO: Static - Setting Target Volume -> {target_vol}") # INFO
            self.target_volume = target_vol
            # Don't call player.audio_set_volume here

        # Set TARGET Rate (loop will handle smoothing)
        target_rate = self.target_rate # Keep current target if no gesture matches
        rate_gesture_detected = False
        if right_gesture == "One Finger": target_rate = 0.5; rate_gesture_detected=True
        elif right_gesture == "Two Fingers": target_rate = 0.75; rate_gesture_detected=True
        elif right_gesture == "Three Fingers": target_rate = 1.0; rate_gesture_detected=True
        elif right_gesture == "Four Fingers": target_rate = 1.5; rate_gesture_detected=True
        if rate_gesture_detected and abs(target_rate - self.target_rate) > 0.01:
            print(f"INFO: Static - Setting Target Rate -> {target_rate:.2f}") # INFO
            self.target_rate = target_rate
            # Don't call player.set_rate here

    def _handle_slider_mode(self, data: dict):
        left_gesture = data.get('L_Gesture'); right_gesture = data.get('R_Gesture')

        # Play/Pause (Direct action, no smoothing needed)
        if left_gesture == "Open Hand":
            if not self.is_playing or self.is_paused: self.play_manual()
        elif left_gesture == "Closed Fist":
            if self.is_playing and not self.is_paused: self.fade_and_pause()

        # Sliders (Direct action, update internal state AND call VLC)
        R_X = data.get('R_X'); R_Y = data.get('R_Y')
        prev_x = self.prev_slider_data.get('R_X'); prev_y = self.prev_slider_data.get('R_Y')

        if right_gesture == "Open Hand" and R_X is not None: # Speed
            if prev_x is not None:
                delta_x = R_X - prev_x
                if abs(delta_x) > self.SLIDER_DEADZONE_X:
                    new_target_rate = self.playback_rate + (delta_x * 0.005)
                    new_target_rate = max(0.25, min(3.0, new_target_rate))
                    if abs(new_target_rate - self.playback_rate) > 0.01:
                        print(f"INFO: Slider - Speed -> {new_target_rate:.2f}") # INFO
                        self.playback_rate = new_target_rate
                        self.target_rate = new_target_rate # Keep target synced
                        self.player.set_rate(self.playback_rate)
                    self.prev_slider_data['R_X'] = R_X
            else: self.prev_slider_data['R_X'] = R_X
            self.prev_slider_data['R_Y'] = None
        elif right_gesture == "Closed Fist" and R_Y is not None: # Volume
            if prev_y is not None:
                delta_y = R_Y - prev_y
                if abs(delta_y) > self.SLIDER_DEADZONE_Y:
                    new_target_vol = self.volume - (delta_y * 0.75)
                    new_target_vol = int(max(0, min(100, new_target_vol)))
                    if new_target_vol != self.volume:
                         print(f"INFO: Slider - Volume -> {new_target_vol}") # INFO
                         self.volume = new_target_vol
                         self.target_volume = new_target_vol # Keep target synced
                         self.player.audio_set_volume(self.volume)
                         if not self.is_fading: self.original_volume_on_fade = self.volume
                    self.prev_slider_data['R_Y'] = R_Y
            else: self.prev_slider_data['R_Y'] = R_Y
            self.prev_slider_data['R_X'] = None
        else: # Reset memory
            if self.prev_slider_data['R_X'] is not None or self.prev_slider_data['R_Y'] is not None:
                self.prev_slider_data['R_X'] = None; self.prev_slider_data['R_Y'] = None

    def _update_state_label(self):
        # Optimized to reduce calls if window is closing
        if not hasattr(self.root, 'winfo_exists') or not self.root.winfo_exists(): return

        state_style = 'Stopped.TLabel'; state = 'stopped'
        # Display the INTERNALLY tracked volume/rate, as VLC query can be slow/laggy
        current_display_vol = self.volume
        current_display_rate = self.playback_rate

        try: # Still try to get actual state for accuracy
            player_state = self.player.get_state()
            if player_state == vlc.State.Playing: state = 'playing'; state_style = 'Playing.TLabel'
            elif player_state == vlc.State.Paused: state = 'paused'; state_style = 'Paused.TLabel'
            elif player_state in [vlc.State.Stopped, vlc.State.Ended, vlc.State.Error]: state = 'stopped'; state_style = 'Stopped.TLabel'
        except Exception: # Fallback to internal flags if VLC query fails
             if self.is_playing and not self.is_paused: state = 'playing'; state_style = 'Playing.TLabel'
             elif self.is_paused: state = 'paused'; state_style = 'Paused.TLabel'

        # Ensure flags match observed state if possible
        if state == 'playing': self.is_playing=True; self.is_paused=False
        elif state == 'paused': self.is_playing=False; self.is_paused=True
        else: self.is_playing=False; self.is_paused=False

        rate_str = f"{current_display_rate:.2f}x"
        vol_str = f"{current_display_vol}"
        self.label_state.config(text=f'State: {state} | Volume: {vol_str} | Rate: {rate_str}', style=state_style)

    def _on_close(self):
        print("INFO: Close window requested.")
        # Cancel loops first
        if self._fade_after_id: 
            try: self.root.after_cancel(self._fade_after_id); 
            except: pass
        if self._poll_after_id: 
            try: self.root.after_cancel(self._poll_after_id); 
            except: pass
        if self._smooth_update_id: 
            try: self.root.after_cancel(self._smooth_update_id); 
            except: pass
        self._fade_after_id = None; self._poll_after_id = None; self._smooth_update_id = None

        self.stop_hand_tracking_subprocess()
        try: print("INFO: Stopping VLC player on close."); self.player.stop()
        except Exception as e: print(f"ERROR: Error stopping player: {e}")
        try: print("INFO: Releasing VLC instance."); self.instance.release()
        except Exception as e: print(f"ERROR: Error releasing instance: {e}")
        try: print("INFO: Destroying root window."); self.root.destroy()
        except tk.TclError: print("INFO: Root window already destroyed.")


def main():
    root = tk.Tk()
    app = MusicControllerGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()