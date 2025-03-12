import threading
import sys
import time
from meetbot import GoogleMeetRecorder, MSTeamsRecorder, ZoomMeetingRecorder

MEET_URL = "https://meet.google.com/vsb-tokr-eea"
TEAMS_URL = "https://teams.microsoft.com/l/meetup-join/19%3ameeting_YzA4N2Y3ZjQtNzliMS00NzFhLThjYTEtMzExMDUwMTViMzBm%40thread.v2/0?context=%7b%22Tid%22%3a%22ebd44379-62c4-41c8-8741-80fadcf2379e%22%2c%22Oid%22%3a%221692d7ae-7733-42ec-9e9e-4f921497626f%22%7d"
ZOOM_URL = "https://us05web.zoom.us/j/81004014333?pwd=bvDn807p2S0wC8fXdPAxoJUjq2pQoj.1"
FILE_OUTPUT_PATH = "/home/mudit/Desktop/test/recordingbot/meeting.mp4"

# Choose the platform
platform = input("Enter 'meet' for Google Meet or 'teams' for MS Teams or 'zoom' for Zoom: ").strip().lower()

if platform == "meet":
    recorder = GoogleMeetRecorder(MEET_URL, FILE_OUTPUT_PATH)
elif platform == "teams":
    recorder = MSTeamsRecorder(TEAMS_URL, FILE_OUTPUT_PATH)
elif platform == "zoom":
    recorder = ZoomMeetingRecorder(ZOOM_URL, FILE_OUTPUT_PATH)
else:
    print("Invalid platform!")
    exit()

recorder.join_meeting()

# Function to detect Enter keypress in a separate thread
def wait_for_exit():
    print("Press Enter to stop recording and leave the meeting...")
    sys.stdin.read(1)
    print("Enter detected! Leaving meeting...")
    recorder.leave_meeting()
    print("Meeting left, waiting for 10 seconds before cleanup...")
    time.sleep(10)
    recorder.close_resources()
    print("Resources closed.")

# Start the input listener in a separate thread
exit_thread = threading.Thread(target=wait_for_exit, daemon=True)
exit_thread.start()

# Keep the main thread running
exit_thread.join()
