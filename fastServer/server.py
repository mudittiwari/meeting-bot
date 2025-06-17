from crud import get_user_by_email, create_Meeting
from dependencies import get_current_user
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
import redis
import json
from routes.user_routes import router as user_router
from routes.meeting_routes import router as meeting_router
from models import ProcessRequest
from dependencies import create_meeting_from_request


app = FastAPI()

r = redis.Redis(host="redis", port=6379, db=0)
queue_name = "recording_queue"

app.include_router(user_router, prefix="/users", tags=["users"])
app.include_router(meeting_router, prefix="/meetings", tags=["meetings"])


@app.get("/")
def read_root():
    return {"message": "Welcome to the Recording Bot API!"}

@app.post("/add-job")
async def add_job(req: ProcessRequest, current_user: dict = Depends(get_current_user)):
    try:
        user = await get_user_by_email(current_user["sub"])
        if not user:
            raise HTTPException(status_code=400, detail="User does not exist")

        created_meeting = await create_Meeting(create_meeting_from_request(req, current_user["sub"]))
        payload = {
            "choice": req.choice,
            "meeting_url": req.meeting_url,
            "email": user.email,
            "meeting_id": created_meeting.id
        }
        r.rpush(queue_name, json.dumps(payload))
        return {"status": "success", "message": "Job added to queue."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))