import concurrent
import cv2
import numpy as np
import os
import easyocr
import json

class MeetingProcessor:
    def __init__(self, video_path,output_json ,output_folder="speaker_boxes"):
        self.video_path = video_path
        self.output_folder = output_folder
        os.makedirs(output_folder, exist_ok=True)
        self.reader = easyocr.Reader(['en'], gpu = True)
        self.speaker_log = []
        self.output_json = output_json

    def get_unique_speaker_names(self, names):
        """
        Retains only the longest and most complete names from the list.
        """
        if not names:
            return []
        names = sorted(names, key=len, reverse=True)
        final_names = []
        for name in names:
            if not any(name in longer_name and name != longer_name for longer_name in final_names):
                final_names.append(name)

        return final_names

    def extract_speaker_name(self, frame, box):
        """ Detects speaker container box (To be overridden) """
        raise NotImplementedError("This method should be implemented by subclasses.")

    def detect_speaker_container(self, frame, frame_count):
        """ Detects speaker container box (To be overridden) """
        raise NotImplementedError("This method should be implemented by subclasses.")

    def extract_frames(self, frame_interval=1):
        """Extracts frames every `frame_interval` seconds based on timestamp."""
        print("extracting frames")
        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            print("Error: Unable to open video file")
            return [], []
        frames, timestamps = [], []
        video_duration = cap.get(cv2.CAP_PROP_FRAME_COUNT) / cap.get(cv2.CAP_PROP_FPS)
        print("video length: ", video_duration)
        current_time = 0
        while current_time < video_duration:
            cap.set(cv2.CAP_PROP_POS_MSEC, current_time * 1000)
            ret, frame = cap.read()
            if not ret:
                break
            frames.append(frame)
            timestamps.append(current_time)
            current_time += frame_interval
        cap.release()
        return frames, timestamps

    def process_video(self):
        """ Detects speaker container box (To be overridden) """
        raise NotImplementedError("This method should be implemented by subclasses.")

    def save_speaker_log(self):
        """ Saves speaker log to a JSON file with timestamped entries. """
        print("output json is ",self.output_json)
        formatted_log = []
        for entry in self.speaker_log:
            formatted_log.append({
                "timestamp": f"{entry['timestamp']}s",
                "speaker": entry['speaker']
            })

        with open(self.output_json, "w") as file:
            json.dump(formatted_log, file, indent=4)

        print(f"[INFO] Speaker log saved: {self.output_json}")

