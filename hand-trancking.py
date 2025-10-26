import cv2
import mediapipe as mp
import math

# Used to convert protobuf message to a dictionary.
from google.protobuf.json_format import MessageToDict

# --- New Imports ---
# Import drawing utilities and styles
mpDrawing = mp.solutions.drawing_utils
mpDrawingStyles = mp.solutions.drawing_styles
# --------------------

# Initializing the Model
mpHands = mp.solutions.hands
hands = mpHands.Hands(
    static_image_mode=False,
    model_complexity=1,
    min_detection_confidence=0.75,
    min_tracking_confidence=0.75,
    max_num_hands=2)
    
# --- New variables for motion detection ---
# Dictionary to store the previous coordinates of each hand (Left/Right)
prev_hand_coords = {}
# A threshold (in pixels) to decide if movement is significant
MOTION_THRESHOLD = 10  
# ------------------------------------------

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

    # Dictionary to store the current frame's coordinates
    current_frame_hands = {}

    # If hands are present in image(frame)
    if results.multi_hand_landmarks:
        # Loop through all detected hands
        for hand_index, hand_landmarks in enumerate(results.multi_hand_landmarks):
            
            # --- 1. Get Hand Label (Left/Right) ---
            # Get the handedness information
            hand_info = results.multi_handedness[hand_index]
            label = MessageToDict(hand_info)['classification'][0]['label']

            # --- 2. Get Coordinates ---
            # We'll use the wrist (landmark 0) as the reference point
            # You can change this to any landmark (0-20)
            wrist_landmark = hand_landmarks.landmark[mpHands.HandLandmark.WRIST]
            
            # Convert normalized coordinates (0.0 - 1.0) to pixel coordinates
            cx = int(wrist_landmark.x * w)
            cy = int(wrist_landmark.y * h)

            # Store the current coordinates
            current_frame_hands[label] = (cx, cy)
            
            # --- 3. Draw Landmarks and Connections ---
            mpDrawing.draw_landmarks(
                img,
                hand_landmarks,
                mpHands.HAND_CONNECTIONS,
                mpDrawingStyles.get_default_hand_landmarks_style(),
                mpDrawingStyles.get_default_hand_connections_style())

            # --- 4. Output Coordinates onto the Image ---
            # Draw a circle at the wrist
            cv2.circle(img, (cx, cy), 7, (255, 0, 0), cv2.FILLED)
            # Put text (Label + Coordinates)
            coord_text = f"{label} Hand: ({cx}, {cy})"
            cv2.putText(img, coord_text, (cx - 70, cy - 20),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7, (255, 0, 0), 2)

        # --- 5. Detect Motion (after processing all hands) ---
        for label, (cx, cy) in current_frame_hands.items():
            # Check if this hand was also present in the previous frame
            if label in prev_hand_coords:
                # Get previous coordinates
                prev_cx, prev_cy = prev_hand_coords[label]
                
                # Calculate the distance moved
                distance = math.sqrt((cx - prev_cx)**2 + (cy - prev_cy)**2)

                # If the distance is greater than our threshold, it's motion!
                if distance > MOTION_THRESHOLD:
                    motion_str = ""
                    # Determine direction
                    dx = cx - prev_cx
                    dy = cy - prev_cy

                    if abs(dx) > abs(dy):  # More horizontal movement
                        motion_str = "Moving Right" if dx > 0 else "Moving Left"
                    else:  # More vertical movement
                        motion_str = "Moving Down" if dy > 0 else "Moving Up"

                    # Display the motion text
                    cv2.putText(img, motion_str, (cx - 70, cy - 50),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.7, (0, 0, 255), 2)
                    
                    # Output to console
                    print(f"{label} Hand: {motion_str} | Coords: ({cx}, {cy})")

        # Update the previous coordinates for the next frame
        prev_hand_coords = current_frame_hands

    else:
        # If no hands are detected, clear the previous coordinates
        prev_hand_coords = {}


    # Display Video and when 'q'
    # is entered, destroy the window
    cv2.imshow('Image', img)
    if cv2.waitKey(1) & 0xff == ord('q'):
        break

# Release the webcam and destroy all windows
cap.release()
cv2.destroyAllWindows()