import cv2
import numpy as np
import os
import easyocr
import json



class MeetingProcessor:
    def __init__(self, video_path, output_folder="speaker_boxes"):
        self.video_path = video_path
        self.output_folder = output_folder
        os.makedirs(output_folder, exist_ok=True)
        self.reader = easyocr.Reader(['en'])
        self.speaker_log = []
        print(self.video_path)

    def extract_speaker_name(self, frame, box):
        """ Detects speaker container box (To be overridden) """
        raise NotImplementedError("This method should be implemented by subclasses.")

    def detect_speaker_container(self, frame, frame_count):
        """ Detects speaker container box (To be overridden) """
        raise NotImplementedError("This method should be implemented by subclasses.")

    def extract_frames(self, frame_interval=0.03):
        """ Extracts frames from video """
        cap = cv2.VideoCapture(self.video_path)
        frame_rate = cap.get(cv2.CAP_PROP_FPS)
        
        if frame_rate <= 0:
            print("Error: Could not determine FPS")
            return [], []

        interval = int(frame_rate * frame_interval)
        frames, timestamps = [], []

        frame_count = 0
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                print(f"Stopped reading at frame {frame_count}, timestamp: {cap.get(cv2.CAP_PROP_POS_MSEC) / 1000}s")
                break

            if frame_count % interval == 0:
                timestamp = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
                # print(f"Frame {frame_count}, Timestamp: {timestamp}s")  # Debug log
                timestamps.append(timestamp)
                frames.append(frame)

            frame_count += 1

        cap.release()
        return frames, timestamps

    def process_video(self):
        """ Process video and extract speaker names """
        frames, timestamps = self.extract_frames()
        for i, frame in enumerate(frames):
            image, speaker_boxes = self.detect_speaker_container(frame, i)
            if len(speaker_boxes)==2:
                print(timestamps[i])
            speaker_names = []
            for box in speaker_boxes:
                speaker_name = self.extract_speaker_name(frame, box)
                if speaker_name:
                    speaker_names.append(speaker_name)
            if speaker_names:
                if self.speaker_log and self.speaker_log[-1]["timestamp"] == timestamps[i]:
                    self.speaker_log[-1]["speaker"].extend(speaker_names)
                else:
                    self.speaker_log.append({"timestamp": timestamps[i], "speaker": speaker_names})  # New entry

        self.save_speaker_log()

    def save_speaker_log(self):
        """ Saves speaker log to a JSON file with timestamped entries. """
        log_file = "speaker_log.json"

        # Convert timestamps to human-readable format
        formatted_log = []
        for entry in self.speaker_log:
            formatted_log.append({
                "timestamp": f"{entry['timestamp']}s",
                "speaker": entry['speaker']
            })

        with open(log_file, "w") as file:
            json.dump(formatted_log, file, indent=4)

        print(f"[INFO] Speaker log saved: {log_file}")


class GoogleMeetProcessor(MeetingProcessor):
    def detect_speaker_container(self, frame, frame_count):
        """ Detects speaker box in Google Meet """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        detected_boxes = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if w > 100 and h > 100 and self.detect_speaker_icon(frame[y:y+h, x:x+w]):
                detected_boxes.append((x, y, w, h))
                cv2.imwrite(os.path.join(self.output_folder, f"frame_box_{frame_count}.png"), frame[y:y+h, x:x+w])
        return detected_boxes

    def detect_speaker_icon(self, frame):
        """ Detects speaker icon in Google Meet """
        h, w, _ = frame.shape
        box_size = 50
        icon_region = frame[0:box_size, w-box_size:w]

        hsv = cv2.cvtColor(icon_region, cv2.COLOR_BGR2HSV)
        lower_blue = np.array([90, 120, 50])
        upper_blue = np.array([150, 255, 255])
        mask = cv2.inRange(hsv, lower_blue, upper_blue)

        circles = cv2.HoughCircles(mask, cv2.HOUGH_GRADIENT, dp=1.2, minDist=10,
                                   param1=50, param2=20, minRadius=5, maxRadius=25)
        return circles is not None

    def extract_speaker_name(self, frame, box):
        """ Extracts speaker name using OCR """
        x, y, w, h = box
        name_height = 40
        roi_x_start = x + 5
        roi_x_end = x + int(w * 0.5)
        roi_y_start = y + h - name_height
        roi_y_end = y + h

        roi = frame[roi_y_start:roi_y_end, roi_x_start:roi_x_end]

        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        gray = cv2.addWeighted(gray, 1.5, cv2.GaussianBlur(gray, (0, 0), 3), -0.5, 0)

        result = self.reader.readtext(gray)
        for (_, text, _) in result:
            return text
        return ""

