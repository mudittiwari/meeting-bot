# app/routes/match_routes.py
from fastapi import APIRouter, HTTPException, Depends
from typing import List
from models import Meeting, MeetingInDB
from crud import create_Meeting, get_user_meetings, get_user_by_email
from dependencies import get_current_user
from pydantic import BaseModel

router = APIRouter()


class StopRequest(BaseModel):
    meeting_id: str

@router.post("/stop")
async def stop_meeting(data: StopRequest):
    if not data.meeting_id:
        raise HTTPException(status_code=400, detail="Meeting ID is required.")

    stop_file_path = f"/shared/STOP_{data.meeting_id}.txt"

    try:
        open(stop_file_path, "w").close()
        return {"message": f"Stop signal file created: STOP_{data.meeting_id}.txt"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create stop file: {str(e)}")


@router.post("/", response_model=MeetingInDB)
async def create_new_meeting(meeting: Meeting):
    user = await get_user_by_email(meeting.user_id)
    if not user:
        raise HTTPException(status_code=400, detail="User does not exist")
    return await create_Meeting(meeting)

@router.get("/currentuser", response_model=List[MeetingInDB])
async def get_matches_for_user(current_user: dict = Depends(get_current_user)):
    return await get_user_meetings(current_user["sub"])

