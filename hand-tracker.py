import cv2
import mediapipe as mp
import sys
import time
from google.protobuf.json_format import MessageToDict

# MediaPipe setup
mpDrawing = mp.solutions.drawing_utils
mpDrawingStyles = mp.solutions.drawing_styles
mpHands = mp.solutions.hands

# Initialize hand detector
hands = mpHands.Hands(
    static_image_mode=False,
    model_complexity=1,
    min_detection_confidence=0.75,
    min_tracking_confidence=0.75,
    max_num_hands=2
)

# Landmark IDs for fingertips
TIP_IDS = [4, 8, 12, 16, 20]

# Gesture tracking state
prev_hand_data = {}
GESTURE_COOLDOWN = 0.5  # Seconds before gesture can change
last_output_line = ""

# Gesture classification lookup
GESTURE_PATTERNS = {
    5: "Open Hand",
    0: "Closed Fist",
    1: "One Finger",
    2: "Two Fingers",
    3: "Three Fingers",
    4: "Four Fingers"
}

def count_fingers(hand_landmarks, label):
    """Counts extended fingers on a hand."""
    fingers_up = []
    
    # Thumb detection (lateral movement)
    thumb_tip_x = hand_landmarks.landmark[TIP_IDS[0]].x
    thumb_ip_x = hand_landmarks.landmark[TIP_IDS[0] - 1].x
    
    if label == 'Right':
        fingers_up.append(1 if thumb_tip_x < thumb_ip_x else 0)
    else:
        fingers_up.append(1 if thumb_tip_x > thumb_ip_x else 0)
    
    # Other fingers (vertical extension)
    for tip_id in TIP_IDS[1:]:
        tip_y = hand_landmarks.landmark[tip_id].y
        pip_y = hand_landmarks.landmark[tip_id - 2].y
        fingers_up.append(1 if tip_y < pip_y else 0)
    
    return fingers_up

def classify_gesture(fingers_up):
    """Classifies gesture based on extended fingers."""
    total = sum(fingers_up)
    
    # Check for specific patterns first
    if total == 1 and (fingers_up[1] == 1 or fingers_up[0] == 1):
        return "One Finger"
    elif total == 2 and fingers_up[1] == 1 and fingers_up[2] == 1:
        return "Two Fingers"
    elif total == 3 and fingers_up[1] == 1 and fingers_up[2] == 1 and fingers_up[3] == 1:
        return "Three Fingers"
    elif total == 4 and all(fingers_up[1:]):
        return "Four Fingers"
    
    return GESTURE_PATTERNS.get(total, "Other")

def get_wrist_position(hand_landmarks, width, height):
    """Returns wrist position in pixel coordinates."""
    wrist = hand_landmarks.landmark[mpHands.HandLandmark.WRIST]
    return int(wrist.x * width), int(wrist.y * height)

def should_update_gesture(label, new_gesture, current_time):
    """Determines if gesture should update based on cooldown."""
    if label not in prev_hand_data:
        return True, new_gesture, current_time
    
    last_gesture = prev_hand_data[label].get('last_display_gesture', 'No Hand')
    last_change = prev_hand_data[label].get('last_change_time', 0)
    
    if (current_time - last_change) < GESTURE_COOLDOWN:
        return False, last_gesture, last_change
    elif new_gesture != last_gesture:
        return True, new_gesture, current_time
    
    return False, last_gesture, last_change

def format_output(detected_hands):
    """Formats hand data for output."""
    output_parts = []
    
    left_data = detected_hands.get('Left')
    right_data = detected_hands.get('Right')
    
    # Left hand data
    if left_data:
        output_parts.extend([
            f"L_Gesture:{left_data['gesture']}",
            f"L_X:{left_data['x']}",
            f"L_Y:{left_data['y']}"
        ])
    else:
        output_parts.append("L_Gesture:No Hand")
    
    # Right hand data
    if right_data:
        output_parts.extend([
            f"R_Gesture:{right_data['gesture']}",
            f"R_X:{right_data['x']}",
            f"R_Y:{right_data['y']}"
        ])
    else:
        output_parts.append("R_Gesture:No Hand")
    
    return "|".join(output_parts)

def main():
    global prev_hand_data, last_output_line
    
    cap = cv2.VideoCapture(0)
    
    while True:
        current_time = time.time()
        success, img = cap.read()
        
        if not success:
            continue
        
        # Flip and convert image
        img = cv2.flip(img, 1)
        height, width, _ = img.shape
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        # Process hands
        results = hands.process(img_rgb)
        
        current_frame_data = {}
        detected_hands = {'Left': None, 'Right': None}
        
        if results.multi_hand_landmarks:
            for hand_index, hand_landmarks in enumerate(results.multi_hand_landmarks):
                # Get hand label
                hand_info = results.multi_handedness[hand_index]
                label = MessageToDict(hand_info)['classification'][0]['label']
                
                # Draw landmarks
                mpDrawing.draw_landmarks(
                    img, hand_landmarks, mpHands.HAND_CONNECTIONS,
                    mpDrawing.DrawingSpec(color=(245, 117, 66), thickness=2, circle_radius=4),
                    mpDrawing.DrawingSpec(color=(245, 66, 230), thickness=2, circle_radius=2)
                )
                
                # Count fingers and classify gesture
                fingers_up = count_fingers(hand_landmarks, label)
                gesture_str = classify_gesture(fingers_up)
                
                # Get wrist position
                cx, cy = get_wrist_position(hand_landmarks, width, height)
                
                # Apply cooldown logic
                should_update, display_gesture, last_change = should_update_gesture(
                    label, gesture_str, current_time
                )
                
                # Store detected hand data
                detected_hands[label] = {'gesture': display_gesture, 'x': cx, 'y': cy}
                current_frame_data[label] = {
                    'last_display_gesture': display_gesture,
                    'last_change_time': last_change
                }
                
                # Draw text on image
                cv2.putText(
                    img, f"{label}: {display_gesture}",
                    (cx - 70, cy - 30),
                    cv2.FONT_HERSHEY_DUPLEX, 0.7, (0, 255, 0), 2, cv2.LINE_AA
                )
        
        # Update tracking data
        prev_hand_data = current_frame_data
        
        # Format and output
        has_any_hand = detected_hands['Left'] or detected_hands['Right']
        
        if has_any_hand:
            output_line = format_output(detected_hands)
            if output_line != last_output_line:
                sys.stdout.write(output_line + '\n')
                sys.stdout.flush()
                last_output_line = output_line
        else:
            if "No hands detected." not in last_output_line and last_output_line:
                sys.stdout.write("No hands detected.\n")
                sys.stdout.flush()
                last_output_line = "No hands detected."
        
        # Display window
        cv2.imshow('Hand Gesture Recognition', img)
        if cv2.waitKey(1) & 0xff == ord('q'):
            break
    
    cap.release()
    cv2.destroyAllWindows()

if __name__ == '__main__':
    main()