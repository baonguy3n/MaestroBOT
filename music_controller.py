import os
import sys
import subprocess
import time
import re
import threading
import queue
# from pathlib import Path # os.path is fine

try:
    import vlc
except Exception:
    print("!!! need 'python-vlc'. 'pip install python-vlc' !!!")
    raise

try:
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
        BG_COLOR = '#2E2E2E'
        FRAME_COLOR = '#3A3A3A'
        TEXT_COLOR = '#E0E0E0'
        BTN_COLOR = '#5C5C5C'
        BTN_TEXT = '#FFFFFF'
        BTN_ACTIVE = '#6F6F6F'
        INSTR_BG = '#454545'

        PLAY_COLOR = '#40FF40'  # Bright Green
        PAUSE_COLOR = '#FFB833' # Bright Orange
        STOP_COLOR = '#FF4040'   # Bright Red

        # Style widgets
        self.style.configure('TFrame', background=FRAME_COLOR)
        self.style.configure('TLabel', background=FRAME_COLOR, foreground=TEXT_COLOR, font=self.font_normal)
        self.style.configure('TButton', font=self.font_bold, padding=(10, 5),
                             background=BTN_COLOR, foreground=BTN_TEXT)
        self.style.map('TButton', background=[('active', BTN_ACTIVE)])

        self.style.configure('Instructions.TLabel', background=INSTR_BG, foreground=TEXT_COLOR,
                             relief='solid', borderwidth=1, padding=(10, 10))

        self.style.configure('Playing.TLabel', background=FRAME_COLOR, font=self.font_state, foreground=PLAY_COLOR)
        self.style.configure('Paused.TLabel', background=FRAME_COLOR, font=self.font_state, foreground=PAUSE_COLOR)
        self.style.configure('Stopped.TLabel', background=FRAME_COLOR, font=self.font_state, foreground=STOP_COLOR)

        # --- VLC player ---
        self.instance = vlc.Instance('--audio-filter=scaletempo') # scaletempo is magic
        self.player = self.instance.media_player_new()

        # --- State vars ---
        self.current_file = None
        self.is_playing = False # Reflects if WE think it should be playing
        self.is_paused = False  # Reflects if WE think it should be paused
        self.camera_on = False # Will be toggled to True on start
        self.volume = 60 # Internal target volume
        self.playback_rate = 1.0 # Internal target rate
        self.player.audio_set_volume(self.volume) # Initialize VLC volume

        # --- Fading State ---
        self.is_fading = False
        self.original_volume_on_fade = 60
        self._fade_after_id = None # Initialize fade ID

        # --- Tab Control State ---
        self.control_mode = "static" # "static" or "slider"
        self.prev_slider_data = {'R_X': None, 'R_Y': None}
        self.SLIDER_DEADZONE_X = 15 # Pixels to move before registering
        self.SLIDER_DEADZONE_Y = 10 # Pixels to move before registering


        # --- Tabbed GUI ---
        self.notebook = ttk.Notebook(root)

        # --- Static Tab ---
        self.static_tab = ttk.Frame(self.notebook, style='TFrame', padding=(10, 10))
        self.notebook.add(self.static_tab, text='Static Gestures')

        static_instructions = (
            "Gesture Controls (Hands must work together):\n"
            "\n"
            "Playback (Main):\n"
            "• Both Hands Open → Play/Resume\n"
            "• Both Hands Closed → Fade to Pause\n"
            "\n"
            "Left Hand (Volume):\n"
            "• One Finger → 25%\n"
            "• Two Fingers → 50%\n"
            "• Three Fingers → 75%\n"
            "• Four Fingers → 100%\n"
            "\n"
            "Right Hand (Speed):\n"
            "• One Finger → 0.50x\n"
            "• Two Fingers → 0.75x\n"
            "• Three Fingers → 1.00x\n"
            "• Four Fingers → 1.50x"
        )
        self.label_static_instr = ttk.Label(self.static_tab, text=static_instructions,
                                            justify=tk.LEFT,
                                            style='Instructions.TLabel')
        self.label_static_instr.pack(fill='x')

        # --- Slider Tab ---
        self.slider_tab = ttk.Frame(self.notebook, style='TFrame', padding=(10, 10))
        self.notebook.add(self.slider_tab, text='Slider Controls')

        slider_instructions = (
            "Gesture Controls (Hands work independently):\n"
            "\n"
            "Left Hand (Playback):\n"
            "• Open Hand → Play/Resume\n"
            "• Closed Fist → Fade to Pause\n"
            "\n"
            "Right Hand (Sliders):\n"
            "• Open Hand + Move L/R → Speed\n"
            "   (Right = Faster, Left = Slower)\n"
            "• Closed Fist + Move U/D → Volume\n"
            "   (Up = Louder, Down = Quieter)"
        )
        self.label_slider_instr = ttk.Label(self.slider_tab, text=slider_instructions,
                                            justify=tk.LEFT,
                                            style='Instructions.TLabel')
        self.label_slider_instr.pack(fill='x')

        self.notebook.pack(fill='x')
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        # --- End of Tabbed GUI ---


        # --- Status Labels Frame (Below tabs) ---
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
        btn_frame.columnconfigure((0, 1, 2, 3), weight=1) # Make buttons space out

        ttk.Button(btn_frame, text='Load MP3', command=self.load_file).grid(row=0, column=0, padx=5, sticky='ew')
        ttk.Button(btn_frame, text='Play', command=self.play_manual).grid(row=0, column=1, padx=5, sticky='ew')
        ttk.Button(btn_frame, text='Pause', command=self.pause_manual).grid(row=0, column=2, padx=5, sticky='ew')
        ttk.Button(btn_frame, text='Stop', command=self.stop_manual).grid(row=0, column=3, padx=5, sticky='ew')

        # --- Camera/Crash Controls ---
        cam_frame = ttk.Frame(root, padding=(10, 15))
        cam_frame.pack(fill='x')
        self.btn_camera_toggle = ttk.Button(cam_frame, text='Turn Camera OFF', command=self.toggle_camera, width=25)
        self.btn_camera_toggle.pack(pady=5)

        # --- Threading stuff ---
        self.queue = queue.Queue()
        self.subproc = None
        self.reader_thread = None
        self.reading = False
        self._poll_after_id = None # Store poll ID for cleanup

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
        self._poll_after_id = self.root.after(100, self._poll_queue) # Store ID
        # Handle closing
        self.root.protocol('WM_DELETE_WINDOW', self._on_close)

    def _on_tab_changed(self, event):
        # Updates the control mode when user clicks a tab
        current_tab_name = self.notebook.tab(self.notebook.select(), "text")
        if current_tab_name == "Static Gestures":
            self.control_mode = "static"
        else:
            self.control_mode = "slider"

        # Reset slider memory to prevent jumps
        self.prev_slider_data = {'R_X': None, 'R_Y': None}
        print(f"DEBUG: Control mode changed to: {self.control_mode}") # DEBUG

    def force_crash(self):
        # for debugging
        print("Stopping camera before crashing...")
        self.stop_hand_tracking_subprocess()

        print("Crashing as requested!")
        raise Exception("Forced crash.")

    def toggle_camera(self):
        # Toggles the hand-tracking subprocess
        if self.camera_on:
            # Turn it OFF
            self.stop_hand_tracking_subprocess()
            self.camera_on = False
            self.btn_camera_toggle.config(text='Turn Camera ON')
            self.label_action.config(text='Action: Camera OFF')
            self.style.map('TButton', background=[('active', BTN_ACTIVE)]) # Re-apply default map
        else:
            # Turn it ON
            self.start_hand_tracking_subprocess()
            if self.subproc: # Check if start was successful
                self.camera_on = True
                self.btn_camera_toggle.config(text='Turn Camera OFF')
                self.label_action.config(text='Action: (waiting)')

    def load_file(self):
        # Opens a file dialog to load an MP3
        file = filedialog.askopenfilename(filetypes=[('MP3 files', '*.mp3'), ('All files', '*.*')])
        if not file: return
        self.current_file = file
        self.label_file.config(text=f'File: {os.path.basename(file)}')
        media = self.instance.media_new(str(file))
        self.player.set_media(media)
        # Automatically play after loading
        print("DEBUG: File loaded, attempting to play...") # DEBUG
        self.play_manual() # Try to play immediately

    def play_manual(self):
        # Manually starts playback, finds a default MP3 if none is loaded
        if self.is_fading:
            print("DEBUG: Play blocked: currently fading.") # DEBUG
            return # Don't play while fading

        # Check actual player state if possible
        try:
             player_state = self.player.get_state()
             # If it's already playing, do nothing
             if player_state == vlc.State.Playing:
                 print("DEBUG: Play called but VLC state is already Playing.")
                 if not self.is_playing or self.is_paused: # Correct flags if needed
                     self.is_playing = True; self.is_paused = False; self._update_state_label()
                 return
        except Exception:
             # Fallback to flags
             if self.is_playing and not self.is_paused:
                 print("DEBUG: Play called but flags indicate already playing.") #DEBUG
                 return

        if not self.current_file:
            print("DEBUG: No file loaded, searching for default...") # DEBUG
            default = find_default_mp3()
            if default:
                self.current_file = str(default)
                media = self.instance.media_new(self.current_file)
                self.player.set_media(media)
                self.label_file.config(text=f'File: {os.path.basename(self.current_file)}')
                print(f"DEBUG: Default file found and loaded: {self.current_file}") # DEBUG
            else:
                print("DEBUG: Play failed: No file loaded and no default found.") # DEBUG
                return

        print(f"DEBUG: *** Calling self.player.play() ***") # DEBUG
        success = self.player.play()
        # Update flags ONLY IF play() likely succeeded (returns 0 on success)
        if success == 0:
            print("DEBUG: play() call likely succeeded. Updating state flags.")
            self.is_playing = True
            self.is_paused = False
            # Re-apply volume and rate just in case they were reset
            self.player.audio_set_volume(self.volume)
            self.player.set_rate(self.playback_rate)
            self._update_state_label() # Update GUI immediately
        else:
             print(f"DEBUG: self.player.play() returned {success}. Not updating state flags.")


    def pause_manual(self):
        # Manually pauses playback
        if self.is_fading:
             print("DEBUG: Pause blocked: currently fading.") # DEBUG
             return # Don't pause while fading

        # Check actual player state if possible - only pause if playing
        try:
             player_state = self.player.get_state()
             if player_state != vlc.State.Playing:
                  print(f"DEBUG: Pause called but VLC state is not Playing (State: {player_state}).")
                  # Correct flags if state is Paused but flags disagree
                  if player_state == vlc.State.Paused and not self.is_paused:
                      self.is_playing = False; self.is_paused = True; self._update_state_label()
                  # Correct flags if state is Stopped but flags disagree
                  elif player_state in [vlc.State.Stopped, vlc.State.Ended, vlc.State.Error] and (self.is_playing or self.is_paused):
                       self.is_playing = False; self.is_paused = False; self._update_state_label()
                  return
        except Exception:
             # Fallback to flags: only pause if playing and not paused
             if not self.is_playing or self.is_paused:
                 print(f"DEBUG: Pause called but flags indicate not playing or already paused (playing={self.is_playing}, paused={self.is_paused}).")
                 return


        print("DEBUG: *** Calling self.player.pause() ***") # DEBUG
        self.player.pause() # Note: vlc pause is a toggle, but we guard with state checks
        # Update flags assuming success
        self.is_paused = True
        self.is_playing = False
        self._update_state_label() # Update GUI


    def stop_manual(self):
        # Manually stops playback (HARD stop, for the button)
        print("DEBUG: Stop button pressed.") # DEBUG
        if self.is_fading:
            print("DEBUG: Cancelling fade due to stop.") # DEBUG
            if self._fade_after_id:
                try: self.root.after_cancel(self._fade_after_id)
                except: pass
                self._fade_after_id = None
            self.is_fading = False

        print("DEBUG: *** Calling self.player.stop() ***") # DEBUG
        self.player.stop()
        print("DEBUG: Resetting state after stop.") # DEBUG
        # Immediately update flags assuming success
        self.is_playing = False
        self.is_paused = False
        # Restore volume and reset rate AFTER stopping
        self.player.audio_set_volume(self.volume)
        self.playback_rate = 1.0 # Reset rate on hard stop
        self.player.set_rate(self.playback_rate) # Apply reset rate
        self._update_state_label() # Update GUI

    # --- Fade and Pause functions ---
    def fade_and_pause(self):
        # Starts the fade-out process
        try: # Check actual player state first
             player_state = self.player.get_state()
             if player_state != vlc.State.Playing:
                 print(f"DEBUG: Fade blocked: Player not in Playing state (State: {player_state})")
                 return
        except Exception: # Fallback to flags
            if self.is_fading or not self.is_playing or self.is_paused:
                 print(f"DEBUG: Fade blocked by flags: fading={self.is_fading}, playing={self.is_playing}, paused={self.is_paused}") # DEBUG
                 return

        print("DEBUG: Starting fade to pause...") # DEBUG
        self.is_fading = True
        self.original_volume_on_fade = self.player.audio_get_volume()
        if self._fade_after_id: # Cancel existing fade if any
             try: self.root.after_cancel(self._fade_after_id)
             except: pass
        self._fade_after_id = self.root.after(50, self._fade_loop_pause) # Store ID

    def _fade_loop_pause(self):
        self._fade_after_id = None # Clear ID now that we are running
        if not self.is_fading: # Check if cancelled before running
             print("DEBUG: Fade loop entered but is_fading is False.")
             self.player.audio_set_volume(self.original_volume_on_fade) # Restore volume
             return

        current_vol = self.player.audio_get_volume()
        step_down = max(1, self.original_volume_on_fade // 10 if self.original_volume_on_fade > 0 else 1)
        new_vol = max(0, current_vol - step_down)

        self.player.audio_set_volume(new_vol)

        if new_vol > 0:
            if self.is_fading and self.root.winfo_exists(): # Keep looping only if still fading and window open
                self._fade_after_id = self.root.after(50, self._fade_loop_pause) # Store ID
            elif not self.is_fading:
                print("DEBUG: Fade cancelled mid-loop.")
                self.player.audio_set_volume(self.original_volume_on_fade) # Restore volume
            # else: window closed, do nothing
        else: # Fade complete
            print("DEBUG: Fade complete. *** Calling self.player.pause() ***") # DEBUG
            self.player.pause()
            print("DEBUG: Restoring volume post-fade pause.") # DEBUG
            self.player.audio_set_volume(self.original_volume_on_fade) # Restore volume for next play
            # Update state flags
            self.is_paused = True
            self.is_playing = False
            self.is_fading = False
            # self._fade_after_id = None # Already cleared or None
            print("DEBUG: Fade complete state updated.") # DEBUG
            self._update_state_label() # Update GUI
    # --- End of fade functions ---

    def start_hand_tracking_subprocess(self):
        # finds and runs the hand_tracker.py script
        if self.subproc and self.subproc.poll() is None:
            print("Hand tracking is already running.")
            return

        script_dir = os.path.dirname(os.path.realpath(__file__))
        script_path = os.path.join(script_dir, 'hand-tracker.py')

        if not os.path.exists(script_path):
            messagebox.showerror('Missing Script', f'hand-tracker.py not found at {script_path}')
            self.subproc = None
            return

        cmd = [sys.executable, '-u', str(script_path)]
        try:
             # Keep stderr visible for now
            self.subproc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                            text=True, bufsize=1, creationflags=subprocess.CREATE_NO_WINDOW,
                                            encoding='utf-8', errors='ignore')
            self.stderr_thread = threading.Thread(target=self._stderr_reader_loop, daemon=True)
            self.stderr_thread.start()

        except Exception as e:
            messagebox.showerror('Subprocess error', f'Failed to start hand-tracker.py: {e}')
            self.subproc = None
            return

        self.reading = True
        self.reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self.reader_thread.start()
        print("Hand tracking subprocess started.")

    def _stderr_reader_loop(self):
        """Reads stderr from the subprocess to prevent buffer issues and print warnings."""
        print("Stderr reader loop started.")
        while self.reading and self.subproc and self.subproc.stderr and not self.subproc.stderr.closed:
            try:
                line = self.subproc.stderr.readline()
                if line:
                    print(f"STDERR (hand-tracker): {line.strip()}", file=sys.stderr)
                else:
                    # print("Stderr readline returned empty, breaking loop.") # Can be noisy on exit
                    break
            except ValueError:
                 # print("ValueError reading stderr (pipe closed?), breaking loop.")
                 break
            except Exception as e:
                print(f"Exception reading stderr: {e}. Breaking.", file=sys.stderr)
                break
        print("Stderr reader loop exited.")


    def stop_hand_tracking_subprocess(self):
        # Stops the hand-tracking subprocess
        print("Stopping hand tracking...") # DEBUG
        self.reading = False # Signal reader loops to stop
        sub = self.subproc # Local ref in case self.subproc is cleared by another thread
        if sub and sub.poll() is None:
            try:
                print("Terminating subprocess...")
                sub.terminate()
                try: sub.wait(timeout=1)
                except subprocess.TimeoutExpired:
                     print("Terminate timed out, forcing kill...")
                     sub.kill()
                print("Hand tracking subprocess stopped/killed.")
            except Exception as e:
                print(f"Error during subprocess termination: {e}")
                if sub and sub.poll() is None: # Double check before kill
                    print("Forcing kill after termination error...")
                    sub.kill()

        # Wait for reader threads to finish AFTER signaling/stopping proc
        if hasattr(self, 'reader_thread') and self.reader_thread and self.reader_thread.is_alive():
            print("Joining stdout reader thread...")
            self.reader_thread.join(timeout=1)
            # if self.reader_thread.is_alive(): print("Stdout thread join timed out.") # Less critical now
        if hasattr(self, 'stderr_thread') and self.stderr_thread and self.stderr_thread.is_alive():
             print("Joining stderr reader thread...")
             self.stderr_thread.join(timeout=1)
             # if self.stderr_thread.is_alive(): print("Stderr thread join timed out.")

        self.subproc = None
        self.reader_thread = None
        self.stderr_thread = None
        # Clear the queue
        while not self.queue.empty():
            try: self.queue.get_nowait()
            except queue.Empty: break

        print("Hand tracking fully stopped and cleaned up.")


    def _reader_loop(self):
        # thread target to read lines from stdout and put them in a queue
        print("Stdout reader loop started.")
        while self.reading:
            if not self.subproc or not self.subproc.stdout or self.subproc.stdout.closed:
                 # print("Stdout reader loop: subprocess or stdout missing/closed.")
                 break
            try:
                raw = self.subproc.stdout.readline()
                if raw:
                    line = raw.strip()
                    if line:
                        self.queue.put(line)
                else:
                    # print("Stdout readline returned empty, breaking loop.") # Normal on exit
                    break # Subprocess likely closed stdout
            except ValueError: # stdout might be closed during readline
                 print("ValueError reading stdout (pipe closed?), breaking loop.")
                 break
            except Exception as e:
                print(f"Exception in stdout reader loop: {e}. Breaking.")
                break # Exit loop if process dies or other error
        print("Stdout reader loop exited.")

    def _poll_queue(self):
        # Periodically checks the queue for new lines
        lines_processed = 0
        try:
            while not self.queue.empty() and lines_processed < 10: # Process batch of 10 max
                line = self.queue.get_nowait()
                self._handle_line(line)
                lines_processed += 1
        except queue.Empty:
            pass
        except Exception as e:
            print(f"Error processing queue: {e}") # Catch errors here too
        finally:
             if hasattr(self.root, 'winfo_exists') and self.root.winfo_exists():
                 self._poll_after_id = self.root.after(50, self._poll_queue) # Poll slightly faster
             # else: print("DEBUG: Root window destroyed, stopping poll loop.")


    # --- Parsing and Logic Dispatcher ---

    def _parse_tracker_data(self, line: str) -> dict | None:
        # Parses the new data string into a dictionary, returns None if invalid
        data = {}
        # Basic format check
        if not line or '|' not in line or ':' not in line or "_Gesture:" not in line:
            return None
        try:
            parts = line.split('|')
            valid_keys = {"L_Gesture", "L_X", "L_Y", "R_Gesture", "R_X", "R_Y"}
            has_at_least_one_hand = False
            for part in parts:
                split_part = part.split(':', 1)
                if len(split_part) == 2:
                    key, val = split_part[0].strip(), split_part[1].strip()
                    if key in valid_keys:
                        if '_X' in key or '_Y' in key:
                            data[key] = int(val) if val != 'None' else None
                        else:
                            data[key] = val
                            if val != "No Hand": has_at_least_one_hand = True
            if not has_at_least_one_hand: return None
            data.setdefault("L_Gesture", "No Hand"); data.setdefault("L_X", None); data.setdefault("L_Y", None)
            data.setdefault("R_Gesture", "No Hand"); data.setdefault("R_X", None); data.setdefault("R_Y", None)
            return data
        except Exception: # Catch any parsing error (ValueError etc.)
             # print(f"DEBUG: Error parsing line: '{line}' | {e}") # Keep minimal
             return None

    def _handle_line(self, line: str):
        if not self.camera_on or self.is_fading: return

        # print(f"DEBUG: Handling line: '{line}' in mode '{self.control_mode}'") # Noisy

        if line == "No hands detected.":
            self.label_action.config(text='Action: (no hands)')
            self.prev_slider_data = {'R_X': None, 'R_Y': None}
            return

        data = self._parse_tracker_data(line)
        if not data: return # Ignore invalid lines silently now

        # print(f"DEBUG: Parsed: {data}") # Noisy

        lg = data.get('L_Gesture', 'N/A')
        rg = data.get('R_Gesture', 'N/A')
        self.label_action.config(text=f"L: {lg} | R: {rg}")

        if self.control_mode == "static":
            self._handle_static_mode(data)
        else:
            self._handle_slider_mode(data)

        # Update label less frequently or only when state *changes*?
        # For now, keep updating to reflect volume/rate sliders
        if self.root.winfo_exists(): self._update_state_label()


    def _handle_static_mode(self, data: dict):
        # print("DEBUG: Handling static mode") # Noisy
        left_gesture = data.get('L_Gesture')
        right_gesture = data.get('R_Gesture')

        # --- Play/Pause ---
        if left_gesture == "Open Hand" and right_gesture == "Open Hand":
             # Check flags first to avoid redundant calls if already playing
            if not self.is_playing or self.is_paused:
                print("DEBUG: Static - Both Open condition met, calling play_manual()")
                self.play_manual()
        elif left_gesture == "Closed Fist" and right_gesture == "Closed Fist":
             # Check flags first to avoid redundant calls if already paused/stopped
             if self.is_playing and not self.is_paused:
                print("DEBUG: Static - Both Closed condition met, calling fade_and_pause()")
                self.fade_and_pause()

        # --- Volume ---
        target_vol = self.volume # Default to current target
        vol_gesture_detected = None
        if left_gesture == "One Finger": target_vol = 25; vol_gesture_detected = left_gesture
        elif left_gesture == "Two Fingers": target_vol = 50; vol_gesture_detected = left_gesture
        elif left_gesture == "Three Fingers": target_vol = 75; vol_gesture_detected = left_gesture
        elif left_gesture == "Four Fingers": target_vol = 100; vol_gesture_detected = left_gesture

        # Only call if target differs from *internal* target
        if vol_gesture_detected and target_vol != self.volume:
            print(f"DEBUG: Static - Volume change: {vol_gesture_detected} -> Target={target_vol}. Current Internal={self.volume}. *** Calling audio_set_volume({target_vol}) ***")
            self.volume = target_vol # Update internal target FIRST
            self.player.audio_set_volume(self.volume)
            if not self.is_fading: self.original_volume_on_fade = self.volume

        # --- Rate ---
        target_rate = self.playback_rate # Default to current target
        rate_gesture_detected = None
        if right_gesture == "One Finger": target_rate = 0.5; rate_gesture_detected = right_gesture
        elif right_gesture == "Two Fingers": target_rate = 0.75; rate_gesture_detected = right_gesture
        elif right_gesture == "Three Fingers": target_rate = 1.0; rate_gesture_detected = right_gesture
        elif right_gesture == "Four Fingers": target_rate = 1.5; rate_gesture_detected = right_gesture

        # Only call if target differs from *internal* target (with tolerance)
        if rate_gesture_detected and abs(target_rate - self.playback_rate) > 0.01:
            print(f"DEBUG: Static - Rate change: {rate_gesture_detected} -> Target={target_rate:.2f}. Current Internal={self.playback_rate:.2f}. *** Calling set_rate({target_rate:.2f}) ***")
            self.playback_rate = target_rate # Update internal target FIRST
            self.player.set_rate(self.playback_rate)


    def _handle_slider_mode(self, data: dict):
        # print("DEBUG: Handling slider mode") # Noisy
        left_gesture = data.get('L_Gesture')
        right_gesture = data.get('R_Gesture')

        # --- Play/Pause ---
        if left_gesture == "Open Hand":
            if not self.is_playing or self.is_paused:
                 print("DEBUG: Slider - Left Open condition met, calling play_manual()")
                 self.play_manual()
        elif left_gesture == "Closed Fist":
            if self.is_playing and not self.is_paused:
                print("DEBUG: Slider - Left Closed condition met, calling fade_and_pause()")
                self.fade_and_pause()

        # --- Sliders ---
        R_X = data.get('R_X'); R_Y = data.get('R_Y')
        prev_x = self.prev_slider_data.get('R_X'); prev_y = self.prev_slider_data.get('R_Y')

        if right_gesture == "Open Hand" and R_X is not None: # Speed
            if prev_x is not None:
                delta_x = R_X - prev_x
                if abs(delta_x) > self.SLIDER_DEADZONE_X:
                    new_target_rate = self.playback_rate + (delta_x * 0.005)
                    new_target_rate = max(0.25, min(3.0, new_target_rate))
                    if abs(new_target_rate - self.playback_rate) > 0.01: # Check internal target
                        print(f"DEBUG: Slider - Speed change: delta_x={delta_x} -> Target={new_target_rate:.2f}. Current Internal={self.playback_rate:.2f}. *** Calling set_rate({new_target_rate:.2f}) ***")
                        self.playback_rate = new_target_rate # Update internal target
                        self.player.set_rate(self.playback_rate)
                    self.prev_slider_data['R_X'] = R_X # Update pos only on significant move
            else: self.prev_slider_data['R_X'] = R_X # Store initial pos
            self.prev_slider_data['R_Y'] = None # Reset other slider memory

        elif right_gesture == "Closed Fist" and R_Y is not None: # Volume
            if prev_y is not None:
                delta_y = R_Y - prev_y
                if abs(delta_y) > self.SLIDER_DEADZONE_Y:
                    new_target_vol = self.volume - (delta_y * 0.75)
                    new_target_vol = int(max(0, min(100, new_target_vol)))
                    if new_target_vol != self.volume: # Check internal target
                         print(f"DEBUG: Slider - Volume change: delta_y={delta_y} -> Target={new_target_vol}. Current Internal={self.volume}. *** Calling audio_set_volume({new_target_vol}) ***")
                         self.volume = new_target_vol # Update internal target
                         self.player.audio_set_volume(self.volume)
                         if not self.is_fading: self.original_volume_on_fade = self.volume
                    self.prev_slider_data['R_Y'] = R_Y # Update pos only on significant move
            else: self.prev_slider_data['R_Y'] = R_Y # Store initial pos
            self.prev_slider_data['R_X'] = None # Reset other slider memory

        else: # Reset memory if gesture changes or coords missing
            if self.prev_slider_data['R_X'] is not None or self.prev_slider_data['R_Y'] is not None:
                self.prev_slider_data['R_X'] = None; self.prev_slider_data['R_Y'] = None


    def _update_state_label(self):
        # Updates the state label with current status
        if not self.root.winfo_exists(): return

        state_style = 'Stopped.TLabel'; state = 'stopped'
        current_vlc_vol = self.volume; current_vlc_rate = self.playback_rate

        try:
            player_state = self.player.get_state()
            current_vlc_vol = self.player.audio_get_volume()
            current_vlc_rate = self.player.get_rate()

            # Update internal state flags based on actual player state
            if player_state == vlc.State.Playing:
                self.is_playing = True; self.is_paused = False
                state = 'playing'; state_style = 'Playing.TLabel'
            elif player_state == vlc.State.Paused:
                self.is_playing = False; self.is_paused = True
                state = 'paused'; state_style = 'Paused.TLabel'
            else: # Stopped, Ended, Error
                self.is_playing = False; self.is_paused = False
                state = 'stopped'; state_style = 'Stopped.TLabel'
                if player_state != vlc.State.Error: current_vlc_rate = 1.0 # Reset visual rate if stopped

            # Update internal targets ONLY if significantly different (e.g., user used manual buttons)
            # This reduces potential overwrites if gesture logic just ran
            if abs(current_vlc_rate - self.playback_rate) > 0.1: # Larger tolerance
                self.playback_rate = current_vlc_rate
            if abs(current_vlc_vol - self.volume) > 5: # Larger tolerance
                 self.volume = current_vlc_vol

        except Exception: # Fallback to flags if get_state fails
             if self.is_playing and not self.is_paused: state = 'playing'; state_style = 'Playing.TLabel'
             elif self.is_paused: state = 'paused'; state_style = 'Paused.TLabel'
             else: state = 'stopped'; state_style = 'Stopped.TLabel'
             current_vlc_vol = self.volume; current_vlc_rate = self.playback_rate


        rate_str = f"{current_vlc_rate:.2f}x"
        vol_str = f"{current_vlc_vol}"

        self.label_state.config(text=f'State: {state} | Volume: {vol_str} | Rate: {rate_str}', style=state_style)
        # print(f"DEBUG: Updated state label: {state}, Vol:{vol_str}, Rate:{rate_str}") # Noisy


    def _on_close(self):
        # Handles window close event
        print("DEBUG: Close window requested.") # DEBUG
        if self._fade_after_id:
             try: self.root.after_cancel(self._fade_after_id)
             except: pass
             self._fade_after_id = None
        if hasattr(self, '_poll_after_id') and self._poll_after_id:
             try: self.root.after_cancel(self._poll_after_id)
             except: pass
             self._poll_after_id = None

        self.stop_hand_tracking_subprocess() # Stop tracking first
        try:
            print("DEBUG: Stopping VLC player on close.") # DEBUG
            if self.player: self.player.stop()
        except Exception as e:
            print(f"DEBUG: Error stopping player on close: {e}") # DEBUG
        print("DEBUG: Releasing VLC instance.")
        try:
            if self.instance: self.instance.release()
        except Exception as e:
            print(f"DEBUG: Error releasing instance: {e}")
        print("DEBUG: Destroying root window.")
        try: self.root.destroy()
        except tk.TclError: print("DEBUG: Root window already destroyed.")


def main():
    root = tk.Tk()
    app = MusicControllerGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()