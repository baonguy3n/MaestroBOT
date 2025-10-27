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

# Start capturing video from webcam
cap = cv2.VideoCapture(0)

# Track the last combined output line
last_output_line = ""
# -----------------------------------------------

print("DEBUG (hand-tracker): Starting capture loop...") # DEBUG

while True:
    current_time = time.time()
    success, img = cap.read()
    if not success: continue

    img = cv2.flip(img, 1)
    h, w, c = img.shape
    imgRGB = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    results = hands.process(imgRGB)

    current_frame_data = {}
    detected_hands = {'Left': None, 'Right': None} # Store full data dict or None

    if results.multi_hand_landmarks:
        for hand_index, hand_landmarks in enumerate(results.multi_hand_landmarks):
            hand_info = results.multi_handedness[hand_index]
            label = MessageToDict(hand_info)['classification'][0]['label']

            mpDrawing.draw_landmarks(
                img, hand_landmarks, mpHands.HAND_CONNECTIONS,
                mpDrawing.DrawingSpec(color=(245, 117, 66), thickness=2, circle_radius=4),
                mpDrawing.DrawingSpec(color=(245, 66, 230), thickness=2, circle_radius=2))

            fingers_up = []
            thumb_tip_x = hand_landmarks.landmark[tip_ids[0]].x
            thumb_ip_x = hand_landmarks.landmark[tip_ids[0] - 1].x
            if label == 'Right': fingers_up.append(1) if thumb_tip_x < thumb_ip_x else fingers_up.append(0)
            else: fingers_up.append(1) if thumb_tip_x > thumb_ip_x else fingers_up.append(0)

            for id in range(1, 5):
                tip_y = hand_landmarks.landmark[tip_ids[id]].y
                pip_y = hand_landmarks.landmark[tip_ids[id] - 2].y
                fingers_up.append(1) if tip_y < pip_y else fingers_up.append(0)

            total_fingers = fingers_up.count(1)
            gesture_str = "Other" # Default
            if total_fingers == 5: gesture_str = "Open Hand"
            elif total_fingers == 1 and (fingers_up[1] == 1 or fingers_up[0] == 1): gesture_str = "One Finger"
            elif total_fingers == 2 and fingers_up[1] == 1 and fingers_up[2] == 1: gesture_str = "Two Fingers"
            elif total_fingers == 3 and fingers_up[1] == 1 and fingers_up[2] == 1 and fingers_up[3] == 1: gesture_str = "Three Fingers"
            elif total_fingers == 4 and fingers_up[1] == 1 and fingers_up[2] == 1 and fingers_up[3] == 1 and fingers_up[4] == 1: gesture_str = "Four Fingers"
            elif total_fingers == 0: gesture_str = "Closed Fist"

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

            # Store data for the detected hand
            detected_hands[label] = {'gesture': display_gesture, 'x': cx, 'y': cy}

            # Store minimal data needed for next frame's debounce check
            current_frame_data[label] = {
                'last_display_gesture': display_gesture,
                'last_change_time': last_change_time
            }

            draw_color = (0, 255, 0)
            cv2.putText(img, f"{label}: {display_gesture}", (cx - 70, cy - 30),
                        cv2.FONT_HERSHEY_DUPLEX, 0.7, draw_color, 2, cv2.LINE_AA)

    # --- Aggregation and Printing (Corrected) ---
    output_parts = []
    left_data = detected_hands.get('Left')
    right_data = detected_hands.get('Right')
    has_any_hand = left_data or right_data

    # Append Left Hand Data (Gesture mandatory, Coords optional)
    if left_data:
        output_parts.append(f"L_Gesture:{left_data['gesture']}")
        output_parts.append(f"L_X:{left_data['x']}")
        output_parts.append(f"L_Y:{left_data['y']}")
    else:
        output_parts.append("L_Gesture:No Hand")
        # DO NOT append coordinates if no hand

    # Append Right Hand Data (Gesture mandatory, Coords optional)
    if right_data:
        output_parts.append(f"R_Gesture:{right_data['gesture']}")
        output_parts.append(f"R_X:{right_data['x']}")
        output_parts.append(f"R_Y:{right_data['y']}")
    else:
        output_parts.append("R_Gesture:No Hand")
        # DO NOT append coordinates if no hand

    output_line = "|".join(output_parts)

    # Determine if the current state is effectively "no hands"
    is_no_hands_now = not has_any_hand
    was_no_hands_before = "No hands detected." in last_output_line or not last_output_line # Check empty too

    # Only print if state changed significantly
    if output_line != last_output_line:
        if is_no_hands_now:
            if not was_no_hands_before: # Only print "No hands" once
                final_output = "No hands detected."
                print(f"DEBUG (hand-tracker): SENDING: {final_output}") # DEBUG
                print(final_output, flush=True)
                last_output_line = final_output
        else: # At least one hand is present
             print(f"DEBUG (hand-tracker): SENDING: {output_line}") # DEBUG
             print(output_line, flush=True)
             last_output_line = output_line

    prev_hand_data = current_frame_data # Update debounce history

    cv2.imshow('Hand Gesture Recognition', img)
    if cv2.waitKey(1) & 0xff == ord('q'):
        break

print("DEBUG (hand-tracker): Exiting capture loop.") # DEBUG
cap.release()
cv2.destroyAllWindows()
print("DEBUG (hand-tracker): Cleanup complete.") # DEBUG