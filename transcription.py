import whisper
from pyannote.audio import Pipeline
import torch
import numpy as np
import subprocess
import os

def trim_audio(input_file, output_file, duration=600, delete_files=None):
    """Trim the audio/video file to the first `duration` seconds (default: 10 minutes = 600s).
    Deletes specified files before running ffmpeg.
    """
    # Ensure delete_files is a list
    if delete_files:
        for file in delete_files:
            if os.path.exists(file):
                os.remove(file)
                print(f"Deleted: {file}")

    # FFmpeg command to trim the video/audio file
    command = [
        "ffmpeg",
        "-i", input_file,
        "-t", str(duration),  # Trim to specified duration (default 600s)
        "-c:a", "copy",
        "-c:v", "copy",  # Copy streams without re-encoding
        output_file
    ]

    subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

def match_speakers_to_transcript(segments, speaker_info):
    """Assign speakers to transcript based on timestamps"""
    transcript_with_speakers = []
    
    for segment in segments:
        start, end = segment["start"], segment["end"]
        speaker = "Unknown"
        for s in speaker_info:
            if s["start"] <= start <= s["end"]:
                speaker = s["speaker"]
                break

        transcript_with_speakers.append(f"[{speaker}] {segment['text']}")

    return "\n".join(transcript_with_speakers)

def convert_mp4_to_wav(input_path, output_path):
    """Convert MP4 to WAV format to ensure compatibility with soundfile."""
    command = [
        "ffmpeg",
        "-i", input_path,
        "-vn",  # Remove video
        "-ac", "1",  # Convert to mono audio
        "-ar", "16000",  # Set sample rate to 16kHz (good for ASR)
        "-acodec", "pcm_s16le",  # Uncompressed WAV format
        output_path
    ]
    
    subprocess.run(command, check=True)
    return output_path


def diarize_audio(audio_file):
    """Perform speaker diarization using Pyannote"""
    pipeline = Pipeline.from_pretrained(
    "pyannote/speaker-diarization@2.1",
    use_auth_token="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")

    # Replace "${AUDIO_FILE_PATH}" with the path to your audio file
    diarization = pipeline(audio_file)


    
    speaker_segments = []
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        speaker_segments.append({
            "speaker": speaker,
            "start": turn.start,
            "end": turn.end
        })

    return speaker_segments

def transcribe_audio(audio_file):
    """Transcribe audio using OpenAI Whisper"""
    model = whisper.load_model("base").to("cuda:6")
    result = model.transcribe(audio_file)
    # print(result["text"], result["segments"])
    return result["text"], result["segments"]

# File paths
original_audio_path = "/mnt/nvme_disk2/User_data/nb57077k/meetbot_project/recording.mp4"
trimmed_audio_path = "/mnt/nvme_disk2/User_data/nb57077k/meetbot_project/trimmed_recording.mp4"
output_wav = "/mnt/nvme_disk2/User_data/nb57077k/meetbot_project/trimmed_recording.wav"
files_to_delete = ["/mnt/nvme_disk2/User_data/nb57077k/meetbot_project/trimmed_recording.mp4", "/mnt/nvme_disk2/User_data/nb57077k/meetbot_project/trimmed_recording.wav"]
trim_audio(original_audio_path, trimmed_audio_path,duration=600,delete_files=files_to_delete)
convert_mp4_to_wav(trimmed_audio_path, output_wav)


# Process the trimmed file
transcript, segments = transcribe_audio(output_wav)
speaker_info = diarize_audio(output_wav)

# Match speakers
final_transcript = match_speakers_to_transcript(segments, speaker_info)

with open("transcript.txt", "w", encoding="utf-8") as file:
    file.write(final_transcript)


print("Final Transcript with Speakers:\n", final_transcript)
