# py -m pip install opencv-python mediapipe
import cv2
import mediapipe as mp
import math
# import numpy as np # --- REMOVED: No longer needed for gradient
import time # --- NEW: Import time module for cooldown

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
tip_ids = [4, 8, 12, 16, 20]
# -----------------------------------

# --- Variables for motion/gesture tracking ---
prev_hand_data = {} 
MOTION_THRESHOLD = 10  # Pixels
GESTURE_COOLDOWN = 0.5 # --- NEW: Cooldown period in seconds (0.5s)
# ------------------------------------

# Start capturing video from webcam
cap = cv2.VideoCapture(0)

while True:
    # --- NEW: Get current time at the start of the frame ---
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

    # --- REMOVED: Gradient overlay block ---
    # (The code for creating the overlay, colors, and cv2.addWeighted has been removed)
    # --- END REMOVED ---

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
            thumb_tip_x = hand_landmarks.landmark[tip_ids[0]].x
            thumb_ip_x = hand_landmarks.landmark[tip_ids[0] - 1].x

            if label == 'Right':
                if thumb_tip_x < thumb_ip_x: fingers_up.append(1)
                else: fingers_up.append(0)
            else: # Left Hand
                if thumb_tip_x > thumb_ip_x: fingers_up.append(1)
                else: fingers_up.append(0)

            for id in range(1, 5):
                tip_y = hand_landmarks.landmark[tip_ids[id]].y
                pip_y = hand_landmarks.landmark[tip_ids[id] - 2].y
                if tip_y < pip_y: fingers_up.append(1)
                else: fingers_up.append(0)
            
            total_fingers = fingers_up.count(1)
            gesture_str = ""
            if total_fingers == 5: gesture_str = "Open Hand"
            elif total_fingers == 1 and fingers_up[1] == 1: 
                gesture_str = "Pointing Up"
            elif total_fingers == 1 and fingers_up[0] == 1: 
                gesture_str = "Thumbs Up"
            elif total_fingers == 2 and fingers_up[1] == 1 and fingers_up[2] == 1:
                gesture_str = "Two Fingers"
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
            else: gesture_str = f"{total_fingers} Fingers"

            # --- 4. Motion Detection Logic ---
            wrist_landmark = hand_landmarks.landmark[mpHands.HandLandmark.WRIST]
            cx = int(wrist_landmark.x * w)
            cy = int(wrist_landmark.y * h)
            
            # --- MODIFIED: Logic for debouncing/cooldown ---
            motion_str = ""
            has_changed = False 
            display_gesture = gesture_str # Default to current frame's gesture

            # Default change time if hand is new
            last_change_time = current_time

            if label in prev_hand_data:
                # Get previous data
                prev_cx, prev_cy = prev_hand_data[label]['coords']
                last_raw_gesture = prev_hand_data[label]['gesture']
                last_display_gesture = prev_hand_data[label]['last_display_gesture']
                last_change_time = prev_hand_data[label]['last_change_time']

                # 1. Check for Motion
                distance = math.sqrt((cx - prev_cx)**2 + (cy - prev_cy)**2)
                if distance > MOTION_THRESHOLD:
                    has_changed = True # Motion triggers a print
                    dx = cx - prev_cx
                    dy = cy - prev_cy
                    if abs(dx) > abs(dy):
                        motion_str = "Moving Right" if dx > 0 else "Moving Left"
                    else:
                        motion_str = "Moving Down" if dy > 0 else "Moving Up"
                
                # 2. Check for Gesture Change (with Cooldown)
                if (current_time - last_change_time) < GESTURE_COOLDOWN:
                    # Cooldown is active. Keep displaying the old gesture.
                    display_gesture = last_display_gesture
                elif gesture_str != last_display_gesture:
                    # Cooldown is over AND gesture has changed.
                    display_gesture = gesture_str
                    last_change_time = current_time # Reset timer
                    has_changed = True # Gesture change triggers a print
                else:
                    # Cooldown is over and gesture is the same.
                    display_gesture = last_display_gesture

                # If only motion happened (no gesture change), we still want to flag it
                if motion_str and not has_changed:
                    has_changed = True

            else:
                # This is a new hand, so it definitely "changed"
                has_changed = True 

            # Store all data for the next frame
            current_frame_data[label] = {
                'coords': (cx, cy),
                'gesture': gesture_str, # The raw gesture from this frame
                'last_display_gesture': display_gesture, # The gesture we're actually showing
                'last_change_time': last_change_time
            }
            # --- END MODIFIED LOGIC ---

            # --- 5. Print to Terminal and Display on Image ---
            if has_changed:
                terminal_output = f"Hand: {label} | Gesture: {display_gesture}" # Use display_gesture
                if motion_str:
                    terminal_output += f" | Motion: {motion_str}"
                print(terminal_output)

            # --- MODIFIED: Display on video window (simplified) ---
            # Position text relative to the hand's wrist
            
            # Draw the gesture text
            cv2.putText(img, f"{label}: {display_gesture}", (cx - 70, cy - 30), # Use display_gesture
                        cv2.FONT_HERSHEY_DUPLEX, 0.7, (0, 0, 0), 2, cv2.LINE_AA) # Blue text

            # --- REMOVED: The cv2.putText call for motion_str (yellow text) ---

        # Update the previous data for the next frame
        prev_hand_data = current_frame_data

    else:
        # If no hands are detected, clear the previous data
        if prev_hand_data: 
            print("No hands detected.")
            # --- REMOVED: The cv2.putText for "No hands detected" ---
        prev_hand_data = {}

    # Display Video
    cv2.imshow('Hand Gesture Recognition', img) # Changed window title
    if cv2.waitKey(1) & 0xff == ord('q'):
        break

# Release the webcam and destroy all windows
cap.release()
cv2.destroyAllWindows()

