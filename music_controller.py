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


# OLD regex function is no longer needed


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
        self.is_playing = False
        self.is_paused = False
        self.camera_on = False # Will be toggled to True on start
        self.volume = 60
        self.playback_rate = 1.0
        self.player.audio_set_volume(self.volume)


        # --- Instructions (UPDATED) ---
        instructions = (
            "Two-Hand Gesture Controls:\n"
            "• Both Hands Open → Play/Resume\n"
            "• Both Hands Closed → Stop\n"
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
        self.play_manual()

    def play_manual(self):
        # Manually starts playback, finds a default MP3 if none is loaded
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
        self.playback_rate = 1.0 # Manual play resets rate
        self.player.set_rate(self.playback_rate)
        self.is_playing = True
        self.is_paused = False
        self._update_state_label()

    def pause_manual(self):
        # Manually pauses playback
        if self.is_playing and not self.is_paused:
            self.player.pause()
            self.is_paused = True
            self._update_state_label()

    def stop_manual(self):
        # Manually stops playback
        self.player.stop()
        self.playback_rate = 1.0
        self.is_playing = False
        self.is_paused = False
        self._update_state_label()

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
            # CREATE_NO_WINDOW hides the console on windows
            self.subproc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                                            text=True, bufsize=1, creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception as e:
            messagebox.showerror('Subprocess error', f'Failed to start hand-tracker.py: {e}')
            self.subproc = None
            return

        self.reading = True
        self.reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self.reader_thread.start()
        print("Hand tracking subprocess started.")

    def stop_hand_tracking_subprocess(self):
        # Stops the hand-tracking subprocess
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
        # thread target to read lines from stdout and put them in a queue
        while self.reading and self.subproc and self.subproc.stdout:
            try:
                raw = self.subproc.stdout.readline()
                if raw:
                    line = raw.strip()
                    if line:
                        self.queue.put(line)
                else:
                    break # Subprocess closed
            except Exception:
                break # Exit loop if process dies
        print("Reader loop exited.")

    def _poll_queue(self):
        # Periodically checks the queue for new lines
        try:
            while not self.queue.empty():
                line = self.queue.get_nowait()
                self._handle_line(line)
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self._poll_queue) # loop!

    def _handle_line(self, line: str):
        # --- NEW LOGIC for Two-Handed Gestures ---
        if not self.camera_on: # Don't process gestures if camera is off
            return
        
        # Handle "no hands" first (catches "No hands detected." and "Left: No Hand | Right: No Hand")
        if "No Hand" in line or "No hands detected" in line:
            self.label_action.config(text='Action: (no hands)')
            return

        # --- 1. Parse the new line format ---
        # Line format: "Left: {gesture} | Right: {gesture}"
        left_gesture = "No Hand"
        right_gesture = "No Hand"

        m_left = re.search(r'Left:\s*([^|]+)', line)
        m_right = re.search(r'Right:\s*(.+)', line) # Simpler regex for 'right'

        if m_left:
            left_gesture = m_left.group(1).strip()
        if m_right:
            right_gesture = m_right.group(1).strip()
        
        # Update the action label to show the full state
        self.label_action.config(text=f'L: {left_gesture} | R: {right_gesture}')

        # --- 2. Handle Play/Stop (Both hands) ---
        if left_gesture == "Open Hand" and right_gesture == "Open Hand":
            if (not self.is_playing or self.is_paused):
                # We need to make sure a file is loaded first!
                if not self.current_file:
                    default = find_default_mp3()
                    if default:
                        self.current_file = str(default)
                        media = self.instance.media_new(self.current_file)
                        self.player.set_media(media)
                        self.label_file.config(text=f'File: {os.path.basename(self.current_file)}')
                    else:
                        messagebox.showinfo('No MP3', 'No MP3 chosen and none found in project folder.')
                        return # Exit handle_line

                # Now we know a file is loaded, so just play.
                self.player.play() # This resumes if paused, or starts if stopped.
                self.is_playing = True
                self.is_paused = False
                print('Played/Resumed (Both Open)')

        elif left_gesture == "Closed Fist" and right_gesture == "Closed Fist":
            if self.is_playing:
                self.stop_manual() # Use existing stop function
                print('Stopped (Both Fists)')

        # --- 3. Handle Left Hand (Volume) ---
        # This is checked *independently* of play/stop
        new_vol = self.volume
        if left_gesture == "One Finger":
            new_vol = 25
        elif left_gesture == "Two Fingers":
            new_vol = 50
        elif left_gesture == "Three Fingers":
            new_vol = 75
        elif left_gesture == "Four Fingers":
            new_vol = 100
        
        if new_vol != self.volume:
            self.volume = new_vol
            self.player.audio_set_volume(self.volume)
            print(f'Volume set to -> {self.volume}')

        # --- 4. Handle Right Hand (Rate) ---
        # This is also checked *independently*
        new_rate = self.playback_rate
        if right_gesture == "One Finger":
            new_rate = 0.5
        elif right_gesture == "Two Fingers":
            new_rate = 0.75
        elif right_gesture == "Three Fingers":
            new_rate = 1.0
        elif right_gesture == "Four Fingers":
            new_rate = 1.5

        if new_rate != self.playback_rate:
            self.playback_rate = new_rate
            self.player.set_rate(self.playback_rate)
            print(f'Speed set to -> {self.playback_rate:.2f}x')
        
        # --- 5. Update GUI ---
        self._update_state_label()


    def _update_state_label(self):
        # Updates the state label with current status
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
        # Handles window close event
        self.stop_hand_tracking_subprocess()
        try:
            self.player.stop()
        except Exception:
            pass # don't care
        self.root.destroy()


def main():
    root = tk.Tk()
    app = MusicControllerGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()