class GoogleMeetProcessor(MeetingProcessor):
    def find_speaker_container(self, frame, circle_bbox):
        """Finds the closest bounding box enclosing the given circle_bbox, ensuring the icon is in the top-right corner."""
        
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        target_bgr = np.uint8([[[216, 153, 111]]]) 
        target_hsv = cv2.cvtColor(target_bgr, cv2.COLOR_BGR2HSV)[0][0]
        lower_bound = np.array([target_hsv[0] - 5, 50, 50])  
        upper_bound = np.array([target_hsv[0] + 5, 255, 255])
        mask = cv2.inRange(hsv, lower_bound, upper_bound)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        x_c, y_c, w_c, h_c = circle_bbox
        best_box = None
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if x <= x_c and y <= y_c and (x + w) >= (x_c + w_c) and (y + h) >= (y_c + h_c):
                margin_x = (x + w) - (x_c + w_c)  
                margin_y = y_c - y  
                if margin_x < w * 0.4 and margin_y < h * 0.4:
                    best_box = (x, y, w, h)
                    break
        if best_box:
            x, y, w, h = best_box
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

        return frame, best_box

    def detect_speaker_icon(self, frame):
        """ Detects and draws speaker icon in Google Meet across the entire frame """
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        lower_blue = np.array([90, 120, 50])
        upper_blue = np.array([150, 255, 255])
        mask = cv2.inRange(hsv, lower_blue, upper_blue)
        
        circles = cv2.HoughCircles(mask, cv2.HOUGH_GRADIENT, dp=1.2, minDist=10,
                               param1=50, param2=20, minRadius=5, maxRadius=25)

        if circles is not None:
            circles = np.uint16(np.around(circles))
            bounding_boxes = []
            for circle in circles[0, :]:
                cx, cy, radius = circle
                x_min = max(0, cx - radius)
                y_min = max(0, cy - radius)
                width = height = 2 * radius

                # Draw detected circle for visualization
                # cv2.circle(frame, (cx, cy), radius, (0, 255, 0), 2)  
                # cv2.rectangle(frame, (x_min, y_min), (x_min + width, y_min + height), (255, 0, 0), 2)  # Draw bounding box
                
                bounding_boxes.append((x_min, y_min, width, height))

            return bounding_boxes
        # print(bounding_boxes)
        return []

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

    def process_video(self):
        """ Process video and extract speaker names in parallel """
        frames, timestamps = self.extract_frames()

        with concurrent.futures.ProcessPoolExecutor(max_workers=10) as executor:
            future_to_index = {
                executor.submit(self.process_frame, frame, timestamps[i], i): i
                for i, frame in enumerate(frames)
            }
            for future in concurrent.futures.as_completed(future_to_index):
                i = future_to_index[future]
                try:
                    result = future.result()
                    if result and result["speaker"]:
                        if self.speaker_log and self.speaker_log[-1]["timestamp"] == result["timestamp"]:
                            combined_speakers = self.speaker_log[-1]["speaker"] + result["speaker"]
                            self.speaker_log[-1]["speaker"] = self.get_unique_speaker_names(combined_speakers)
                        else:
                            self.speaker_log.append(result)
                except Exception as e:
                    print(f"Error processing frame {i}: {e}")
                    
        executor.shutdown(wait=True)

        self.save_speaker_log()

    def process_frame(self, frame, timestamp, frame_index):
        """ Process a single frame and extract speaker names """
        result = self.detect_speaker_icon(frame)
        if not result or len(result) == 0:
            return None
        speaker_names = []
        for circle_bbox in result:
            frame, container_box = self.find_speaker_container(frame, circle_bbox)
            if container_box:
                speaker_name = self.extract_speaker_name(frame, container_box)
                if speaker_name:
                    speaker_names.append(speaker_name)

        if speaker_names:
            return {"timestamp": timestamp, "speaker": self.get_unique_speaker_names(speaker_names)}
        return None


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
        
        avg_brightness = cv2.mean(roi_gray, mask[:, :, 0])[0] 
        variance = np.var(roi_gray[roi_gray > 0])
        
        return avg_brightness > 50 and variance > 500

    def detect_speaker_container(self, image, frame_count):
        """Detects name boxes with the specific background color when someone is speaking."""
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        target_bgr = np.uint8([[[169, 104, 98]]])
        target_hsv = cv2.cvtColor(target_bgr, cv2.COLOR_BGR2HSV)[0][0]
        lower_bound = np.array([target_hsv[0] - 5, 80, 100])
        upper_bound = np.array([target_hsv[0] + 5, 255, 255])
        mask = cv2.inRange(hsv, lower_bound, upper_bound)
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        boxes = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if w > 30 and w < 200 and h > 15 and h < 30:
                boxes.append((x, y, w, h))
                cv2.rectangle(image, (x, y), (x + w, y + h), (0, 255, 0), 2)
        return image, boxes

    def extract_speaker_name(self, frame, box):
        """Extracts text from the detected speaker name box."""
        x, y, w, h = box
        roi = frame[y:y+h, x:x+w]
        if roi is None or roi.size == 0:
            print("[ERROR] Empty region selected!")
            return ""
        if len(roi.shape) == 3 and roi.shape[2] == 3:
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        else:
            gray = roi 
        gray = cv2.addWeighted(gray, 1.5, cv2.GaussianBlur(gray, (3, 3), 0), -0.5, 0)
        result = self.reader.readtext(gray)

        for (_, text, _) in result:
            # print(text)
            return text 

        return ""

    def process_frame(self, frame, timestamp, frame_index):
        """ Process a single frame and extract speaker names """
        image, speaker_boxes = self.detect_speaker_container(frame, frame_index)

        if not speaker_boxes:
            return {"timestamp": timestamp, "speaker": []}
        speaker_names = []
        for box in speaker_boxes:
            speaker_name = self.extract_speaker_name(frame, box)
            if speaker_name:
                speaker_names.append(speaker_name)
        speaker_names = self.get_unique_speaker_names(speaker_names)
        
        return {"timestamp": timestamp, "speaker": speaker_names}

    def process_video(self):
        """ Process video frames concurrently using GPU """
        frames, timestamps = self.extract_frames()
        print(f"Total Frames: {len(frames)}")

        results = []
        with concurrent.futures.ProcessPoolExecutor(max_workers= 10) as executor:
            future_to_frame = {executor.submit(self.process_frame, frame, timestamps[i], i): i for i, frame in enumerate(frames)}

            for future in concurrent.futures.as_completed(future_to_frame):
                try:
                    result = future.result()
                    if result and result["speaker"]:  # Only add if speaker names were detected
                        if self.speaker_log and self.speaker_log[-1]["timestamp"] == result["timestamp"]:
                            combined_speakers = self.speaker_log[-1]["speaker"] + result["speaker"]
                            self.speaker_log[-1]["speaker"] = self.get_unique_speaker_names(combined_speakers)
                        else:
                            self.speaker_log.append(result)
                except Exception as e:
                    print(f"Error processing frame {future_to_frame[future]}: {e}")

        executor.shutdown(wait=True)
        self.save_speaker_log()


    # def process_video(self):
    #     """ Process video and extract speaker names """
    #     frames, timestamps = self.extract_frames()
    #     print(len(frames))
    #     for i, frame in enumerate(frames):
    #         result = self.detect_speaker_container(frame, i)

    #         # Ensure result is valid and has two expected values
    #         if not result or len(result) != 2:
    #             print(f"Warning: detect_speaker_container returned unexpected value at frame {i}")
    #             return  # Or continue if inside a loop

    #         image, speaker_boxes = result

    #         # Ensure speaker_boxes is a valid list
    #         if not speaker_boxes:  # If empty, skip processing
    #             return
    #         speaker_names = []

    #         # Extract speaker names from detected speaker boxes
    #         for box in speaker_boxes:
    #             speaker_name = self.extract_speaker_name(frame, box)
    #             if speaker_name:
    #                 speaker_names.append(speaker_name)

    #         if speaker_names:
    #             # Ensure only the most complete names are retained
    #             speaker_names = self.get_unique_speaker_names(speaker_names)

    #             if self.speaker_log and self.speaker_log[-1]["timestamp"] == timestamps[i]:
    #                 # Merge new speaker names with existing ones at the same timestamp
    #                 combined_speakers = self.speaker_log[-1]["speaker"] + speaker_names
    #                 self.speaker_log[-1]["speaker"] = self.get_unique_speaker_names(combined_speakers)
    #             else:
    #                 self.speaker_log.append({"timestamp": timestamps[i], "speaker": speaker_names})

    #     self.save_speaker_log()

