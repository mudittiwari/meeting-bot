# Automated Meeting Recorder, Transcriber, and Speaker Diarization

This project automates the recording of online meetings, transcribes the audio, identifies speakers, and merges the information into a structured transcript.

## Features

- **Automated Meeting Recording**: Uses Selenium and browser automation to record meetings.
- **Transcription & Speaker Diarization**: Uses Whisper for transcription and Pyannote for speaker diarization.
- **Speaker Identification from Video**: Uses OCR to extract the name of the currently speaking person.
- **Final Transcript Generation**: Merges transcription and speaker logs into a structured output.

---

## Installation

### Prerequisites
- Python 3.8+
- `pip` and `virtualenv`
- Selenium WebDriver (Chrome/Firefox)
- FFmpeg
- Whisper & Pyannote (Hugging Face)
- Easy OCR
- OpenCV

### Setup
```bash
# Create a virtual environment
python -m venv env
source env/bin/activate  # On Windows use: env\Scripts\activate

# Install dependencies
pip install -r requirements.txt
