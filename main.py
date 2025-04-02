import os
from multiprocessing import Process
import sys
import time
from meetbot import GoogleMeetRecorder, MSTeamsRecorder, ZoomMeetingRecorder
import json
from transcription import convert_mp4_to_wav, diarize_audio, match_speakers_to_transcript, transcribe_audio, trim_audio
from video_processing import TeamsProcessor, GoogleMeetProcessor
import time
import re
import torch.multiprocessing as mp


# os.environ["CUDA_VISIBLE_DEVICES"] = "6"  


def clean_name(name):
    return re.sub(r'[^a-zA-Z\s]+$', '', name).strip()

def get_unique_speaker_names(speaker_names):
    """ Remove short/incomplete names and keep only full names """
    cleaned_names = {clean_name(name): name for name in speaker_names}
    unique_names = set(cleaned_names.keys())
    full_names = set()

    for name in unique_names:
        if not any(name in other and name != other for other in unique_names):
            full_names.add(cleaned_names[name])
    return list(full_names)

def start_recording_bot():
    MEET_URL = "https://meet.google.com/amr-bvrt-htn"
    TEAMS_URL = "https://teams.microsoft.com/l/meetup-join/19%3ameeting_YzA4N2Y3ZjQtNzliMS00NzFhLThjYTEtMzExMDUwMTViMzBm%40thread.v2/0?context=%7b%22Tid%22%3a%22ebd44379-62c4-41c8-8741-80fadcf2379e%22%2c%22Oid%22%3a%221692d7ae-7733-42ec-9e9e-4f921497626f%22%7d"
    ZOOM_URL = "https://us05web.zoom.us/j/81004014333?pwd=bvDn807p2S0wC8fXdPAxoJUjq2pQoj.1"
    FILE_OUTPUT_PATH = "/home/mudit/Desktop/test/recordingbot/meeting.mp4"

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
    
    
    def wait_for_exit():
        print("Press Enter to stop recording and leave the meeting...")
        sys.stdin.read(1)
        print("Enter detected! Leaving meeting...")
        recorder.leave_meeting()
        print("Meeting left, waiting for 10 seconds before cleanup...")
        time.sleep(10)
        recorder.close_resources()
        print("Resources closed.")
    exit_thread = threading.Thread(target=wait_for_exit, daemon=True)
    exit_thread.start()
    exit_thread.join()

def merge_transcripts(transcript_1, transcript_2, threshold=1.0):
    """
    Merges two transcript lists by matching timestamps within a given threshold.
    
    Parameters:
    - transcript_1: List of dictionaries containing timestamps, speakers, and text.
    - transcript_2: List of dictionaries containing timestamps and speakers.
    - threshold: Maximum time difference (in seconds) to consider two timestamps as matching.

    Returns:
    - Merged list of transcript entries.
    """
    merged_transcript = []
    
    # Sort transcripts by timestamp
    transcript_1_sorted = sorted(transcript_1, key=lambda x: float(x["timestamp"][:-1]))
    transcript_2_sorted = sorted(transcript_2, key=lambda x: float(x["timestamp"][:-1]))

    i, j = 0, 0
    while i < len(transcript_1_sorted) and j < len(transcript_2_sorted):
        t1 = float(transcript_1_sorted[i]["timestamp"][:-1])
        t2 = float(transcript_2_sorted[j]["timestamp"][:-1])

        if abs(t1 - t2) <= threshold:
            real_speakers = [s for s in transcript_2_sorted[j]["speaker"] if not s.startswith("speaker")]
            merged_entry = {
                "timestamp": transcript_1_sorted[i]["timestamp"],
                "speaker": get_unique_speaker_names(real_speakers if real_speakers else ["Unknown"]),
                "text": transcript_1_sorted[i]["text"]
            }
            merged_transcript.append(merged_entry)
            i += 1
            j += 1
        elif t1 < t2:
            merged_transcript.append({
                "timestamp": transcript_1_sorted[i]["timestamp"],
                "speaker": ["Unknown"],
                "text": transcript_1_sorted[i]["text"]
            })
            i += 1
        else:
            real_speakers = [s for s in transcript_2_sorted[j]["speaker"] if not s.startswith("speaker")]
            merged_transcript.append({
                "timestamp": transcript_2_sorted[j]["timestamp"],
                "speaker": get_unique_speaker_names(real_speakers if real_speakers else ["Unknown"]),
                "text": ""  
            })
            j += 1

    while i < len(transcript_1_sorted):
        merged_transcript.append({
            "timestamp": transcript_1_sorted[i]["timestamp"],
            "speaker": ["Unknown"],
            "text": transcript_1_sorted[i]["text"]
        })
        i += 1

    while j < len(transcript_2_sorted):
        real_speakers = [s for s in transcript_2_sorted[j]["speaker"] if not s.startswith("speaker")]
        merged_transcript.append({
            "timestamp": transcript_2_sorted[j]["timestamp"],
            "speaker": get_unique_speaker_names(real_speakers if real_speakers else ["Unknown"]),
            "text": ""
        })
        j += 1

    return merged_transcript

