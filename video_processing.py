import cv2
import numpy as np
import os
import easyocr

# Initialize EasyOCR reader
reader = easyocr.Reader(['en'])


def extract_speaker_name(frame, box):
    x, y, w, h = box
    print(x,y,w,h)
    name_height = 40
    roi_x_start = x + 5
    roi_x_end = x + int(w * 0.5)
    roi_y_start = y + h - name_height
    roi_y_end = y + h

    # Extract the name region
    roi = frame[roi_y_start:roi_y_end, roi_x_start:roi_x_end]

    # Convert to grayscale
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    gray = cv2.addWeighted(gray, 1.5, cv2.GaussianBlur(gray, (0, 0), 3), -0.5, 0)
    result = reader.readtext(gray)
    # cv2.imshow("Speaker Name ROI", gray)
    # while True:
    #     key = cv2.waitKey(1) & 0xFF
    #     if key == ord('q') or cv2.getWindowProperty("Speaker Name ROI", cv2.WND_PROP_VISIBLE) < 1:
    #         break
    for (bbox, text, prob) in result:
        return text
    return ""


def detect_speaker_container(frame, frame_count):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    detected_boxes = []
    for i, contour in enumerate(contours):
        x, y, w, h = cv2.boundingRect(contour)
        if w > 100 and h > 100:
            cropped_box = frame[y:y+h, x:x+w]
            if detect_speaker_icon(frame=cropped_box):
                detected_boxes.append((x, y, w, h))
                cropped_box = frame[y:y+h, x:x+w]
                filename = os.path.join(output_folder, f"frame_box_{frame_count}_{i}.png")
                cv2.imwrite(filename, cropped_box)
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
    return detected_boxes

def detect_speaker_icon(frame):
    h, w, _ = frame.shape
    box_size = 50
    x_start, y_start = w - box_size, 0
    icon_region = frame[y_start:y_start + box_size, x_start:x_start + box_size]
    hsv = cv2.cvtColor(icon_region, cv2.COLOR_BGR2HSV)
    lower_blue = np.array([90, 120, 50])
    upper_blue = np.array([150, 255, 255])
    mask = cv2.inRange(hsv, lower_blue, upper_blue)
    circles = cv2.HoughCircles(mask, cv2.HOUGH_GRADIENT, dp=1.2, minDist=10,
                               param1=50, param2=20, minRadius=5, maxRadius=25)
    cv2.rectangle(frame, (x_start, y_start), (x_start + box_size, y_start + box_size), (0, 255, 0), 2)
    if circles is not None:
        circles = np.uint16(np.around(circles))
        for circle in circles[0, :]:
            x, y, r = circle
            cv2.circle(icon_region, (x, y), r, (0, 255, 0), 2)
            print("Speaker Icon Detected (Circular Shape)!")
            return True

    return False


def extract_frames(video_path, frame_interval=0.5):
    cap = cv2.VideoCapture(video_path)
    frame_rate = cap.get(cv2.CAP_PROP_FPS)  
    interval = int(frame_rate * frame_interval)  # Capture every `frame_interval` seconds
    frames = []
    timestamps = []
    
    frame_count = 0
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        if frame_count % interval == 0:
            timestamps.append(cap.get(cv2.CAP_PROP_POS_MSEC) / 1000)  # Store timestamp in seconds
            frames.append(frame)
        frame_count += 1

    cap.release()
    return frames, timestamps









video_path = "/home/mudit/Desktop/test/recordingbot/meeting.mp4"
frames, timestamps = extract_frames(video_path)
speaker_log = []
output_folder = "speaker_boxes"
os.makedirs(output_folder, exist_ok=True)
count = 0
reader = easyocr.Reader(['en'])




for i, frame in enumerate(frames):
    speaker_boxes = detect_speaker_container(frame,i)
    for j, box in enumerate(speaker_boxes):
        speaker_name = extract_speaker_name(frame, box)
        if speaker_name:
            speaker_log.append({"timestamp": timestamps[i], "speaker": speaker_name})


with open("speaker_log.txt", "w") as file:
    for entry in speaker_log:
        file.write(f"At {entry['timestamp']}s, Speaker: {entry['speaker']}\n")











# image_path = "/home/mudit/Desktop/test/recordingbot/meetbot_env/meetbot_project/test2.png"
# frame = cv2.imread(image_path)

# # Detect the speaker name container (Assuming this function returns a list of bounding boxes)
# speaker_boxes = detect_speaker_container(frame, 0)
# print(speaker_boxes)


# Process each detected speaker box
# for box in speaker_boxes:
#     x, y, w, h = box
#     result = extract_speaker_name(frame, box)
#     print(result)
    # Draw bounding boxes and overlay extracted text
    # cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

    # # Overlay the extracted text
    # for (_, text, prob) in result:
    #     cv2.putText(frame, text, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
    #     print(f"Detected Text: {text} (Confidence: {prob:.2f})")

# Show the final image with text annotations
# cv2.imshow("Final Output", frame)

# Wait for user input to close the window
# while True:
#     key = cv2.waitKey(1) & 0xFF
#     if key == ord('q') or cv2.getWindowProperty("Final Output", cv2.WND_PROP_VISIBLE) < 1:
#         break

# cv2.destroyAllWindows()

