class ZoomProcessor(MeetingProcessor):
    def detect_speaker_container(self, image, frame_count):
        """Detects boxes with a specific yellow border color (RGBA: 130,242,41,255)."""
        
        # Convert image to HSV
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        # Convert RGBA (130,242,41) to BGR -> then to HSV
        target_bgr = np.uint8([[[41, 242, 130]]])  # BGR equivalent
        target_hsv = cv2.cvtColor(target_bgr, cv2.COLOR_BGR2HSV)[0][0]

        # Define a precise range around the target HSV color
        lower_bound = np.array([target_hsv[0] - 10, 100, 100])  # Hue ±10 to allow variation
        upper_bound = np.array([target_hsv[0] + 10, 255, 255])  # Allow bright variations

        # Create mask
        mask = cv2.inRange(hsv, lower_bound, upper_bound)

        # Morphological operations to clean noise
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        # Find contours of detected boxes
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        boxes = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if w > 50 and h > 50:  # Filter small detections
                boxes.append((x, y, w, h))
                cv2.rectangle(image, (x, y), (x + w, y + h), (0, 0, 255), 2)  # Draw green box

        return image, boxes

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

    def process_video(self):
        """ Process video and extract speaker names in parallel """
        frames, timestamps = self.extract_frames()

        with concurrent.futures.ProcessPoolExecutor(max_workers=10) as executor:
            future_to_index = {
                executor.submit(self.process_frame, frame, timestamps[i], i): i
                for i, frame in enumerate(frames)
            }
            for future in concurrent.futures.as_completed(future_to_index):
                i = future_to_index[future]
                try:
                    result = future.result()
                    if result and result["speaker"]:
                        if self.speaker_log and self.speaker_log[-1]["timestamp"] == result["timestamp"]:
                            combined_speakers = self.speaker_log[-1]["speaker"] + result["speaker"]
                            self.speaker_log[-1]["speaker"] = self.get_unique_speaker_names(combined_speakers)
                        else:
                            self.speaker_log.append(result)
                except Exception as e:
                    print(f"Error processing frame {i}: {e}")
                    
        executor.shutdown(wait=True)

        self.save_speaker_log()

    def process_frame(self, frame, timestamp, frame_index):
        """ Process a single frame and extract speaker names """
        image, result = self.detect_speaker_container(frame, frame_index)
        if not result or len(result) == 0:
            return None
        speaker_names = []
        for bbox in result:
            speaker_name = self.extract_speaker_name(frame, bbox)
            if speaker_name:
                speaker_names.append(speaker_name)
        
        # print(speaker_names)
        if speaker_names:
            return {"timestamp": timestamp, "speaker": self.get_unique_speaker_names(speaker_names)}
        return None

# Example usage:
# google_meet_video_path = "/home/mudit/Desktop/test/recordingbot/meeting.mp4"
# processor = GoogleMeetProcessor(google_meet_video_path) 
# ms_teams_video_path = "/mnt/nvme_disk2/User_data/nb57077k/meetbot_project/output.mp4"
# processor = TeamsProcessor(ms_teams_video_path) 
# processor.process_video()


























