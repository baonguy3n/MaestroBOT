# py -m pip install opencv-python mediapipe
import cv2
import mediapipe as mp
import math

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
# This dictionary will store the previous state (coords and gesture) of each hand
prev_hand_data = {} 
MOTION_THRESHOLD = 10  # Pixels
# ------------------------------------

# Start capturing video from webcam
cap = cv2.VideoCapture(0)

while True:
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

            # --- 2. Draw Landmarks ---
            mpDrawing.draw_landmarks(
                img,
                hand_landmarks,
                mpHands.HAND_CONNECTIONS,
                mpDrawingStyles.get_default_hand_landmarks_style(),
                mpDrawingStyles.get_default_hand_connections_style())

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
            elif total_fingers == 0: gesture_str = "Closed Fist"
            elif total_fingers == 2 and fingers_up[1] == 1 and fingers_up[2] == 1:
                gesture_str = "Peace Sign"
            elif total_fingers == 1 and fingers_up[1] == 1: gesture_str = "Pointing Up"
            elif total_fingers == 1 and fingers_up[0] == 1: gesture_str = "Thumbs Up"
            else: gesture_str = f"{total_fingers} Fingers"

            # --- 4. Motion Detection Logic ---
            wrist_landmark = hand_landmarks.landmark[mpHands.HandLandmark.WRIST]
            cx = int(wrist_landmark.x * w)
            cy = int(wrist_landmark.y * h)
            # Store current data
            current_frame_data[label] = {'coords': (cx, cy), 'gesture': gesture_str} 

            motion_str = ""
            has_changed = False # Flag to track if we should print

            if label in prev_hand_data:
                # --- Check for Motion ---
                prev_cx, prev_cy = prev_hand_data[label]['coords']
                distance = math.sqrt((cx - prev_cx)**2 + (cy - prev_cy)**2)
                if distance > MOTION_THRESHOLD:
                    has_changed = True # Motion detected
                    dx = cx - prev_cx
                    dy = cy - prev_cy
                    if abs(dx) > abs(dy):
                        motion_str = "Moving Right" if dx > 0 else "Moving Left"
                    else:
                        motion_str = "Moving Down" if dy > 0 else "Moving Up"
                
                # --- Check for Gesture Change ---
                last_gesture = prev_hand_data[label]['gesture']
                if gesture_str != last_gesture:
                    has_changed = True # Gesture changed

            else:
                has_changed = True # New hand detected

            # --- 5. Print to Terminal and Display on Image ---
            
            # --- *** NEW: Print to terminal ONLY on change *** ---
            if has_changed:
                terminal_output = f"Hand: {label} | Gesture: {gesture_str}"
                if motion_str:
                    terminal_output += f" | Motion: {motion_str}"
                print(terminal_output)
            # --- *** End of new code *** ---

            # Display on video window (as before)
            cv2.putText(img, f"{label}: {gesture_str}", (cx - 70, cy - 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)
            if motion_str: # Only display motion if it's happening
                cv2.putText(img, motion_str, (cx - 70, cy - 20),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

        # Update the previous data for the next frame
        prev_hand_data = current_frame_data

    else:
        # If no hands are detected, clear the previous data
        if prev_hand_data: # Only print "No hands" once
            print("No hands detected.")
        prev_hand_data = {}

    # Display Video
    cv2.imshow('Image', img)
    if cv2.waitKey(1) & 0xff == ord('q'):
        break

# Release the webcam and destroy all windows
cap.release()
cv2.destroyAllWindows()
