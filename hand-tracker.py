# py -m pip install opencv-python mediapipe
import cv2
import mediapipe as mp
import math
import time 

# Used to convert protobuf message to a dictionary.
from google.protobuf.json_format import MessageToDict

# --- Imports for drawing ---
mpDrawing = mp.solutions.drawing_utils
mpDrawingStyles = mp.solutions.drawing_styles
# --------------------------

# Initializing the Model
mpHands = mp.solutions.hands
hands = mpHands.Hands(
    static_image_mode=False,
    model_complexity=1,
    min_detection_confidence=0.75,
    min_tracking_confidence=0.75,
    max_num_hands=2)

# --- Landmark IDs for Finger Tips ---
tip_ids = [4, 8, 12, 16, 20] # Thumb, Index, Middle, Ring, Pinky
# -----------------------------------

# --- Variables for motion/gesture tracking ---
prev_hand_data = {} 
MOTION_THRESHOLD = 10  # Pixels
GESTURE_COOLDOWN = 0.5 # Cooldown period in seconds (0.5s)

# --- NEW: Auto-repeat settings ---
AUTO_REPEAT_DELAY = 0.4 # Time in seconds between repeats
AUTO_REPEAT_ACTIONS = [
    "Volume Up", 
    "Volume Down", 
    "Speed Up", 
    "Slow Down"
]
# ------------------------------------

# Start capturing video from webcam
cap = cv2.VideoCapture(0)

