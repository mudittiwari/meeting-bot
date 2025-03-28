import whisper
from pyannote.audio import Pipeline
import torch
import numpy as np
import subprocess
import os


hugging_face_token="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"
original_audio_path ="/mnt/nvme_disk2/User_data/nb57077k/meetbot_project/output.mp4"
trimmed_audio_path = "/mnt/nvme_disk2/User_data/nb57077k/meetbot_project/trimmed_recording.mp4"
output_wav = "/mnt/nvme_disk2/User_data/nb57077k/meetbot_project/trimmed_recording.wav"
files_to_delete = [ "/mnt/nvme_disk2/User_data/nb57077k/meetbot_project/trimmed_recording.wav"]

def trim_audio(input_file, output_file, duration=600, delete_files=None):
    if delete_files:
        for file in delete_files:
            if os.path.exists(file):
                os.remove(file)
                print(f"Deleted: {file}")
    # print("hello world")
    # command1 = [
    #     "ffmpeg",
    #     "-i", input_file,
    #     "-c:a", "aac",
    #     "-c:v", "libx264",
    #     "output.mp4"
    # ]
    # command2 = [
    #     "ffmpeg",
    #     "-i", input_file,
    #     "-t", str(duration), 
    #     "-c:a", "copy",
    #     "-c:v", "copy",
    #     output_file
    # ]


    # subprocess.run(command1, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    # subprocess.run(command2, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    print("files deleted successfully")

def match_speakers_to_transcript(segments, speaker_info):
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
    command = [
        "ffmpeg",
        "-i", input_path,
        "-vn", 
        "-ac", "1",
        "-ar", "16000",
        "-acodec", "pcm_s16le",
        output_path
    ]
    subprocess.run(command, check=True)
    return output_path


def diarize_audio(audio_file):
    pipeline = Pipeline.from_pretrained(
    "pyannote/speaker-diarization@2.1",
    use_auth_token=hugging_face_token)
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
    model = whisper.load_model("base").to("cuda:6")
    result = model.transcribe(audio_file)
    return result["text"], result["segments"]


trim_audio(original_audio_path, trimmed_audio_path,duration=100,delete_files=files_to_delete)
convert_mp4_to_wav(original_audio_path, output_wav)

# Process the trimmed file
transcript, segments = transcribe_audio(output_wav)
speaker_info = diarize_audio(output_wav)

# Match speakers
final_transcript = match_speakers_to_transcript(segments, speaker_info)

with open("transcript.txt", "w", encoding="utf-8") as file:
    file.write(final_transcript)


print("Final Transcript with Speakers:\n", final_transcript)
