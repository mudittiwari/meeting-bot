# app/routes/match_routes.py
from fastapi import APIRouter, HTTPException, Depends
from typing import List
from models import Meeting, MeetingInDB
from crud import create_Meeting, get_user_meetings, get_user_by_email
from dependencies import get_current_user

router = APIRouter()

@router.post("/", response_model=MeetingInDB)
async def create_new_meeting(meeting: Meeting):
    user = await get_user_by_email(meeting.user_id)
    if not user:
        raise HTTPException(status_code=400, detail="User does not exist")
    return await create_Meeting(meeting)

@router.get("/currentuser", response_model=List[MeetingInDB])
async def get_matches_for_user(current_user: dict = Depends(get_current_user)):
    return await get_user_meetings(current_user["sub"])