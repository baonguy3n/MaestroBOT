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
GESTURE_COOLDOWN = 0.5 # Cooldown period in seconds (0.5s)

# --- NEW: Stillness & Position Settings ---
STILLNESS_THRESHOLD = 15  # Max pixels moved per frame to be "still". Increase if too sensitive.
CENTER_ROI_PCT = 0.05     # 0.05 = 5% border, captures inner 90% of screen. (CHANGED)
# ------------------------------------------

# Start capturing video from webcam
cap = cv2.VideoCapture(0)

# Track the last combined output line
last_output_line = ""
# -----------------------------------------------

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

    # --- NEW: Define the Center ROI boundaries ---
    roi_x_min = int(w * CENTER_ROI_PCT)
    roi_x_max = int(w * (1 - CENTER_ROI_PCT))
    roi_y_min = int(h * CENTER_ROI_PCT)
    roi_y_max = int(h * (1 - CENTER_ROI_PCT))
    # ---------------------------------------------

    # Convert BGR image to RGB image
    imgRGB = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # Process the RGB image
    results = hands.process(imgRGB)

    # Store current frame's data
    current_frame_data = {}
    detected_hands = {'Left': 'No Hand', 'Right': 'No Hand'}
    # ----------------------------------------

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
                mpDrawing.DrawingSpec(color=(245, 117, 66), thickness=2, circle_radius=4), 
                mpDrawing.DrawingSpec(color=(245, 66, 230), thickness=2, circle_radius=2))

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
            
            # --- Gesture Definitions (Modified) ---
            if total_fingers == 5: 
                gesture_str = "Open Hand"
            elif total_fingers == 1 and (fingers_up[1] == 1 or fingers_up[0] == 1): 
                gesture_str = "One Finger"
            elif total_fingers == 2 and fingers_up[1] == 1 and fingers_up[2] == 1:
                gesture_str = "Two Fingers"
            elif total_fingers == 3 and fingers_up[1] == 1 and fingers_up[2] == 1 and fingers_up[3] == 1:
                gesture_str = "Three Fingers"
            elif total_fingers == 4 and fingers_up[1] == 1 and fingers_up[2] == 1 and fingers_up[3] == 1 and fingers_up[4] == 1:
                gesture_str = "Four Fingers"
            elif total_fingers == 0:
                gesture_str = "Closed Fist"
            else: 
                gesture_str = "Other" # Catches undefined gestures

            # --- 4. Debounce Gesture (to prevent flickering) ---
            wrist_landmark = hand_landmarks.landmark[mpHands.HandLandmark.WRIST]
            cx = int(wrist_landmark.x * w)
            cy = int(wrist_landmark.y * h)
            
            last_display_gesture = prev_hand_data.get(label, {}).get('last_display_gesture', 'No Hand')
            last_change_time = prev_hand_data.get(label, {}).get('last_change_time', 0)
            
            display_gesture = gesture_str 
            if (current_time - last_change_time) < GESTURE_COOLDOWN:
                display_gesture = last_display_gesture
            elif gesture_str != last_display_gesture:
                display_gesture = gesture_str
                last_change_time = current_time 

            # --- 5. NEW: Check Stillness & Position ---
            prev_cx, prev_cy = prev_hand_data.get(label, {}).get('coords', (cx, cy))
            distance = math.sqrt((cx - prev_cx)**2 + (cy - prev_cy)**2)
            
            is_still = distance < STILLNESS_THRESHOLD
            is_in_center = (roi_x_min < cx < roi_x_max) and (roi_y_min < cy < roi_y_max)
            
            # --- 6. Store data for aggregation ---
            if is_in_center and is_still:
                detected_hands[label] = display_gesture # Store the debounced gesture
            else:
                detected_hands[label] = "Inactive" # Hand is moving or out of bounds

            # --- 7. Store all data for the next frame ---
            current_frame_data[label] = {
                'coords': (cx, cy), # Store current coords for next frame's distance check
                'gesture': gesture_str, 
                'last_display_gesture': display_gesture,
                'last_change_time': last_change_time
            }

            # --- 8. Draw the gesture text near the hand (runs every frame) ---
            # Determine text color based on active state
            if is_in_center and is_still:
                draw_color = (0, 255, 0) # Green
            else:
                draw_color = (0, 0, 255) # Red

            cv2.putText(img, f"{label}: {display_gesture}", (cx - 70, cy - 30), 
                        cv2.FONT_HERSHEY_DUPLEX, 0.7, draw_color, 2, cv2.LINE_AA)

        # --- END OF FOR LOOP ---

    # --- Aggregation and Printing (outside the 'for' loop) ---
    left_gesture = detected_hands['Left']
    right_gesture = detected_hands['Right']
    
    # Handle the "No Hand" vs "Inactive" distinction
    # If a hand is "Inactive", treat it as "No Hand" for the controller
    if left_gesture == "Inactive": left_gesture = "No Hand"
    if right_gesture == "Inactive": right_gesture = "No Hand"

    if left_gesture == "No Hand" and right_gesture == "No Hand":
        output_line = "No hands detected."
    else:
        output_line = f"Left: {left_gesture} | Right: {right_gesture}"

    # Only print if the state has changed
    if output_line != last_output_line:
        print(output_line, flush=True)
        last_output_line = output_line

    # Update the previous data for the next frame
    prev_hand_data = current_frame_data

    # --- Draw the ROI box --- (REMOVED)
    # cv2.rectangle(img, (roi_x_min, roi_y_min), (roi_x_max, roi_y_max), (0, 255, 0), 2) 

    # Display Video
    cv2.imshow('Hand Gesture Recognition', img)
    if cv2.waitKey(1) & 0xff == ord('q'):
        break

# Release the webcam and destroy all windows
cap.release()
cv2.destroyAllWindows()