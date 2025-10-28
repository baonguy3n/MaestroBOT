import os
import sys
import subprocess
import time
import threading
import queue

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


def find_default_mp3():
    """Finds the first .mp3 file in the script directory."""
    script_dir = os.path.dirname(os.path.realpath(__file__))
    mp3s = [f for f in os.listdir(script_dir) if f.endswith('.mp3')]
    return os.path.join(script_dir, mp3s[0]) if mp3s else None


class MusicControllerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title('MaestroBOT')
        self.root.geometry("480x600")
        self.root.configure(bg='#121212')

        # Style configuration
        self.style = ttk.Style(self.root)
        self.style.theme_use('clam')

        # Font selection with fallback
        try:
            self.font_normal = font.Font(family='Consolas', size=10)
            self.font_bold = font.Font(family='Consolas', size=11, weight='bold')
            self.font_action = font.Font(family='Consolas', size=16, weight='bold')
            self.font_state = font.Font(family='Consolas', size=14, weight='bold')
        except tk.TclError:
            print("INFO: Consolas font not found, falling back to Segoe UI.")
            self.font_normal = font.Font(family='Segoe UI', size=10)
            self.font_bold = font.Font(family='Segoe UI', size=11, weight='bold')
            self.font_action = font.Font(family='Segoe UI', size=16, weight='bold')
            self.font_state = font.Font(family='Segoe UI', size=14, weight='bold')

        # Dark mode color palette
        BG_COLOR = '#121212'
        FRAME_COLOR = '#1E1E1E'
        TEXT_COLOR = '#E0E0E0'
        BTN_COLOR = '#333333'
        BTN_TEXT = '#FFFFFF'
        BTN_ACTIVE = '#4F4F4F'
        INSTR_BG = '#2A2A2A'
        PLAY_COLOR = '#66BB6A'
        PAUSE_COLOR = '#FFA726'
        STOP_COLOR = '#EF5350'

        # Apply styles to widgets
        self.style.configure('.', background=BG_COLOR, foreground=TEXT_COLOR)
        self.style.configure('TFrame', background=FRAME_COLOR)
        self.style.configure('TLabel', background=FRAME_COLOR, foreground=TEXT_COLOR, font=self.font_normal)
        self.style.configure('TButton', font=self.font_bold, padding=(10, 5),
                             background=BTN_COLOR, foreground=BTN_TEXT, borderwidth=0)
        self.style.map('TButton',
                       background=[('active', BTN_ACTIVE), ('pressed', BTN_ACTIVE)],
                       foreground=[('active', BTN_TEXT)])
        self.style.layout('TButton', [('Button.padding', {'sticky': 'nswe', 'children': [('Button.label', {'sticky': 'nswe'})]})])

        self.style.configure('Instructions.TLabel', background=INSTR_BG, foreground=TEXT_COLOR,
                             relief='solid', borderwidth=1, padding=(10, 10), font=self.font_normal)

        self.style.configure('Playing.TLabel', background=FRAME_COLOR, font=self.font_state, foreground=PLAY_COLOR)
        self.style.configure('Paused.TLabel', background=FRAME_COLOR, font=self.font_state, foreground=PAUSE_COLOR)
        self.style.configure('Stopped.TLabel', background=FRAME_COLOR, font=self.font_state, foreground=STOP_COLOR)

        self.style.configure('TNotebook', background=BG_COLOR, borderwidth=0)
        self.style.configure('TNotebook.Tab', background=BTN_COLOR, foreground=TEXT_COLOR, padding=[10, 5], font=self.font_bold, borderwidth=0)
        self.style.map('TNotebook.Tab',
                       background=[('selected', FRAME_COLOR), ('active', BTN_ACTIVE)],
                       foreground=[('selected', TEXT_COLOR)])

        # VLC player initialization
        self.instance = vlc.Instance('--audio-filter=scaletempo', '--quiet')
        self.player = self.instance.media_player_new()

        # State variables
        self.current_file = None
        self.is_playing = False
        self.is_paused = False
        self.camera_on = False
        self.volume = 60
        self.playback_rate = 1.0
        self.target_volume = 60
        self.target_rate = 1.0
        self.player.audio_set_volume(self.volume)

        # Fading state
        self.is_fading = False
        self.original_volume_on_fade = 60
        self._fade_after_id = None

        # Control mode state
        self.control_mode = "static"
        self.prev_slider_data = {'R_X': None, 'R_Y': None}
        self.SLIDER_DEADZONE_X = 15
        self.SLIDER_DEADZONE_Y = 10

        # Smoothing loop tracking
        self._smooth_update_id = None
        self._last_state_update = 0
        self.STATE_UPDATE_INTERVAL = 0.1  # Update state label every 100ms

        # Build GUI
        self._build_gui(FRAME_COLOR)

        # Threading components
        self.queue = queue.Queue()
        self.subproc = None
        self.reader_thread = None
        self.reading = False
        self._poll_after_id = None

        # Start camera and loops
        self.toggle_camera()
        self._poll_after_id = self.root.after(50, self._poll_queue)
        self._smooth_update_id = self.root.after(50, self._smooth_update_loop)
        self.root.protocol('WM_DELETE_WINDOW', self._on_close)

    def _build_gui(self, FRAME_COLOR):
        """Builds all GUI components."""
        # Tabbed interface
        self.notebook = ttk.Notebook(self.root, style='TNotebook')
        
        # Static gestures tab
        self.static_tab = ttk.Frame(self.notebook, style='TFrame', padding=(10, 10))
        self.notebook.add(self.static_tab, text='Static Gestures')
        static_instructions = (
            "Static Gestures (Hands work together):\n"
            "───────────────────────────────────────\n"
            " Playback:\n"
            "   • Both Hands Open   → Play/Resume\n"
            "   • Both Hands Closed → Fade to Pause\n"
            "\n"
            " Volume (Left Hand):\n"
            "   • One Finger   → 25%\n"
            "   • Two Fingers  → 50%\n"
            "   • Three Fingers→ 75%\n"
            "   • Four Fingers → 100%\n"
            "\n"
            " Speed (Right Hand):\n"
            "   • One Finger   → 0.50x\n"
            "   • Two Fingers  → 0.75x\n"
            "   • Three Fingers→ 1.00x\n"
            "   • Four Fingers → 1.50x"
        )
        self.label_static_instr = ttk.Label(self.static_tab, text=static_instructions, 
                                           justify=tk.LEFT, style='Instructions.TLabel')
        self.label_static_instr.pack(fill='x', expand=True)

        # Slider controls tab
        self.slider_tab = ttk.Frame(self.notebook, style='TFrame', padding=(10, 10))
        self.notebook.add(self.slider_tab, text='Slider Controls')
        slider_instructions = (
            "Slider Controls (Hands work independently):\n"
            "───────────────────────────────────────────\n"
            " Playback (Left Hand):\n"
            "   • Open Hand   → Play/Resume\n"
            "   • Closed Fist → Fade to Pause\n"
            "\n"
            " Sliders (Right Hand):\n"
            "   • Open Hand + Move L/R → Speed\n"
            "      (Right=Faster, Left=Slower)\n"
            "\n"
            "   • Closed Fist + Move U/D → Volume\n"
            "      (Up=Louder, Down=Quieter)"
        )
        self.label_slider_instr = ttk.Label(self.slider_tab, text=slider_instructions, 
                                           justify=tk.LEFT, style='Instructions.TLabel')
        self.label_slider_instr.pack(fill='x', expand=True)

        self.notebook.pack(fill='x', padx=10, pady=(10,0))
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        # Status display
        status_frame = ttk.Frame(self.root, padding=(10, 10), style='TFrame')
        status_frame.pack(fill='x')
        self.label_file = ttk.Label(status_frame, text='File: (none)', wraplength=450)
        self.label_file.pack(pady=(5, 10))
        self.label_action = ttk.Label(status_frame, text='Action: (waiting)', 
                                     font=self.font_action, style='TLabel', background=FRAME_COLOR)
        self.label_action.pack(pady=(10, 10))
        self.label_state = ttk.Label(status_frame, text='State: stopped | Volume: 60 | Rate: 1.00x', 
                                     style='Stopped.TLabel', background=FRAME_COLOR)
        self.label_state.pack(pady=(10, 10))

        # Manual control buttons
        btn_frame = ttk.Frame(self.root, padding=(10, 10), style='TFrame')
        btn_frame.pack(fill='x')
        btn_frame.columnconfigure((0, 1, 2, 3), weight=1)
        ttk.Button(btn_frame, text='Load MP3', command=self.load_file).grid(row=0, column=0, padx=5, sticky='ew')
        ttk.Button(btn_frame, text='Play', command=self.play_manual).grid(row=0, column=1, padx=5, sticky='ew')
        ttk.Button(btn_frame, text='Pause', command=self.pause_manual).grid(row=0, column=2, padx=5, sticky='ew')
        ttk.Button(btn_frame, text='Stop', command=self.stop_manual).grid(row=0, column=3, padx=5, sticky='ew')

        # Camera toggle
        cam_frame = ttk.Frame(self.root, padding=(10, 15), style='TFrame')
        cam_frame.pack(fill='x')
        self.btn_camera_toggle = ttk.Button(cam_frame, text='Turn Camera OFF', 
                                           command=self.toggle_camera, width=25)
        self.btn_camera_toggle.pack(pady=5)

        # Crash button
        bottom_frame = ttk.Frame(self.root, padding=(10, 10), style='TFrame')
        bottom_frame.pack(fill='x', side='bottom')
        self.style.configure('Crash.TButton', background='#a00', foreground='white', 
                           font=self.font_bold, borderwidth=0)
        self.style.map('Crash.TButton', background=[('active', '#c00'), ('pressed', '#c00')])
        self.style.layout('Crash.TButton', [('Button.padding', {'sticky': 'nswe', 
                         'children': [('Button.label', {'sticky': 'nswe'})]})])
        self.btn_crash = ttk.Button(bottom_frame, text='☠️ Crash', command=self.force_crash, 
                                    style='Crash.TButton')
        self.btn_crash.pack(side='right', padx=10, pady=10)

    def _on_tab_changed(self, event):
        """Handles tab switching between control modes."""
        current_tab_name = self.notebook.tab(self.notebook.select(), "text")
        self.control_mode = "static" if current_tab_name == "Static Gestures" else "slider"
        self.target_volume = self.volume
        self.target_rate = self.playback_rate
        self.prev_slider_data = {'R_X': None, 'R_Y': None}
        print(f"INFO: Control mode changed to: {self.control_mode}")

    def force_crash(self):
        """Forces application crash for testing error handling."""
        print("INFO: Stopping camera before crashing...")
        self.stop_hand_tracking_subprocess()
        print("INFO: Crashing as requested!")
        raise Exception("Forced crash.")

    def toggle_camera(self):
        """Toggles camera on/off for hand tracking."""
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
            else:
                self.camera_on = False
                self.btn_camera_toggle.config(text='Turn Camera ON')
                self.label_action.config(text='Action: Start Failed')

    def load_file(self):
        """Opens file dialog to load an MP3 file."""
        file = filedialog.askopenfilename(filetypes=[('MP3 files', '*.mp3'), ('All files', '*.*')])
        if not file:
            return
        self.current_file = file
        self.label_file.config(text=f'File: {os.path.basename(file)}')
        media = self.instance.media_new(str(file))
        self.player.set_media(media)
        self.play_manual()

    def play_manual(self):
        """Starts or resumes playback."""
        if self.is_fading:
            return
        
        try:
            player_state = self.player.get_state()
            if player_state == vlc.State.Playing:
                return
        except Exception:
            pass

        if not self.current_file:
            default = find_default_mp3()
            if default:
                self.current_file = str(default)
                media = self.instance.media_new(self.current_file)
                self.player.set_media(media)
                self.label_file.config(text=f'File: {os.path.basename(self.current_file)}')
            else:
                return

        success = self.player.play()
        if success == 0:
            self.is_playing = True
            self.is_paused = False
            self.volume = self.target_volume
            self.playback_rate = self.target_rate
            self.player.audio_set_volume(self.volume)
            self.player.set_rate(self.playback_rate)
            self._update_state_label()

    def pause_manual(self):
        """Pauses playback immediately."""
        if self.is_fading:
            return
        
        try:
            player_state = self.player.get_state()
            if player_state != vlc.State.Playing:
                return
        except Exception:
            pass

        self.player.pause()
        self.is_paused = True
        self.is_playing = False
        self._update_state_label()

    def stop_manual(self):
        """Stops playback and resets to initial state."""
        if self.is_fading:
            if self._fade_after_id:
                try:
                    self.root.after_cancel(self._fade_after_id)
                except Exception:
                    pass
            self._fade_after_id = None
            self.is_fading = False

        self.player.stop()
        self.is_playing = False
        self.is_paused = False
        self.volume = 60
        self.target_volume = 60
        self.playback_rate = 1.0
        self.target_rate = 1.0
        self.player.audio_set_volume(self.volume)
        self.player.set_rate(self.playback_rate)
        self._update_state_label()

    def fade_and_pause(self):
        """Gradually fades volume to zero then pauses."""
        try:
            player_state = self.player.get_state()
            if player_state != vlc.State.Playing or self.is_fading:
                return
        except Exception:
            return

        self.is_fading = True
        self.original_volume_on_fade = self.player.audio_get_volume()
        if self._fade_after_id:
            try:
                self.root.after_cancel(self._fade_after_id)
            except Exception:
                pass
        self._fade_after_id = self.root.after(50, self._fade_loop_pause)

    def _fade_loop_pause(self):
        """Recursive loop for fade effect."""
        self._fade_after_id = None
        
        try:
            root_exists = self.root.winfo_exists()
        except Exception:
            return

        if not self.is_fading or not root_exists:
            if not self.is_fading:
                try:
                    if self.player.is_playing():
                        self.player.audio_set_volume(self.original_volume_on_fade)
                except Exception:
                    pass
            return

        current_vol = self.player.audio_get_volume()
        step_down = max(1, self.original_volume_on_fade // 10 if self.original_volume_on_fade > 0 else 1)
        new_vol = max(0, current_vol - step_down)
        self.player.audio_set_volume(new_vol)

        if new_vol > 0:
            if self.is_fading and root_exists:
                self._fade_after_id = self.root.after(50, self._fade_loop_pause)
            elif not self.is_fading:
                try:
                    if self.player.is_playing():
                        self.player.audio_set_volume(self.original_volume_on_fade)
                except Exception:
                    pass
        else:
            self.player.pause()
            try:
                self.player.audio_set_volume(self.original_volume_on_fade)
            except Exception:
                pass
            self.is_paused = True
            self.is_playing = False
            self.is_fading = False
            self._update_state_label()

    def start_hand_tracking_subprocess(self):
        """Launches the hand tracking subprocess."""
        if self.subproc and self.subproc.poll() is None:
            return
        
        script_dir = os.path.dirname(os.path.realpath(__file__))
        script_path = os.path.join(script_dir, 'hand-tracker.py')
        
        if not os.path.exists(script_path):
            messagebox.showerror('Missing Script', f'hand-tracker.py not found at {script_path}')
            return
        
        cmd = [sys.executable, '-u', str(script_path)]
        try:
            print("INFO: Starting hand-tracking subprocess...")
            self.subproc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, bufsize=1, creationflags=subprocess.CREATE_NO_WINDOW,
                encoding='utf-8', errors='ignore'
            )
        except Exception as e:
            messagebox.showerror('Subprocess error', f'Failed to start hand-tracker.py: {e}')
            self.subproc = None
            return
        
        self.reading = True
        self.reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self.reader_thread.start()
        print("INFO: Hand tracking subprocess started.")

    def stop_hand_tracking_subprocess(self):
        """Stops the hand tracking subprocess cleanly."""
        print("INFO: Stopping hand tracking...")
        self.reading = False
        sub = self.subproc
        
        if sub and sub.poll() is None:
            try:
                sub.terminate()
                try:
                    sub.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    sub.kill()
            except Exception as e:
                print(f"ERROR: Error terminating subprocess: {e}")
                if sub and sub.poll() is None:
                    try:
                        sub.kill()
                    except Exception as kill_e:
                        print(f"ERROR: Error killing subprocess: {kill_e}")
        
        if hasattr(self, 'reader_thread') and self.reader_thread and self.reader_thread.is_alive():
            self.reader_thread.join(timeout=1)
        
        self.subproc = None
        self.reader_thread = None
        
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
            except queue.Empty:
                break
        
        print("INFO: Hand tracking stopped.")

    def _reader_loop(self):
        """Background thread that reads from subprocess stdout."""
        while self.reading:
            sub = self.subproc
            if not sub or not sub.stdout or sub.stdout.closed:
                break
            try:
                raw = sub.stdout.readline()
                if raw:
                    line = raw.strip()
                    if line:
                        self.queue.put(line)
                else:
                    break
            except ValueError:
                break
            except Exception as e:
                if self.reading:
                    print(f"ERROR: Exception in reader loop: {e}. Exiting.")
                break

    def _poll_queue(self):
        """Polls the message queue from hand tracking subprocess."""
        try:
            for _ in range(10):
                if self.queue.empty():
                    break
                line = self.queue.get_nowait()
                self._handle_line(line)
        except queue.Empty:
            pass
        except Exception as e:
            print(f"ERROR: Error processing queue: {e}")
        finally:
            try:
                root_exists = self.root.winfo_exists()
            except Exception:
                return
            
            if root_exists:
                self._poll_after_id = self.root.after(50, self._poll_queue)

    def _smooth_update_loop(self):
        """Smoothly interpolates volume and playback rate changes."""
        try:
            root_exists = self.root.winfo_exists()
        except Exception:
            return

        if not root_exists:
            return

        vol_changed = False
        rate_changed = False
        
        try:
            current_vlc_vol = self.player.audio_get_volume()
            current_vlc_rate = self.player.get_rate()

            # Smooth volume transitions
            if not self.is_fading and abs(self.target_volume - self.volume) > 1:
                step = 2 if self.target_volume > self.volume else -2
                self.volume = max(0, min(100, self.volume + step))
                if self.volume != current_vlc_vol:
                    self.player.audio_set_volume(self.volume)
                    vol_changed = True

            # Smooth rate transitions
            if abs(self.target_rate - self.playback_rate) > 0.02:
                step = 0.05 if self.target_rate > self.playback_rate else -0.05
                self.playback_rate = max(0.25, min(3.0, self.playback_rate + step))
                if abs(self.playback_rate - current_vlc_rate) > 0.01:
                    self.player.set_rate(self.playback_rate)
                    rate_changed = True

            # Throttled state label updates
            current_time = time.time()
            if vol_changed or rate_changed or (current_time - self._last_state_update) > self.STATE_UPDATE_INTERVAL:
                self._update_state_label()
                self._last_state_update = current_time

        except Exception as e:
            print(f"ERROR in smooth update loop accessing player: {e}")
        finally:
            if root_exists:
                try:
                    self._smooth_update_id = self.root.after(50, self._smooth_update_loop)
                except Exception:
                    pass

    def _parse_tracker_data(self, line: str) -> dict | None:
        """Parses hand tracking data from subprocess output."""
        if not line or '|' not in line or ':' not in line or "_Gesture:" not in line:
            return None
        
        data = {}
        try:
            parts = line.split('|')
            valid_keys = {"L_Gesture", "L_X", "L_Y", "R_Gesture", "R_X", "R_Y"}
            has_hand = False
            
            for part in parts:
                split_part = part.split(':', 1)
                if len(split_part) == 2:
                    key, val = split_part[0].strip(), split_part[1].strip()
                    if key in valid_keys:
                        if '_X' in key or '_Y' in key:
                            data[key] = int(val) if val != 'None' else None
                        else:
                            data[key] = val
                            has_hand |= (val != "No Hand")
            
            if not has_hand:
                return None
            
            data.setdefault("L_Gesture", "No Hand")
            data.setdefault("L_X", None)
            data.setdefault("L_Y", None)
            data.setdefault("R_Gesture", "No Hand")
            data.setdefault("R_X", None)
            data.setdefault("R_Y", None)
            
            return data
        except (ValueError, Exception):
            return None

    def _handle_line(self, line: str):
        """Processes a single line of hand tracking data."""
        if not self.camera_on or self.is_fading:
            return
        
        if line == "No hands detected.":
            self.label_action.config(text='Action: (no hands)')
            self.prev_slider_data = {'R_X': None, 'R_Y': None}
            return

        data = self._parse_tracker_data(line)
        if not data:
            return

        lg = data.get('L_Gesture', 'N/A')
        rg = data.get('R_Gesture', 'N/A')
        self.label_action.config(text=f"L: {lg} | R: {rg}")

        if self.control_mode == "static":
            self._handle_static_mode(data)
        else:
            self._handle_slider_mode(data)

    def _handle_static_mode(self, data: dict):
        """Handles gesture processing in static mode."""
        left_gesture = data.get('L_Gesture')
        right_gesture = data.get('R_Gesture')

        # Playback control
        if left_gesture == "Open Hand" and right_gesture == "Open Hand":
            if not self.is_playing or self.is_paused:
                self.play_manual()
        elif left_gesture == "Closed Fist" and right_gesture == "Closed Fist":
            if self.is_playing and not self.is_paused:
                self.fade_and_pause()

        # Volume control (left hand)
        volume_map = {
            "One Finger": 25,
            "Two Fingers": 50,
            "Three Fingers": 75,
            "Four Fingers": 100
        }
        
        if left_gesture in volume_map:
            target_vol = volume_map[left_gesture]
            if target_vol != self.target_volume:
                self.target_volume = target_vol

        # Speed control (right hand)
        rate_map = {
            "One Finger": 0.5,
            "Two Fingers": 0.75,
            "Three Fingers": 1.0,
            "Four Fingers": 1.5
        }
        
        if right_gesture in rate_map:
            target_rate = rate_map[right_gesture]
            if abs(target_rate - self.target_rate) > 0.01:
                self.target_rate = target_rate

    def _handle_slider_mode(self, data: dict):
        """Handles gesture processing in slider mode."""
        left_gesture = data.get('L_Gesture')
        right_gesture = data.get('R_Gesture')

        # Playback control (left hand)
        if left_gesture == "Open Hand":
            if not self.is_playing or self.is_paused:
                self.play_manual()
        elif left_gesture == "Closed Fist":
            if self.is_playing and not self.is_paused:
                self.fade_and_pause()

        # Slider controls (right hand)
        R_X = data.get('R_X')
        R_Y = data.get('R_Y')
        prev_x = self.prev_slider_data.get('R_X')
        prev_y = self.prev_slider_data.get('R_Y')

        # Speed control via horizontal movement
        if right_gesture == "Open Hand" and R_X is not None:
            if prev_x is not None:
                delta_x = R_X - prev_x
                if abs(delta_x) > self.SLIDER_DEADZONE_X:
                    new_actual_rate = self.playback_rate + (delta_x * 0.005)
                    new_actual_rate = max(0.25, min(3.0, new_actual_rate))
                    if abs(new_actual_rate - self.playback_rate) > 0.01:
                        self.playback_rate = new_actual_rate
                        self.target_rate = new_actual_rate
                        self.player.set_rate(self.playback_rate)
            
            self.prev_slider_data['R_X'] = R_X
            self.prev_slider_data['R_Y'] = None

        # Volume control via vertical movement
        elif right_gesture == "Closed Fist" and R_Y is not None:
            if prev_y is not None:
                delta_y = R_Y - prev_y
                if abs(delta_y) > self.SLIDER_DEADZONE_Y:
                    new_actual_vol = self.volume - (delta_y * 0.75)
                    new_actual_vol = int(max(0, min(100, new_actual_vol)))
                    if new_actual_vol != self.volume:
                        self.volume = new_actual_vol
                        self.target_volume = new_actual_vol
                        self.player.audio_set_volume(self.volume)
                        if not self.is_fading:
                            self.original_volume_on_fade = self.volume
            
            self.prev_slider_data['R_Y'] = R_Y
            self.prev_slider_data['R_X'] = None
        
        else:
            if self.prev_slider_data['R_X'] is not None or self.prev_slider_data['R_Y'] is not None:
                self.prev_slider_data['R_X'] = None
                self.prev_slider_data['R_Y'] = None

    def _update_state_label(self):
        """Updates the state display label with current playback info."""
        try:
            root_exists = self.root.winfo_exists()
        except Exception:
            return

        if not root_exists:
            return

        state_style = 'Stopped.TLabel'
        state = 'stopped'
        current_display_vol = self.volume
        current_display_rate = self.playback_rate

        try:
            player_state = self.player.get_state()
            if player_state == vlc.State.Playing:
                state = 'playing'
                state_style = 'Playing.TLabel'
            elif player_state == vlc.State.Paused:
                state = 'paused'
                state_style = 'Paused.TLabel'
            
            self.is_playing = (state == 'playing')
            self.is_paused = (state == 'paused')
        except Exception:
            if self.is_playing and not self.is_paused:
                state = 'playing'
                state_style = 'Playing.TLabel'
            elif self.is_paused:
                state = 'paused'
                state_style = 'Paused.TLabel'

        rate_str = f"{current_display_rate:.2f}x"
        vol_str = f"{current_display_vol}"
        self.label_state.config(
            text=f'State: {state} | Volume: {vol_str} | Rate: {rate_str}',
            style=state_style
        )

    def _on_close(self):
        """Cleanup handler for window close event."""
        print("INFO: Close window requested.")
        
        # Cancel all scheduled callbacks
        if self._fade_after_id:
            try:
                self.root.after_cancel(self._fade_after_id)
            except Exception:
                pass
        if self._poll_after_id:
            try:
                self.root.after_cancel(self._poll_after_id)
            except Exception:
                pass
        if self._smooth_update_id:
            try:
                self.root.after_cancel(self._smooth_update_id)
            except Exception:
                pass
        
        self._fade_after_id = None
        self._poll_after_id = None
        self._smooth_update_id = None

        # Stop hand tracking
        self.stop_hand_tracking_subprocess()
        
        # Stop VLC player
        try:
            print("INFO: Stopping VLC player on close.")
            if self.player:
                self.player.stop()
        except Exception as e:
            print(f"ERROR: Error stopping player: {e}")
        
        try:
            print("INFO: Releasing VLC instance.")
            if self.instance:
                self.instance.release()
        except Exception as e:
            print(f"ERROR: Error releasing instance: {e}")
        
        # Destroy window
        try:
            print("INFO: Destroying root window.")
            self.root.destroy()
        except tk.TclError:
            print("INFO: Root window already destroyed.")
        except Exception as e:
            print(f"ERROR: Error destroying root: {e}")


def main():
    root = tk.Tk()
    app = MusicControllerGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()