def create_merge_transcript_file(file1_path, file2_path, output_path): 
    with open(file1_path, "r") as file1, open(file2_path, "r") as file2:
        transcript_1 = json.load(file1)
        transcript_2 = json.load(file2)
    merged_data = merge_transcripts(transcript_1, transcript_2)
    filtered_data = [entry for entry in merged_data if entry.get("text", "").strip()]
    with open(output_path, "w") as output_file:
        json.dump(filtered_data, output_file, indent=4)

    print(f"Merged transcript saved to {output_path}")

def process_parallel(video_path, trimmed_video_path, output_audio_path, files_to_delete, file1_path, file2_path, output_path, choice):
    start_time = time.time() 
    process1 = Process(target=get_whisper_transcript, args=(video_path, trimmed_video_path, output_audio_path, file1_path, files_to_delete))
    process2 = Process(target=get_video_ocr_results, args=(video_path,choice,file2_path))

    process1.start()
    process2.start()

    process1.join()
    process2.join()

    print("Merging files...")
    create_merge_transcript_file(file1_path, file2_path, output_path)

    end_time = time.time()
    execution_time = end_time - start_time
    print(f"Parallel processing completed in {execution_time:.2f} seconds")

def get_whisper_transcript(video_path,trimmed_video_path, output_audio_path, file1_path, files_to_delete=[]):
    print("running whisper")
    trim_audio(video_path, trimmed_video_path,duration=60,delete_files=files_to_delete)
    convert_mp4_to_wav(video_path, output_audio_path)
    transcript, segments = transcribe_audio(output_audio_path)
    speaker_info = diarize_audio(output_audio_path)
    match_speakers_to_transcript(segments, speaker_info, file1_path)
    # time.sleep(8)

def get_video_ocr_results(video_path, choice, file2_path):
    print("running ocr")
    if choice == "1":
        processor = GoogleMeetProcessor(video_path, file2_path) 
        processor.process_video()
    elif choice == "2":
        processor = TeamsProcessor(video_path, file2_path) 
        processor.process_video()
        
    # time.sleep(8)

def initialize():
    while True:
        print("\n=== Meeting Recorder ===")
        print("1. Google Meet")
        print("2. Microsoft Teams")
        print("3. Exit")
        
        choice = input("Please enter your numeric choice: ").strip()
        
        if choice == "1":
            prefix = "gmeet"
        elif choice == "2":
            prefix = "teams"
        elif choice == "3":
            print("Exiting program...")
            exit(0)
        else:
            print("Invalid choice! Please enter 1, 2, or 3.")
            continue  # Restart menu loop
        
        # Define file paths dynamically based on the chosen meeting type
        file1_path = f"{prefix}_transcript_log.json"
        file2_path = f"{prefix}_speaker_log.json"
        output_path = f"{prefix}_merged_transcript.json"
        original_video_path = f"/mnt/nvme_disk2/User_data/nb57077k/meetbot_project/{prefix}_output.mp4"
        trimmed_video_path = f"/mnt/nvme_disk2/User_data/nb57077k/meetbot_project/{prefix}_trimmed_recording.mp4"
        output_wav = f"/mnt/nvme_disk2/User_data/nb57077k/meetbot_project/{prefix}_trimmed_recording.wav"
        files_to_delete = [output_wav, trimmed_video_path]

        print(f"\nProcessing {prefix.capitalize()} meeting...\n")
        process_parallel(original_video_path, trimmed_video_path, output_wav, files_to_delete, file1_path, file2_path, output_path, choice)


if __name__ == "__main__":
    print(os.cpu_count()) 
    mp.set_start_method("spawn", force=True)
    initialize()
