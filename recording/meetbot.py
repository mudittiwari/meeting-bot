import json
import redis
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
from handleZIP import zipIt
import asyncio
import shutil


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
        display_num = 99
        os.environ["DISPLAY"] = f":{display_num}"
        lock_file = f"/tmp/.X{display_num}-lock"

        # Kill any running Xvfb on :99
        print("Checking if Xvfb is running on :99...")
        try:
            # Find and kill any Xvfb process using :99
            output = subprocess.getoutput(f"ps aux | grep 'Xvfb :{display_num}' | grep -v grep")
            if output:
                print("Existing Xvfb process found. Killing it...")
                pid = output.split()[1]
                os.system(f"kill -9 {pid}")
                time.sleep(1)
            else:
                print("No existing Xvfb process found.")
        except Exception as e:
            print("Error while checking/killing existing Xvfb:", str(e))

        # Remove lock file if it still exists
        if os.path.exists(lock_file):
            print(f"Removing stale Xvfb lock file: {lock_file}")
            os.remove(lock_file)

        # Start Xvfb
        print(f"Starting Xvfb on display :{display_num}")
        os.system(f"Xvfb :{display_num} -screen 0 1920x1080x24 &")

    # def start_virtual_display(self):
    #     display_num = 99
    #     os.environ["DISPLAY"] = f":{display_num}"
    
    #     # Clean up any stale lock files
    #     lock_file = f"/tmp/.X{display_num}-lock"
    #     if os.path.exists(lock_file):
    #         print(f"Removing stale Xvfb lock file: {lock_file}")
    #         os.remove(lock_file)
        
    #     # Start Xvfb
    #     print(f"Starting Xvfb on display :{display_num}")
    #     os.system(f"Xvfb :{display_num} -screen 0 1920x1080x24 &")
        
    # def start_ffmpeg_recording(self):
    #     try:
    #         print("Starting FFmpeg recording...")
    #         print("Output path:", self.file_output_path)

    #         if not self.file_output_path:
    #             raise ValueError("Output path is not set.")
    #         os.makedirs(os.path.dirname(self.file_output_path), exist_ok=True)
    #         self.ffmpeg_process =  subprocess.Popen(
    #             [
    #                 "ffmpeg",
    #                 "-y",
    #                 "-f", "x11grab",
    #                 "-r", "30",
    #                 "-video_size", "1920x1080",
    #                 "-framerate", "30",
    #                 # "-draw_mouse", "0",
    #                 "-i", ":99",
    #                 "-f", "pulse",
    #                 "-i", "VirtualSink.monitor",
    #                 "-ac", "2",
    #                 "-ar", "48000",
    #                 "-b:a", "320k",
    #                 "-codec:a", "libmp3lame",
    #                 "-af", "highpass=f=200,lowpass=f=3000,loudnorm",
    #                 "-codec:v", "libx264",
    #                 "-preset", "ultrafast",
    #                 "-pix_fmt", "yuv420p",
    #                 "-fps_mode", "cfr",
    #                 self.file_output_path
    #             ],
    #             stdout=subprocess.PIPE,
    #             stderr=subprocess.PIPE
    #         )
    #     except Exception as e:
    #         print("Exception occurred while starting FFmpeg:")
    #         print(str(e))

    def start_ffmpeg_recording(self):
        try:
            print("Starting FFmpeg recording...")
            print("Output path:", self.file_output_path)

            if not self.file_output_path:
                raise ValueError("Output path is not set.")
            os.makedirs(os.path.dirname(self.file_output_path), exist_ok=True)

            self.ffmpeg_process = subprocess.Popen(
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

            # Function to consume a pipe continuously
            def consume(pipe):
                for _ in iter(pipe.readline, b''):
                    pass
                pipe.close()

            # Start threads to consume stdout and stderr
            threading.Thread(target=consume, args=(self.ffmpeg_process.stdout,), daemon=True).start()
            threading.Thread(target=consume, args=(self.ffmpeg_process.stderr,), daemon=True).start()

        except Exception as e:
            print("Exception occurred while starting FFmpeg:")
            print(str(e))

    def stop_ffmpeg_recording(self):
        if hasattr(self, 'ffmpeg_process') and self.ffmpeg_process:
            print("Stopping FFmpeg recording...")
            self.ffmpeg_process.terminate()  # sends SIGTERM to FFmpeg
            self.ffmpeg_process.wait()
            print("FFmpeg recording stopped.")
            self.ffmpeg_process = None

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
        options.add_argument("--disable-default-apps")
        options.add_argument('--ignore-certificate-errors')
        options.add_argument('--allow-running-insecure-content')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.6998.35 Safari/537.36"
        )
        self.driver = uc.Chrome(options=options)

    # def close_resources(self):
    #     """Stop FFmpeg recording and clean up resources properly"""
    #     try:
    #         if self.ffmpeg_process:
    #             print("Stopping recording...")
    #             self.ffmpeg_process.terminate()
    #             try:
    #                 stdout, stderr = self.ffmpeg_process.communicate(timeout=10)
    #                 print("FFmpeg stderr:\n", stderr.decode())
    #             except subprocess.TimeoutExpired:
    #                 self.ffmpeg_process.kill()
    #                 print("FFmpeg force-killed after timeout")

    #         if self.driver:
    #             self.driver.quit()
    #             print("WebDriver closed.")

    #         os.system("pkill chrome")
    #         os.system("pkill chromedriver")
    #         os.system("pulseaudio --kill")
    #         os.system("pkill Xvfb")
    #         if os.path.exists(self.file_output_path):
    #             os.chown(self.file_output_path, 1039, 1042)
    #         else:
    #             print(f"Output file does not exist: {self.file_output_path}")
            
    #         print("All resources cleaned up.")

    #     except Exception as e:
    #         print("Error closing resources:", e)

    def close_resources(self):
        try:
            if self.ffmpeg_process:
                print("Stopping recording...")
                self.ffmpeg_process.terminate()

                if self.ffmpeg_process.poll() is None:
                    try:
                        stdout, stderr = self.ffmpeg_process.communicate(timeout=10)
                        print("FFmpeg stderr:\n", stderr.decode())
                    except subprocess.TimeoutExpired:
                        self.ffmpeg_process.kill()
                        print("FFmpeg force-killed after timeout")
                else:
                    print("FFmpeg process already exited.")

            if self.driver:
                self.driver.quit()
                print("WebDriver closed.")

            os.system("pkill chrome")
            os.system("pkill chromedriver")
            os.system("pulseaudio --kill")
            os.system("pkill Xvfb")

            if os.path.exists(self.file_output_path):
                os.chown(self.file_output_path, 1039, 1042)
            else:
                print(f"Output file does not exist: {self.file_output_path}")

            print("All resources cleaned up.")

        except Exception as e:
            print("Error closing resources:", e)


