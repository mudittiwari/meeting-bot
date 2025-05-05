import random
import sys
import threading
import time
import os
import subprocess
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
import signal
import logging


logging.basicConfig(
    level=logging.ERROR,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)
class BaseRecorder:
    def __init__(self, meeting_url, file_output_path):
        self.meeting_url = meeting_url
        self.file_output_path = file_output_path
        self.ffmpeg_process = None
        self.driver = None

    def start_virtual_audio_sink(self):
        os.system("pulseaudio --start")
        os.system("pactl load-module module-null-sink sink_name=VirtualSink")
        os.system("pactl set-default-sink VirtualSink")
        
    def start_virtual_display(self):
        os.environ["DISPLAY"] = f":{99}"
        os.system(f"Xvfb :{99} -screen 0 1920x1080x24 &")
        
    def start_ffmpeg_recording(self):
        try:
            print("Starting FFmpeg recording...")
            print("Output path:", self.file_output_path)

            if not self.file_output_path:
                raise ValueError("Output path is not set.")
            os.makedirs(os.path.dirname(self.file_output_path), exist_ok=True)
            subprocess.Popen(
                [
                    "ffmpeg",
                    "-y",
                    "-f", "x11grab",
                    "-r", "30",
                    "-video_size", "1920x1080",
                    "-framerate", "30",
                    # "-draw_mouse", "0",
                    "-i", ":99",
                    "-f", "pulse",
                    "-i", "VirtualSink.monitor",
                    "-ac", "2",
                    "-ar", "48000",
                    "-b:a", "320k",
                    "-codec:a", "libmp3lame",
                    "-af", "highpass=f=200,lowpass=f=3000,loudnorm",
                    "-codec:v", "libx264",
                    "-preset", "ultrafast",
                    "-pix_fmt", "yuv420p",
                    "-fps_mode", "cfr",
                    self.file_output_path
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
        except Exception as e:
            print("Exception occurred while starting FFmpeg:")
            print(str(e))

    def setup_browser(self):
        options = uc.ChromeOptions()
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--use-fake-ui-for-media-stream")
        options.add_argument("--use-fake-device-for-media-stream")
        options.add_argument("--disable-usb-devices")
        options.add_argument("--disable-media-source")
        options.add_argument("--disable-webrtc")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-notifications")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-default-apps")
        options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.6998.35 Safari/537.36"
        )
        self.driver = uc.Chrome(options=options)

    def close_resources(self):
        """Stop FFmpeg recording and clean up resources properly"""
        try:
            if self.ffmpeg_process:
                print("Stopping recording...")
                self.ffmpeg_process.send_signal(signal.SIGINT)
                self.ffmpeg_process.wait()
                print("Recording stopped and saved:", self.file_output_path)

            if self.driver:
                self.driver.quit()
                print("WebDriver closed.")

            os.system("pkill chrome")
            os.system("pkill chromedriver")
            os.system("pulseaudio --kill")
            os.system("pkill Xvfb")
            print("All resources cleaned up.")

        except Exception as e:
            print("Error closing resources:", e)


class GoogleMeetRecorder(BaseRecorder):
    def __init__(self, meeting_url, file_output_path):
        super().__init__(meeting_url, file_output_path)

    def join_meeting(self):
        self.start_virtual_audio_sink()
        self.start_virtual_display()
        self.start_ffmpeg_recording()
        self.setup_browser()
        self.driver.get(self.meeting_url)
        time.sleep(5)
        wait = WebDriverWait(self.driver, 15)

        try:
            mute_mic_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//div[contains(@aria-label, 'Turn off microphone')]"))
            )
            mute_mic_button.click()
            print("Microphone Muted")

            mute_camera_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//div[contains(@aria-label, 'Turn off camera')]"))
            )
            mute_camera_button.click()
            print("Camera Turned Off")

            time.sleep(2)
        except Exception as e:
            print("Could not mute microphone or turn off camera:", e)

        try:
            name_input = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Your name']")))
            name_input.send_keys("Bot User")
            print("Name inserted successfully")
            time.sleep(2)
        except Exception as e:
            print("Could not enter name:", e)

        try:
            ask_to_join_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//span[contains(text(),'Ask to join')]"))
            )
            ask_to_join_button.click()
            print("Clicked 'Ask to Join' successfully!")
        except Exception as e:
            print("Could not find 'Ask to Join' button:", e)

    def leave_meeting(self):
        wait = WebDriverWait(self.driver, 15)
        try:
            leave_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='Leave call']")))
            leave_button.click()
            print("Meeting left successfully!")
        except Exception as e:
            print("Could not leave the meeting:", e)


