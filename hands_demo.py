import cv2
import mediapipe as mp
import csv
import os

# Initialize MediaPipe Hands
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
hands = mp_hands.Hands(static_image_mode=False,
                       max_num_hands=2,
                       min_detection_confidence=0.5,
                       min_tracking_confidence=0.5)

# Create/append to CSV file
csv_path = "hand_landmarks.csv"
file_exists = os.path.isfile(csv_path)

with open(csv_path, mode='a', newline='') as f:
    csv_writer = csv.writer(f)
    
    # Write header if file is new
    if not file_exists:
        header = ["frame_id", "hand_label"]
        for i in range(21):
            header += [f"x{i}", f"y{i}", f"z{i}"]
        csv_writer.writerow(header)

    cap = cv2.VideoCapture(0)
    frame_id = 0
    recording = False  # moved outside loop

    while cap.isOpened():
        success, frame = cap.read()
        if not success:
            break

        frame = cv2.flip(frame, 1)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands.process(rgb_frame)

        # Handle key presses
        key = cv2.waitKey(5) & 0xFF
        if key == ord('r'):
            recording = not recording
            print("Recording:", recording)
        elif key == 27:  # ESC to quit
            break

        # Always draw landmarks if detected
        if results.multi_hand_landmarks:
            for hand_landmarks, handedness in zip(results.multi_hand_landmarks, results.multi_handedness):
                # Draw landmarks on frame (always)
                mp_drawing.draw_landmarks(
                    frame,
                    hand_landmarks,
                    mp_hands.HAND_CONNECTIONS,
                    mp_drawing.DrawingSpec(color=(0,255,0), thickness=2, circle_radius=3),
                    mp_drawing.DrawingSpec(color=(0,0,255), thickness=2)
                )

                # Save to CSV only if recording
                if recording:
                    data = [frame_id, handedness.classification[0].label]
                    for lm in hand_landmarks.landmark:
                        data.extend([lm.x, lm.y, lm.z])
                    csv_writer.writerow(data)

        frame_id += 1
        cv2.imshow("MediaPipe Hands", frame)

    cap.release()
    cv2.destroyAllWindows()
