import os
import zipfile
import smtplib
import json
import requests
import redis
import time
import uuid
import asyncio
from email.message import EmailMessage
from meetbot import start_recording_bot, wait_for_exit

from dotenv import load_dotenv
load_dotenv()

EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("APP_PASS")
SMTP_SERVER = os.getenv("EMAIL_HOST")
SMTP_PORT = int(os.getenv("EMAIL_PORT"))
NOTIFY_EMAIL = os.getenv("NOTIFICATION_EMAIL")
GOFILE_TOKEN = os.getenv("GOFILE_TOKEN")

r = redis.Redis(host='redis', port=6379, db=0)
queue_name = "recording_queue"
queue_name_fastAPI = "fastAPI-queue"

def create_zip(input_file="/shared/meeting.mp4", output_dir="/shared/zips"):
    print("Creating zip file from recording directory...")
    print(f"Recording directory: {input_file}")

    if not os.path.isfile(input_file):
        raise FileNotFoundError(f"{input_file} does not exist!")
    

    unique_id = str(uuid.uuid4())[:8]
    output_zip_path = os.path.join(output_dir, f"recording_{unique_id}.zip")
    os.makedirs(output_dir, exist_ok=True)

    with zipfile.ZipFile(output_zip_path, 'w') as zipf:
        zipf.write(input_file, arcname="meeting.mp4")
    return output_zip_path

def upload_to_gofile(zip_path, token, email, folder_id=None):
    upload_url = "https://upload.gofile.io/uploadFile"
    # Ignore Authorization header as requested
    files = {
        "file": open(zip_path, "rb")
    }
    data = {}
    if folder_id:
        data["folderId"] = folder_id
    data["token"] = token  # Include token in form data as required by GoFile API

    resp = requests.post(upload_url, files=files, data=data).json()

    if resp["status"] == "ok":
        file_info = resp["data"]
        download_link = file_info["downloadPage"]
        print("GoFile upload successful")

        # Send email after successful upload
        send_email_with_zip_link(email, download_link)
        print(f"Email sent to {email}")

        return download_link
    else:
        raise Exception("Upload failed", resp)
    
def send_email_with_zip_link(to_email, download_link):
    msg = EmailMessage()
    msg["Subject"] = "🎥 Your Meeting Recording is Ready!"
    msg["From"] = EMAIL_USER
    msg["To"] = to_email
    msg.set_content(f"""\
Hi,

Your meeting recording is ready.

🔗 Download it here:
{download_link}

Thanks,
Meeting Bot
""")
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as smtp:
        smtp.starttls()
        smtp.login(EMAIL_USER, EMAIL_PASS)
        smtp.send_message(msg)

# while True:
#     _, message = r.blpop(queue_name)
#     print(f"Raw job data: {message}")
    
#     try:
#         data = json.loads(message.decode())
#         print(f"Decoded job: {data}")

#         choice = data.get('choice')
#         url = data.get('meeting_url')
#         email = data.get('email')  # email is still required

#         if not all([choice, url, email]):
#             print("Missing required fields in job")
#             continue

#         print(f"Running job: choice={choice}, url={url}, email={email}")

#         recorder = start_recording_bot(choice, url)
#         print("Recording started...")
#         time.sleep(30)  # Optional buffer for setup
#         wait_for_exit(recorder, choice)
#         print("Recording finished")

#         time.sleep(30)
#         zip_path = create_zip()
#         print(f"Created zip at: {zip_path}")

#         print("Uploading zip to GoFile...")
#         if not GOFILE_TOKEN:
#             raise ValueError("GOFILE_TOKEN is not set in environment variables")
#         if not os.path.exists(zip_path):
#             raise FileNotFoundError(f"Zip file not found: {zip_path}")
#         download_link = upload_to_gofile(zip_path, GOFILE_TOKEN, email)
#         print(f"Uploaded to GoFile: {download_link}")

#     except Exception as e:
#         print(f"Error processing job: {e}")

async def process_job(choice, url, email, meeting_id):
    print(f"[ASYNC] Starting recording: {choice}, {url}")
    recorder = await start_recording_bot(choice, url)

    # recorder = await asyncio.to_thread(start_recording_bot, choice, url)
    
    await wait_for_exit(recorder, choice)
    # await asyncio.to_thread(wait_for_exit, recorder, choice)
    print("[ASYNC] Recording finished")

    zip_path = create_zip()
    # zip_path = await asyncio.to_thread(create_zip)
    print(f"[ASYNC] Zip created: {zip_path}")

    download_link = upload_to_gofile(zip_path, GOFILE_TOKEN, email)
    # await asyncio.to_thread(upload_to_gofile, zip_path, GOFILE_TOKEN, email)

    # await update_meeting_status(meeting_id, MeetingStatus.successfully_done)
    # await update_meeting_zip_file(meeting_id, zip_path )
    payload = {
            "status": "successfully_done",
            "meeting_id": meeting_id,
            "zip_file_link": download_link
        }
    r.rpush(queue_name_fastAPI, json.dumps(payload))


async def main():
    print("Consumer started. Waiting for jobs...")

    while True:
        _, message = r.blpop(queue_name)
        print(f"Raw job data: {message}")

        try:
            data = json.loads(message.decode())
            choice = data.get('choice')
            url = data.get('meeting_url')
            email = data.get('email')
            meeting_id = data.get('meeting_id')

            if not all([choice, url, email, meeting_id]):
                print("Missing required fields in job")
                continue

            # asyncio.create_task(process_job(choice, url, email))  # fire and forget
            await process_job(choice, url, email, meeting_id)

        except Exception as e:
            print(f"Error processing job: {e}")

if __name__ == "__main__":
    asyncio.run(main())