class MSTeamsRecorder(BaseRecorder):
    def __init__(self, meeting_url, file_output_path):
        super().__init__(meeting_url, file_output_path)
    def close_external_protocol_popup(self):
        time.sleep(2)  # Wait for the pop-up to appear
        os.system("xdotool key Return")
        print("Pressed Enter to dismiss the pop-up")

    def close_mic_camera(self, wait):
        try:
            # **Find the microphone toggle button**
            mute_mic_button = wait.until(
                EC.presence_of_element_located((By.XPATH, "//div[@data-tid='toggle-mute']"))
            )

            # **Check if the mic is unmuted (toggle-mute-true) and mute it**
            if "toggle-mute-true" in mute_mic_button.get_attribute("data-cid"):
                mute_mic_button.click()
                print("Microphone Muted")
            else:
                print("Microphone is already muted")
        except Exception as e:
            print("Could not find the microphone toggle button:", e)



        try:
            # **Find the microphone toggle button**
            toggle_camera_button = wait.until(
                EC.presence_of_element_located((By.XPATH, "//div[@data-tid='toggle-video']"))
            )

            # **Check if the mic is unmuted (toggle-mute-true) and mute it**
            if "toggle-video-true" in toggle_camera_button.get_attribute("data-cid"):
                toggle_camera_button.click()
                print("Camera Switched Off")
            else:
                print("Camera is already off")
        except Exception as e:
            print("Could not find the camera toggle button:", e)


    def join_meeting(self):
        self.start_virtual_audio_sink()
        self.start_virtual_display()
        self.start_ffmpeg_recording()
        self.setup_browser()
        self.driver.get(self.meeting_url)
        time.sleep(5)
        self.close_external_protocol_popup()

        wait = WebDriverWait(self.driver, 15)

        try:
            continue_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[@data-tid='joinOnWeb']"))
            )
            continue_button.click()
            print("Clicked 'Continue on this browser' button")
            time.sleep(5)  # Wait for the next page to load
        except Exception as e:
            print("Could not find the 'Continue on this browser' button:", e)



        try:
            name_input = wait.until(
                EC.presence_of_element_located((By.XPATH, "//input[@data-tid='prejoin-display-name-input']"))
            )
            print(name_input)
            name_input.clear()  # Clear any existing text
            name_input.send_keys("Bot User")  # Enter the name
            print("Name inserted successfully")
            time.sleep(2)
        except Exception as e:
            print("Could not enter name:", e)


        

        self.close_mic_camera(wait=wait)
        try:
            join_now_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[@data-tid='prejoin-join-button']"))
            )
            join_now_button.click()
            print("Clicked 'Join now' button")
        except Exception as e:
            print("Could not find the 'Join now' button:", e)

        self.close_mic_camera(wait=wait)

        

        
    def leave_meeting(self):
        wait = WebDriverWait(self.driver, 15)
        try:
            leave_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='Leave (Ctrl+Shift+H)']")))
            leave_button.click()
            time.sleep(10)
        except Exception as e:
            print("Could not leave the meeting:", e)


