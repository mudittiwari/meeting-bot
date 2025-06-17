import asyncio
import json
from crud import update_meeting_status
import redis
import logging
from models import MeetingStatus


r = redis.Redis(host='redis', port=6379, db=0)
queue_name = "fastAPI-queue"

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logging.getLogger("pymongo").setLevel(logging.ERROR)

logger = logging.getLogger(__name__)


async def update_meeting_status_consumer(meeting_id, status, zip_file_link):
    if status == "in_queue":
        await update_meeting_status(meeting_id, MeetingStatus.in_queue, zip_file_link)
    elif status == "successfully_done":
        await update_meeting_status(meeting_id, MeetingStatus.successfully_done,  zip_file_link)
    elif status == "failed":
        await update_meeting_status(meeting_id, MeetingStatus.failed,  zip_file_link)



async def main():
    logger.info("FastAPI consumer started. Waiting for jobs...")
    while True:
        _, message = r.blpop(queue_name)
        print(f"Raw job data: {message}")

        try:
            data = json.loads(message.decode())
            meeting_id = data.get('meeting_id')
            status = data.get('status')
            zip_file_link = data.get('zip_file_link')

            if not all([meeting_id, status, zip_file_link]):
                print("Missing required fields in job")
                continue
            # asyncio.create_task(process_job(choice, url, email))  # fire and forget
            await update_meeting_status_consumer(meeting_id, status, zip_file_link)

        except Exception as e:
            print(f"Error processing job: {e}")

if __name__ == "__main__":
    asyncio.run(main())