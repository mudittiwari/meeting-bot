import cv2
import numpy as np
import easyocr

class MeetingProcessor:
    def __init__(self, image_path):
        self.image = cv2.imread(image_path)
        self.reader = easyocr.Reader(['en'])

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

    def detect_speaker_boxes(self, image):
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

    def detect_rectangles(self, gray):
        """Detect rectangular containers (camera on)."""
        edges = cv2.Canny(gray, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        rectangles = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if w > 100 and h > 100:  # Filter out small detections
                rectangles.append((x, y, w, h))
                cv2.rectangle(self.image, (x, y), (x + w, y + h), (0, 255, 0), 2)  # Draw green rectangles
        return rectangles

    def extract_text(self, roi):
        """Use OCR to extract text from a region if it exists."""
        if roi is None or roi.size == 0:
            return ""

        gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        result = self.reader.readtext(gray_roi)
        return result if result else ""

    def process_image(self):
        gray, blurred = self.preprocess_image()
        # circles = self.detect_circles(blurred)
        rectangles = self.detect_rectangles(gray)

        detected_participants = []
        valid_circles = []  # Store only valid circles

        # if circles is not None:
        #     for circle in circles[0, :]:
        #         x, y, r = circle

        #         # Define circle boundary
        #         # circle_left = x - r
        #         # circle_right = x + r
        #         # circle_top = y - r
        #         circle_bottom = y + r

        #         # Extract bottom-left region for text (approximate name position)
        #         text_x1 = max(0, int(x) - (2 * int(r)))
        #         text_y1 = max(0, int(y) + int(r) - 10)
        #         text_x2 = max(0, int(x) - int(r) + 150)
        #         text_y2 = max(0, int(y) + int(r) + 20)

        #         # Ensure text ROI is within bounds
        #         if text_y1 < 0 or text_y2 > self.image.shape[0]:
        #             continue  

        #         text_roi = self.image[text_y1:text_y2, text_x1:text_x2]
        #         speaker_name = self.extract_text(text_roi)

        #         text_bbox_list = []  # Store detected text bounding boxes
        #         for (bbox, text, prob) in speaker_name:
        #             if prob > 0.5:  # Confidence threshold
        #                 (x1, y1), (x2, y2), (x3, y3), (x4, y4) = bbox 
        #                 tx_min = text_x1 + min(x1, x2, x3, x4)
        #                 ty_min = text_y1 + min(y1, y2, y3, y4)
        #                 tx_max = text_x1 + max(x1, x2, x3, x4)
        #                 ty_max = text_y1 + max(y1, y2, y3, y4)

        #                 abs_tx_min = min(x1, x2, x3, x4)
        #                 abs_ty_min = min(y1, y2, y3, y4)
        #                 abs_tx_max = max(x1, x2, x3, x4)
        #                 abs_ty_max = max(y1, y2, y3, y4)

        #                 text_bbox_list.append((tx_min, ty_min, tx_max, ty_max, text))  # Store text bounding box
        #                 # cv2.rectangle(text_roi, (abs_tx_min, abs_ty_min), (abs_tx_max, abs_ty_max), (0, 0, 255), 2)  # Draw red box for text
        #                 # cv2.rectangle(self.image, (text_x1, text_y1), (text_x2, text_y2), (0, 0, 255), 2)  # Draw red box for text

        #         # Check for text-circle overlap (more accurate)
        #         circle_rejected = False
        #         for (tx_min, ty_min, tx_max, ty_max, text) in text_bbox_list:
        #             if (abs(ty_min) < abs(circle_bottom-5)):
        #                 circle_rejected = True
        #                 break  # Reject immediately if overlap found

        #         # Only draw circles that do NOT overlap with text
        #         if not circle_rejected:
        #             valid_circles.append((x, y, r,text))
        #             # cv2.circle(self.image, (x, y), r, (0, 255, 0), 2)  # Draw green circle
        #             # cv2.line(self.image, (x - r, y + r), (x + r, y + r), (0, 255, 0), 2)  # Draw bottom line
        #             # cv2.circle(self.image, (tx_min, ty_min), 3, (255, 0, 0), -1)  # Blue point


        return valid_circles  # Return only valid circles

    def display_result(self):
        """Display the processed image in a window until 'q' is pressed."""
        while True:
            cv2.imshow("Detected Participants", self.image)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or cv2.getWindowProperty("Detected Participants", cv2.WND_PROP_VISIBLE) < 1:
                break
        cv2.destroyAllWindows()


# Run the processing
image_path = "image2.png"  # Change this to your image path
image = cv2.imread(image_path)
processor = MeetingProcessor(image_path)
# participants = processor.process_image()
# for (x, y, r, text) in participants:
#     print(text)
# # print("Detected Participants:", participants)
# processor.display_result()


processed_image, detected_boxes = processor.detect_speaker_boxes(image)


scale_percent = 80  # Adjust percentage as needed
width = int(processed_image.shape[1] * scale_percent / 100)
height = int(processed_image.shape[0] * scale_percent / 100)
resized_image = cv2.resize(processed_image, (width, height), interpolation=cv2.INTER_AREA)

# Show the smaller image
cv2.imshow("Detected Text (Resized)", resized_image)
cv2.waitKey(0)
cv2.destroyAllWindows()