class GoogleMeetRecorder(BaseRecorder):
    def __init__(self, meeting_url, file_output_path):
        super().__init__(meeting_url, file_output_path)

    def join_meeting(self):
        self.start_virtual_audio_sink()
        self.start_virtual_display()
        # self.start_ffmpeg_recording()
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

            # print("Attempting to start recording now...")
            # self.start_ffmpeg_recording()
            # print("Recording started.")
        except Exception as e:
            print("Could not find 'Ask to Join' button:", e)

        try:
            joined_wait = WebDriverWait(self.driver, 120)  # wait up to 2 mins
            joined_wait.until(
                # Wait for "Leave call" button to confirm full join
                EC.presence_of_element_located((By.XPATH, "//button[@aria-label='Leave call']"))
            )
            print("Successfully joined the meeting.")
            self.start_ffmpeg_recording()
            print("Recording started.")
        except Exception as e:
            print("Never joined the meeting (maybe host denied or never accepted):", e)


        try:
            got_it_button = WebDriverWait(self.driver, 1).until(
                EC.element_to_be_clickable((By.XPATH, '//span[text()="Got it"]/ancestor::button'))
            )
            got_it_button.click()
            print("Closed the overlay dialog.")
        except:
            print("No overlay or 'Got it' button found.")
        
        try:
            # Find the "People" icon
            people_icon = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, '//i[contains(text(), "people")]'))
            )

            # Get the button containing the icon
            people_button = people_icon.find_element(By.XPATH, './ancestor::button[1]')

            # Wait until it's clickable
            WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable(people_button))

            # Scroll into view and click using JS
            self.driver.execute_script("arguments[0].scrollIntoView(true);", people_button)
            self.driver.execute_script("arguments[0].click();", people_button)

        except Exception as e:
            print("Exception while clicking People button:", e)

    def close_got_it_popup(self):
        try:
            got_it_button = WebDriverWait(self.driver, 1).until(
                EC.element_to_be_clickable((By.XPATH, '//span[text()="Got it"]/ancestor::button'))
            )
            got_it_button.click()
            print("Closed the overlay dialog.")
        except:
            print("No overlay or 'Got it' button found.")


    def leave_meeting(self):
        wait = WebDriverWait(self.driver, 15)
        try:
        # Optional: check if already removed from meeting
            print("Checking if bot is already removed from the meeting...")
            if "You’ve been removed" in self.driver.page_source or "has ended" in self.driver.page_source:
                print("Bot was already removed or meeting has ended.")
                return

            leave_button = wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//button[@aria-label='Leave call']")
            ))
            leave_button.click()
            print("Meeting left successfully!")
        except Exception as e:
            print("Could not leave the meeting:", e)

    def get_participants(self):
        try:
            # Locate the specific participant list using both role and aria-label
            participant_list = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((
                    By.XPATH,
                    '//div[@role="list" and @aria-label="Participants"]'
                ))
            )

            # print(participant_list)
            # Now find all children with role="listitem"
            list_items = participant_list.find_elements(By.XPATH, './/div[@role="listitem"]')

            # Extract and clean participant names
            matching = []
            for p in list_items:
                name = p.get_attribute("aria-label")
                if not name:
                    continue

                # Try to find the tooltip div inside the participant block
                try:
                    tooltip = p.find_element(By.XPATH, './/div[@role="tooltip"]')
                    # print(tooltip.get_attribute("outerHTML"))
                    tooltip_text = tooltip.get_attribute("textContent").strip().lower()
                    # print(tooltip_text)
                    if "mute" in tooltip_text and "unmute" not in tooltip_text:
                        # print(tooltip_text)
                        matching.append(name.replace("(You)", "").strip())
                except:
                    # Tooltip may not be present; skip silently
                    continue

            # print(matching)
            return  matching
            

        except Exception as e:
            print("Error retrieving participants:", e)

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


        try:
            joined_wait = WebDriverWait(self.driver, 120)  # wait up to 2 mins
            joined_wait.until(
                # Wait for "Leave call" button to confirm full join
                EC.presence_of_element_located((By.XPATH, '//button[@id="roster-button" and @aria-label="People"]'))
            )
            print("Successfully joined the meeting.")
            print("Recording started.")
            self.start_ffmpeg_recording()
        except Exception as e:
            print("Never joined the meeting (maybe host denied or never accepted):", e)
            
        try:
            # Wait until the "People" button is present and clickable
            people_button = WebDriverWait(self.driver, 30).until(
                EC.element_to_be_clickable((By.XPATH, '//button[@id="roster-button" and @aria-label="People"]'))
            )

            # Scroll into view and click using JS
            self.driver.execute_script("arguments[0].scrollIntoView(true);", people_button)
            self.driver.execute_script("arguments[0].click();", people_button)
            print("People button clicked successfully.")

        except Exception as e:
            print("Exception while clicking People button:", e)
       
    def get_participants(self):
        try:
            # Wait for any participant list item with role="presentation" and data-cid="roster-participant"
            participant_items = WebDriverWait(self.driver, 10).until(
                EC.presence_of_all_elements_located((
                    By.XPATH,
                    '//li[@role="presentation" and @data-cid="roster-participant"]'
                ))
            )

            matching = []

            for item in participant_items:
                aria_label = item.get_attribute("aria-label")
                if not aria_label:
                    continue

                # Example: "Bot User, Muted" or "John Doe, Unmuted"
                aria_label = aria_label.strip().lower()

                # Check for mute (only if "muted" is present but "unmuted" is NOT)
                if "unmuted" in aria_label:
                    # Extract name before the comma
                    name = aria_label.split(',')[0].strip().title()
                    matching.append(name)

            # print("unmuted participants:", matching)
            return matching

        except Exception as e:
            print("Error retrieving participants:", e)
        
    def leave_meeting(self):
        wait = WebDriverWait(self.driver, 15)
        try:
            leave_button = wait.until(EC.element_to_be_clickable((By.ID, "hangup-button")))
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

        try:
            action = ActionChains(self.driver)
            action.move_by_offset(100, 100).perform()
            time.sleep(1)
            participants_button = WebDriverWait(self.driver, 15).until(
                EC.element_to_be_clickable((
                    By.XPATH,
                    '//button[contains(@aria-label, "participants") and .//span[text()="Participants"]]'
                ))
            )
            
            # Scroll into view and click
            self.driver.execute_script("arguments[0].scrollIntoView(true);", participants_button)
            self.driver.execute_script("arguments[0].click();", participants_button)
        except Exception as e:
            print("Could not find 'Join' button:", e)

    def get_participants(self):
        try:
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_all_elements_located((By.XPATH, '//div[contains(@class, "participants-item__item-layout")]'))
            )
            participants = self.driver.find_elements(By.XPATH, '//div[contains(@class, "participants-item__item-layout")]')
            unmuted_names = []
            for participant in participants:
                try:
                    # print(f"\n--- Participant ---\n{html}\n")
                    svg_icons = participant.find_elements(By.TAG_NAME, 'svg')
                    svg_icon =svg_icons[0] if svg_icons else None
                    if svg_icon:
                        svg_class = svg_icon.get_attribute("class")
                        if "unmuted" in svg_class.lower():
                                name_element = participant.find_element(By.XPATH, './/span[contains(@class, "participants-item__display-name")]')
                                name = name_element.text.strip()
                                if "(Me)" in name:
                                    name = name.replace("(Me)", "").strip()
                                unmuted_names.append(name)
                except Exception as e:
                    print("Error finding participant icon:", e)
                    continue
            print("Unmuted Participants:", unmuted_names)
            return unmuted_names
        except Exception as e:
            print("Error while fetching unmuted participants:", e)
            return []

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