class ZoomMeetingRecorder(BaseRecorder):
    def __init__(self, meeting_url, file_output_path):
        super().__init__(meeting_url, file_output_path)

    def close_external_protocol_popup(self):
        time.sleep(2)  # Wait for the pop-up to appear
        os.system("xdotool key Return")
        print("Pressed Enter to dismiss the pop-up")

    def join_meeting(self):
        self.start_virtual_audio_sink()
        self.start_virtual_display()
        self.start_ffmpeg_recording()
        self.setup_browser()
        self.driver.get(self.meeting_url)
        time.sleep(5)
        wait = WebDriverWait(self.driver, 10)
        self.close_external_protocol_popup()

        try:
            launch_meeting_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//div[@role='button' and contains(text(), 'Launch Meeting')]"))
            )
            print(launch_meeting_button)
            launch_meeting_button.click()
            time.sleep(2)
            self.close_external_protocol_popup()
            print("Lanch meeting Button Clicked")
            time.sleep(10j)
        except Exception as e:
            print("Could not click launch meeting button", e)


        try:
            join_from_browser_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//a[@role='button' and contains(text(), 'Join from your browser')]"))
            )
            join_from_browser_button.click()
            print("join from browser button clicked")
            time.sleep(10)
        except Exception as e:
            print("Could not click join from browser button", e)


        try:
            # print(self.driver.page_source)
            # with open("page_source.html", "w", encoding="utf-8") as file:
            #     file.write(self.driver.page_source)

            wait.until(EC.presence_of_element_located((By.ID, "webclient")))
            self.driver.switch_to.frame("webclient")  # Switch to iframe
            mute_mic_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(@aria-label, 'Mute')]"))
)
            print(mute_mic_button)
            mute_mic_button.click()
            print("Microphone Muted")
            mute_camera_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='Stop Video']"))
            )
            mute_camera_button.click()
            print("Camera Turned Off")
            time.sleep(2)
        except Exception as e:
            print("Could not mute microphone or turn off camera:", e)

        try:
            name_input = wait.until(
            EC.presence_of_element_located((By.ID, "input-for-name"))
        )
            # Enter "Bot User" into the input field
            name_input.clear()
            name_input.send_keys("Bot User")
            print("Name inserted successfully")
            time.sleep(2)
        except Exception as e:
            print("Could not enter name:", e)

        try:
            join_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'preview-join-button')]"))
            )
            join_button.click()
            print("Clicked 'Join' successfully!")
        except Exception as e:
            print("Could not find 'Join' button:", e)

    def leave_meeting(self):
        wait = WebDriverWait(self.driver, 15)
        action = ActionChains(self.driver)
        action.move_by_offset(100, 100).perform()
        time.sleep(1)
        try:
            leave_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[normalize-space()='Leave']"))
            )
            self.driver.execute_script("arguments[0].click();", leave_button)
            # leave_button.click()
            time.sleep(2)
            leave_meeting_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[normalize-space()='Leave Meeting']"))
            )
            self.driver.execute_script("arguments[0].click();", leave_meeting_button)
            # leave_meeting_button.click()
            
            print("Meeting left successfully!")
        except Exception as e:
            print("Could not leave the meeting:", e)


def start_recording_bot():
    MEET_URL = "https://meet.google.com/tjq-ehib-gbh"
    TEAMS_URL = "https://teams.microsoft.com/l/meetup-join/19%3ameeting_YzA4N2Y3ZjQtNzliMS00NzFhLThjYTEtMzExMDUwMTViMzBm%40thread.v2/0?context=%7b%22Tid%22%3a%22ebd44379-62c4-41c8-8741-80fadcf2379e%22%2c%22Oid%22%3a%221692d7ae-7733-42ec-9e9e-4f921497626f%22%7d"
    ZOOM_URL = "https://us05web.zoom.us/j/81004014333?pwd=bvDn807p2S0wC8fXdPAxoJUjq2pQoj.1"
    FILE_OUTPUT_PATH = os.path.abspath("meeting.mp4")

    # platform = input("Enter 'meet' for Google Meet or 'teams' for MS Teams or 'zoom' for Zoom: ").strip().lower()

    # if platform == "meet":
    #     recorder = GoogleMeetRecorder(MEET_URL, FILE_OUTPUT_PATH)
    # elif platform == "teams":
    #     recorder = MSTeamsRecorder(TEAMS_URL, FILE_OUTPUT_PATH)
    # elif platform == "zoom":
    #     recorder = ZoomMeetingRecorder(ZOOM_URL, FILE_OUTPUT_PATH)
    # else:
    #     print("Invalid platform!")
    #     exit()

    recorder = GoogleMeetRecorder(MEET_URL, FILE_OUTPUT_PATH)
    recorder.join_meeting()
    return recorder
    
    
def wait_for_exit(recorder, stop_flag_path="/app/STOP.txt"):
    print(f"Waiting for {stop_flag_path} to appear to stop recording...")
    while not os.path.exists(stop_flag_path):
        time.sleep(1)
    print("STOP file detected! Stopping...")
    recorder.leave_meeting()
    time.sleep(2)
    recorder.close_resources()
    print("Resources closed.")




if __name__ == "__main__":
    recorder = start_recording_bot()
    wait_for_exit(recorder)


















