class TeamsProcessor(MeetingProcessor):

    def preprocess_image(self):
        """Convert image to grayscale and apply blur."""
        gray = cv2.cvtColor(self.image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        return gray, blurred

    def detect_circles(self, blurred):
        """Detect circular profile containers using HoughCircles."""
        circles = cv2.HoughCircles(blurred, cv2.HOUGH_GRADIENT, dp=1.2, minDist=50,
                                   param1=50, param2=30, minRadius=40, maxRadius=100)
        return np.uint16(np.around(circles)) if circles is not None else None

    def is_valid_profile_circle(self, x, y, r):
        """Check if the circle contains a real profile picture."""
        mask = np.zeros_like(self.image, dtype=np.uint8)
        cv2.circle(mask, (x, y), r - 5, (255, 255, 255), -1)
        roi = cv2.bitwise_and(self.image, mask)
        roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        
        avg_brightness = cv2.mean(roi_gray, mask[:, :, 0])[0]  # Mean brightness
        variance = np.var(roi_gray[roi_gray > 0])  # Compute variance
        
        return avg_brightness > 50 and variance > 500  # Adjust variance threshold

    def detect_speaker_container(self, image, frame_count):
        """Detects name boxes with the specific background color when someone is speaking."""
        # Convert image to HSV
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        # Convert HEX #6268A9 to BGR -> then to HSV
        target_bgr = np.uint8([[[169, 104, 98]]])  # BGR of #6268A9
        target_hsv = cv2.cvtColor(target_bgr, cv2.COLOR_BGR2HSV)[0][0]

        # Define a precise range around the target HSV color
        lower_bound = np.array([target_hsv[0] - 5, 80, 100])  # Hue ±5, avoid desaturated colors
        upper_bound = np.array([target_hsv[0] + 5, 255, 255])  # Allow bright variations

        # Create mask
        mask = cv2.inRange(hsv, lower_bound, upper_bound)

        # Morphological operations to clean noise
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        # Find contours of detected text
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)


        boxes = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if w > 30 and w < 200 and h > 15 and h < 30:  # Filter small detections
                boxes.append((x, y, w, h))
                cv2.rectangle(image, (x, y), (x + w, y + h), (0, 255, 0), 2)  # Draw green box

        return image, boxes

    def extract_speaker_name(self, frame, box):
        """Extracts text from the detected speaker name box."""
        x, y, w, h = box  # Ensure box is properly unpacked
        roi = frame[y:y+h, x:x+w]

        if roi is None or roi.size == 0:
            print("[ERROR] Empty region selected!")
            return ""

        # Ensure it has 3 channels before converting to grayscale
        if len(roi.shape) == 3 and roi.shape[2] == 3:
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        else:
            gray = roi  # Already grayscale

        # Enhance contrast for better OCR
        gray = cv2.addWeighted(gray, 1.5, cv2.GaussianBlur(gray, (3, 3), 0), -0.5, 0)

        # Run OCR
        result = self.reader.readtext(gray)

        for (_, text, _) in result:
            return text  # Return first detected text

        return ""  # No text found

class ZoomProcessor(MeetingProcessor):
    def detect_speaker_container(self, frame, frame_count):
        """ Detects speaker box in Zoom """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        detected_boxes = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if w > 90 and h > 90 and self.detect_speaker_icon(frame[y:y+h, x:x+w]):
                detected_boxes.append((x, y, w, h))
                cv2.imwrite(os.path.join(self.output_folder, f"zoom_box_{frame_count}.png"), frame[y:y+h, x:x+w])
        return detected_boxes

    def detect_speaker_icon(self, frame):
        """ Detects speaker icon in Zoom """
        h, w, _ = frame.shape
        box_size = 40
        icon_region = frame[0:box_size, w-box_size:w]

        hsv = cv2.cvtColor(icon_region, cv2.COLOR_BGR2HSV)
        lower_green = np.array([50, 100, 50])
        upper_green = np.array([90, 255, 255])
        mask = cv2.inRange(hsv, lower_green, upper_green)

        return np.count_nonzero(mask) > 300  # Detects green speaker highlight


# Example usage:
# google_meet_video_path = "/home/mudit/Desktop/test/recordingbot/meeting.mp4"
# processor = GoogleMeetProcessor(google_meet_video_path) 
ms_teams_video_path = "/home/mudit/Desktop/test/recordingbot/teams_sample_recording.webm"
processor = TeamsProcessor(ms_teams_video_path) 
processor.process_video()


