async def start_recording_bot(choice: str, meeting_url: str):
    # MEET_URL = "https://meet.google.com/myx-rsbb-nce"
    # TEAMS_URL = "https://teams.microsoft.com/l/meetup-join/19%3ameeting_YzA4N2Y3ZjQtNzliMS00NzFhLThjYTEtMzExMDUwMTViMzBm%40thread.v2/0?context=%7b%22Tid%22%3a%22ebd44379-62c4-41c8-8741-80fadcf2379e%22%2c%22Oid%22%3a%221692d7ae-7733-42ec-9e9e-4f921497626f%22%7d"
    # ZOOM_URL = "https://us05web.zoom.us/j/81004014333?pwd=bvDn807p2S0wC8fXdPAxoJUjq2pQoj.1"
    FILE_OUTPUT_PATH = os.path.abspath("/shared/meeting.mp4")

    # platform = input("Enter 'meet' for Google Meet or 'teams' for MS Teams or 'zoom' for Zoom: ").strip().lower()

    if choice == "gmeet":
        recorder = GoogleMeetRecorder(meeting_url, FILE_OUTPUT_PATH)
    elif choice == "teams":
        recorder = MSTeamsRecorder(meeting_url, FILE_OUTPUT_PATH)
    elif choice == "zoom":
        recorder = ZoomMeetingRecorder(meeting_url, FILE_OUTPUT_PATH)
    else:
        print("Invalid platform!")
        exit()

    # recorder = GoogleMeetRecorder(MEET_URL, FILE_OUTPUT_PATH)
    # recorder.join_meeting()

    # return recorder
    await asyncio.to_thread(recorder.join_meeting)
    # await recorder.join_meeting()

    return recorder

