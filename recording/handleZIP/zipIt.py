import os
import zipfile
import smtplib
import logging
import requests
from email.message import EmailMessage

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def create_zip(meeting_id, recording_dir="/shared/recordings", output_dir="/shared/zips"):
    input_path = os.path.join(recording_dir, meeting_id)
    output_zip_path = os.path.join(output_dir, f"{meeting_id}.zip")

    with zipfile.ZipFile(output_zip_path, 'w') as zipf:
        for root, _, files in os.walk(input_path):
            for file in files:
                filepath = os.path.join(root, file)
                arcname = os.path.relpath(filepath, input_path)
                zipf.write(filepath, arcname)

    logger.info(f"Created zip: {output_zip_path}")
    return output_zip_path

def upload_to_gofile(file_path, gofile_token=None):
    server_res = requests.get("https://api.gofile.io/getServer").json()
    server = server_res["data"]["server"]

    with open(file_path, 'rb') as f:
        files = {"file": f}
        data = {"token": gofile_token} if gofile_token else {}
        res = requests.post(f"https://{server}.gofile.io/uploadFile", files=files, data=data).json()

    if res["status"] != "ok":
        raise Exception(f"Upload failed: {res}")

    download_link = res["data"]["downloadPage"]
    logger.info(f"File uploaded to GoFile: {download_link}")
    return download_link

def send_email_with_zip_link(to_email, download_link):
    msg = EmailMessage()
    msg["Subject"] = "🎥 Your Meeting Recording is Ready!"
    msg["From"] = os.getenv("EMAIL_USER")
    msg["To"] = to_email

    msg.set_content(f"""\
Hi,

Your meeting recording is ready! 🎉

🔗 Download it here:
{download_link}

Best regards,
MeetingBot
""")

    with smtplib.SMTP_SSL(os.getenv("SMTP_SERVER"), int(os.getenv("SMTP_PORT"))) as smtp:
        smtp.login(os.getenv("EMAIL_USER"), os.getenv("EMAIL_PASS"))
        smtp.send_message(msg)

    logger.info(f"Email sent to {to_email}")

def handle_post_recording(meeting_id, user_email):
    zip_path = create_zip(meeting_id)
    gofile_link = upload_to_gofile(zip_path, os.getenv("GOFILE_TOKEN"))
    send_email_with_zip_link(user_email, gofile_link)

    # Optional: update database or Redis
    # update_match_status(meeting_id, MatchStatus.successfully_done)
    # update_match_zip_file(meeting_id, gofile_link)
