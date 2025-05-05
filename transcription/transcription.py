import concurrent
import whisper
from pyannote.audio import Pipeline
import torch
import numpy as np
import subprocess
import os
import json
from dotenv import load_dotenv



load_dotenv()

def trim_audio(input_file, output_file, duration=60, delete_files=None):
    if delete_files:
        for file in delete_files:
            if os.path.exists(file):
                os.remove(file)
                print(f"Deleted: {file}")
    command = [
        "ffmpeg",
        "-i", input_file,
        "-t", str(duration), 
        "-c:a", "copy",
        "-c:v", "copy",
        output_file
    ]
    subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    print("files deleted successfully")

def match_speakers_to_transcript(segments, speaker_info, output_file):
    transcript_data = []

    for segment in segments:
        start, end = segment["start"], segment["end"]
        speaker_names = set()
        for s in speaker_info:
            if s["start"] <= start <= s["end"]:
                speaker_names.add(s["speaker"])
        speakers = list(speaker_names) if speaker_names else ["Unknown"]
        transcript_data.append({
            "timestamp": f"{start:.2f}s",
            "speaker": speakers,
            "text": segment["text"]
        })
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(transcript_data, f, indent=4)
    return transcript_data

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

def process_segment(turn, speaker):
    """Helper function to process a single diarization segment."""
    return {
        "speaker": speaker,
        "start": turn.start,
        "end": turn.end
    }

def diarize_audio(audio_file):
    hugging_face_token = os.getenv("hugging_face_token")
    
    # Load diarization model
    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization@2.1",
        use_auth_token=hugging_face_token
    )
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    pipeline.to(device)

    # Perform diarization
    diarization = pipeline(audio_file)
    
    speaker_segments = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=10) as executor:
        future_results = {
            executor.submit(process_segment, turn, speaker): (turn, speaker)
            for turn, _, speaker in diarization.itertracks(yield_label=True)
        }

        for future in concurrent.futures.as_completed(future_results):
            speaker_segments.append(future.result())
            
    executor.shutdown(wait=True)
    return speaker_segments

def transcribe_audio(audio_file):
    model = whisper.load_model("base").to("cuda:6")
    result = model.transcribe(audio_file)
    return result["text"], result["segments"]


# trim_audio(original_audio_path, trimmed_audio_path,duration=100,delete_files=files_to_delete)
# convert_mp4_to_wav(original_audio_path, output_wav)

# Process the trimmed file
# transcript, segments = transcribe_audio(output_wav)
# speaker_info = diarize_audio(output_wav)

# transcript = match_speakers_to_transcript(segments, speaker_info)

# Print the generated JSON
# print(json.dumps(transcript, indent=4))