def append_speaker_data(file_path, timestamp, speaker_list):
    # Initialize data
    new_entry = {
        "timestamp": f"{timestamp}s",
        "speaker": speaker_list
    }

    # If the file exists, load existing array
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = []
    else:
        data = []

    # Append the new entry
    data.append(new_entry)

    # Save back to file
    with open(file_path, "w") as f:
        json.dump(data, f, indent=4)
    
    
async def wait_for_exit(recorder, choice, stop_flag_path="/app/STOP.txt"):
    INPUT_DIR = "/shared"

    #####################################code to delete zip file folder##################################

    # zip_folder_path = os.path.join(INPUT_DIR, "zips")
    # logger.info(zip_folder_path)
    # if os.path.isdir(zip_folder_path):
    #     try:
    #         shutil.rmtree(zip_folder_path)
    #         print(f"Deleted folder: {zip_folder_path}")
    #     except Exception as e:
    #         print(f"Failed to delete folder {zip_folder_path}: {e}")

    #####################################code to delete zip file folder##################################


    logger.info("Watching for input file...")
    print(f"Waiting for {stop_flag_path} to appear to stop recording...")
    timestamp = 0



    #####################################code to clear speaker log json##################################


    if os.path.exists(f"/shared/{choice}_merged_transcript.json"):
        os.remove(f"/shared/{choice}_merged_transcript.json")

    with open(f"/shared/{choice}_speaker_log.json", "w") as f:
        json.dump([], f, indent=4)

    #####################################code to clear speaker log json##################################




    while not os.path.exists(stop_flag_path):
        participants = recorder.get_participants()
        if(choice == "gmeet"):
            recorder.close_got_it_popup()
        append_speaker_data(f"/shared/{choice}_speaker_log.json", timestamp, participants)
        timestamp = timestamp + 1
        await asyncio.sleep(1)
    print("STOP file detected! Stopping...")
    await asyncio.to_thread(recorder.leave_meeting)
    await asyncio.sleep(2)
    await asyncio.to_thread(recorder.close_resources)
    print("Resources closed.")
    # subprocess.run([
    #     "docker", "exec", "worker", "python3", "main.py",
    #     "--mode", "normal"
    # ])
    # choice, original_video_path, file1_path, file2_path ,output_json_path, output_wav
    input_data = {
        "choice": choice,
        "original_video_path": recorder.file_output_path,
        "trimmed_video_path" : f"/shared/{choice}_trimmed_recording.mp4",
        "file1_path": f"/shared/{choice}_transcript_log.json",
        "file2_path": f"/shared/{choice}_speaker_log.json",
        "output_json_path": f"/shared/{choice}_merged_transcript.json",
        "output_wav": "/shared/meeting.wav",
    }