# import time
# import os
# import undetected_chromedriver as uc
# from selenium.webdriver.common.by import By
# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.support import expected_conditions as EC
# import subprocess
# import signal

# MEETING_URL = "https://meet.google.com/xdi-ecab-hzj"
# AUDIO_OUTPUT_PATH = "/home/mudit/Desktop/test/recordingbot/meeting_audio.mp3"
# FILE_OUTPUT_PATH = "/home/mudit/Desktop/test/recordingbot/meeting.mp4"

# # Use Pulseaudio Virtual Sink for Audio Capture
# os.system("pulseaudio --start")

# # Start FFmpeg Audio Recording
# os.system("pactl load-module module-null-sink sink_name=VirtualSink")

# # Start FFmpeg Audio Recording
# os.system("Xvfb :99 -screen 0 1920x1080x24 &")
# os.environ["DISPLAY"] = ":99"

# # # Start FFmpeg Recording (Captures Video + Audio)
# ffmpeg_process = subprocess.Popen(
#     [
#         "ffmpeg",
#         "-y",
        
#         # Video Configuration
#         "-f", "x11grab",            
#         "-video_size", "1920x1080", 
#         "-framerate", "30",         
#         "-i", ":99",

#         # audio Configuration
#         "-f", "pulse",
#         "-i", "VirtualSink.monitor",
#         "-ac", "2",
#         "-ar", "48000",
#         "-b:a", "320k",
#         "-codec:a", "libmp3lame",
#         "-af", "highpass=f=200,lowpass=f=3000,loudnorm",

#         # Video Encoding
#         "-codec:v", "libx264",
#         "-preset", "ultrafast",
#         "-pix_fmt", "yuv420p",

#         FILE_OUTPUT_PATH 
#     ],
#     stdout=subprocess.PIPE,
#     stderr=subprocess.PIPE
# )


# options = uc.ChromeOptions()
# # options.add_argument("--headless=new")
# options.add_argument("--window-size=1920,1080")

# options.add_argument("--disable-blink-features=AutomationControlled")
# options.add_argument("--use-fake-ui-for-media-stream")
# options.add_argument("--use-fake-device-for-media-stream")
# options.add_argument("--disable-usb-devices")
# options.add_argument("--disable-media-source")
# options.add_argument("--disable-features=MediaCapture")
# options.add_argument("--disable-webrtc")

# options.add_argument("--disable-popup-blocking")
# options.add_argument("--disable-notifications")
# options.add_argument("--no-sandbox")
# options.add_argument("--disable-dev-shm-usage")
# options.add_argument(
#     "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.6998.35 Safari/537.36"
# )

# driver = uc.Chrome(options=options)
# driver.get(MEETING_URL)
# time.sleep(5)

# driver.execute_script("document.body.style.zoom='100%'")
# wait = WebDriverWait(driver, 15)



# try:
#     mute_mic_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[contains(@aria-label, 'Turn off microphone')]")))
#     mute_mic_button.click()
#     print("Microphone Muted")

#     mute_camera_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[contains(@aria-label, 'Turn off camera')]")))
#     mute_camera_button.click()
#     print("Camera Turned Off")

#     time.sleep(2)
# except Exception as e:
#     print("Could not mute microphone or turn off camera:", e)


# try:
#     name_input = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Your name']")))
#     name_input.send_keys("Bot User")
#     print("name inserted successfully")
#     time.sleep(2)
# except Exception as e:
#     print("Could not enter name:", e)

# try:
#     ask_to_join_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[contains(text(),'Ask to join')]")))
#     ask_to_join_button.click()
#     print("Clicked 'Ask to Join' successfully!")
# except Exception as e:
#     print("Could not find 'Ask to Join' button:", e)

# MEETING_DURATION = 30
# time.sleep(MEETING_DURATION)

# try:
#     leave_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='Leave call']")))
#     leave_button.click()
#     print("Meeting left successfully!")
# except Exception as e:
#     print("Could not leave the meeting:", e)

# ffmpeg_process.terminate()
# print(f"Meeting recording saved as {FILE_OUTPUT_PATH}")

# driver.quit()
# os.system("pkill chrome")  
# os.system("pkill chromedriver")
# os.system("pulseaudio --kill")
# os.system("pkill Xvfb")