while True:
    # --- Get current time at the start of the frame ---
    current_time = time.time()

    # Read video frame by frame
    success, img = cap.read()
    if not success:
        print("Ignoring empty camera frame.")
        continue

    # Flip the image(frame)
    img = cv2.flip(img, 1)

    # Get image dimensions (Height, Width)
    h, w, c = img.shape

    # Convert BGR image to RGB image
    imgRGB = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # Process the RGB image
    results = hands.process(imgRGB)

    # To store the current frame's data for comparison
    current_frame_data = {}

    # If hands are present in image(frame)
    if results.multi_hand_landmarks:
        # Loop through all detected hands
        for hand_index, hand_landmarks in enumerate(results.multi_hand_landmarks):
            
            # --- 1. Get Hand Label (Left/Right) ---
            hand_info = results.multi_handedness[hand_index]
            label = MessageToDict(hand_info)['classification'][0]['label']

            # --- 2. Draw Landmarks (Slightly improved styling) ---
            mpDrawing.draw_landmarks(
                img,
                hand_landmarks,
                mpHands.HAND_CONNECTIONS,
                mpDrawing.DrawingSpec(color=(245, 117, 66), thickness=2, circle_radius=4), # Landmark color (orange-ish)
                mpDrawing.DrawingSpec(color=(245, 66, 230), thickness=2, circle_radius=2))  # Connection color (pink-ish)

            # --- 3. Gesture Recognition Logic ---
            fingers_up = [] 
            
            # --- Thumb Logic (Horizontal check) ---
            thumb_tip_x = hand_landmarks.landmark[tip_ids[0]].x
            thumb_ip_x = hand_landmarks.landmark[tip_ids[0] - 1].x # IP joint

            if label == 'Right':
                if thumb_tip_x < thumb_ip_x: fingers_up.append(1)
                else: fingers_up.append(0)
            else: # Left Hand
                if thumb_tip_x > thumb_ip_x: fingers_up.append(1)
                else: fingers_up.append(0)

            # --- Other 4 Fingers Logic (Vertical check) ---
            for id in range(1, 5): # Loop for Index, Middle, Ring, Pinky
                tip_y = hand_landmarks.landmark[tip_ids[id]].y
                pip_y = hand_landmarks.landmark[tip_ids[id] - 2].y
                if tip_y < pip_y: fingers_up.append(1)
                else: fingers_up.append(0)
            
            total_fingers = fingers_up.count(1)
            gesture_str = "" # The raw gesture string from this frame
            
            # --- Gesture Definitions ---
            if total_fingers == 5: 
                gesture_str = "Open Hand"
            elif total_fingers == 1 and fingers_up[1] == 1: 
                gesture_str = "Pointing Up"
            elif total_fingers == 1 and fingers_up[0] == 1: 
                gesture_str = "Thumbs Up"
            elif total_fingers == 2 and fingers_up[1] == 1 and fingers_up[2] == 1:
                gesture_str = "Two Fingers"
            elif total_fingers == 3 and fingers_up[1] == 1 and fingers_up[2] == 1 and fingers_up[3] == 1:
                gesture_str = "Three Fingers" # For Speed Up
            elif total_fingers == 4 and fingers_up[1] == 1 and fingers_up[2] == 1 and fingers_up[3] == 1 and fingers_up[4] == 1:
                gesture_str = "Four Fingers"  # For Slow Down
            elif total_fingers == 0:
                index_tip_y = hand_landmarks.landmark[8].y
                middle_tip_y = hand_landmarks.landmark[12].y
                index_pip_y = hand_landmarks.landmark[6].y
                index_mcp_y = hand_landmarks.landmark[5].y
                pointing_buffer = abs(index_pip_y - index_mcp_y) * 0.5 
                if (index_tip_y > index_pip_y) and (index_tip_y > (middle_tip_y + pointing_buffer)):
                    gesture_str = "Pointing Down"
                else:
                    gesture_str = "Closed Fist"
            else: 
                gesture_str = f"{total_fingers} Fingers"

            # --- 4. Motion, Cooldown, and NEW Auto-Repeat Logic ---
            wrist_landmark = hand_landmarks.landmark[mpHands.HandLandmark.WRIST]
            cx = int(wrist_landmark.x * w)
            cy = int(wrist_landmark.y * h)
            
            # --- Get data from previous frame ---
            prev_cx, prev_cy = prev_hand_data.get(label, {}).get('coords', (cx, cy))
            last_display_gesture = prev_hand_data.get(label, {}).get('last_display_gesture', 'No Hand')
            last_change_time = prev_hand_data.get(label, {}).get('last_change_time', 0)
            
            # --- NEW: Get last print time and action ---
            last_print_time = prev_hand_data.get(label, {}).get('last_print_time', 0)
            last_printed_action = prev_hand_data.get(label, {}).get('last_printed_action', 'No Action')

            # --- 1. Check for Motion ---
            distance = math.sqrt((cx - prev_cx)**2 + (cy - prev_cy)**2)
            if distance > MOTION_THRESHOLD:
                # Motion is detected, but we don't print it here anymore,
                # we just let the controller know if it's part of a new action.
                # You could add a print here if you want motion printed separately.
                # print(f"Hand: {label} | Motion: ...", flush=True)
                pass # For now, we only care about actions

            # --- 2. Debounce Gesture (to prevent flickering) ---
            display_gesture = gesture_str # Default to current frame's gesture
            if (current_time - last_change_time) < GESTURE_COOLDOWN:
                # Cooldown is active. Keep displaying the old gesture.
                display_gesture = last_display_gesture
            elif gesture_str != last_display_gesture:
                # Cooldown is over AND gesture has changed.
                display_gesture = gesture_str
                last_change_time = current_time # Reset timer
            
            # --- 3. Map DEBOUNCED gesture to an action string ---
            action_str = "No Action" # Default
            if display_gesture == "Open Hand":
                action_str = "Play/Resume"
            elif display_gesture == "Closed Fist":
                action_str = "Pause"
            elif display_gesture == "Pointing Up" or display_gesture == "Thumbs Up":
                action_str = "Volume Up"
            elif display_gesture == "Two Fingers":
                action_str = "Volume Down"
            elif display_gesture == "Three Fingers":
                action_str = "Speed Up"
            elif display_gesture == "Four Fingers":
                action_str = "Slow Down"
            
            # --- 4. Decide if we should print the action ---
            should_print = False
            if action_str != last_printed_action:
                # This is a NEW action (e.g., changing from "Pause" to "Play")
                # Or changing from "No Action" to "Volume Up"
                should_print = True
            elif action_str in AUTO_REPEAT_ACTIONS and (current_time - last_print_time) > AUTO_REPEAT_DELAY:
                # This is a HELD action (like "Volume Up") that is ready to repeat
                should_print = True

            # --- 5. Print to Terminal (if needed) ---
            if should_print and action_str != "No Action":
                # This print() is what sends the command to the other script
                print(f"Hand: {label} | Action: {action_str}", flush=True)
                last_print_time = current_time # Update the last print time
                last_printed_action = action_str # Update the last action

            # --- 6. Store all data for the next frame ---
            current_frame_data[label] = {
                'coords': (cx, cy),
                'gesture': gesture_str, # The raw gesture from this frame
                'last_display_gesture': display_gesture, # The gesture we're actually showing
                'last_change_time': last_change_time,
                'last_print_time': last_print_time, # Store the updated print time
                'last_printed_action': last_printed_action # Store the updated action
            }

            # --- 7. Draw the gesture text near the hand (runs every frame) ---
            cv2.putText(img, f"{label}: {display_gesture}", (cx - 70, cy - 30), 
                        cv2.FONT_HERSHEY_DUPLEX, 0.7, (255, 0, 0), 2, cv2.LINE_AA) # Blue text

        # Update the previous data for the next frame
        prev_hand_data = current_frame_data

    else:
        # If no hands are detected, check if we need to print "No hands"
        if prev_hand_data: # This means hands just disappeared
            print("No hands detected.", flush=True)
        prev_hand_data = {}

    # Display Video
    cv2.imshow('Hand Gesture Recognition', img) # Changed window title
    if cv2.waitKey(1) & 0xff == ord('q'):
        break

# Release the webcam and destroy all windows
cap.release()
cv2.destroyAllWindows()