#   /shared/input-{uuid.uuid4().hex}
    filename = f"/shared/input-transcription.json"
    with open(filename, "w") as f:
        json.dump(input_data, f)

    print(f"Input file created: {filename}")
    print(f"Recording saved at: {recorder.file_output_path}")
    
    await asyncio.to_thread(recorder.stop_ffmpeg_recording)
    print("FFmpeg recording stopped after async tasks completed.")

def watch_loop():
    INPUT_DIR = "/shared"
    logger.info("Watching for input file...")
    while True:
        for file in os.listdir(INPUT_DIR):
            if file.startswith("input-bot") and file.endswith(".json"):
                file_path = os.path.join(INPUT_DIR, file)
                try:
                    with open(file_path, "r") as f:
                        data = json.load(f)
                    if "choice" in data and "meeting_url" in data:
                        recorder = start_recording_bot(data["choice"], data["meeting_url"])
                        time.sleep(30)
                        print(f"Starting recording for {data['choice']} meeting at {data['meeting_url']}")
                        wait_for_exit(recorder, data["choice"])

                    print(f"Processed: {file}")
                except Exception as e:
                    print(f"Error processing {file}: {e}")
                try:
                    os.remove(file_path)
                    print(f"Deleted: {file}")
                except Exception as e:
                    print(f"Failed to delete {file}: {e}")

        time.sleep(2)


if __name__ == "__main__":
    watch_loop()
    
    # recorder = start_recording_bot()
    # wait_for_exit(recorder)

# {"choice": "gmeet", "meeting_url" : "https://meet.google.com/jjc-evpv-stq"}
















































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






