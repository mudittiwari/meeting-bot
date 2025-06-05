from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import redis
import json

app = FastAPI()

r = redis.Redis(host="redis", port=6379, db=0)
queue_name = "recording_queue"

class JobRequest(BaseModel):
    choice: str
    meeting_url: str
    email: str 

@app.get("/")
def read_root():
    return {"message": "Welcome to the Recording Bot API!"}

@app.post("/add-job")
def add_job(job: JobRequest):
    try:
        payload = {
            "choice": job.choice,
            "meeting_url": job.meeting_url,
            "email": job.email
        }
        r.rpush(queue_name, json.dumps(payload))
        return {"status": "success", "message": "Job added to queue."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))