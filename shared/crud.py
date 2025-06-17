from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorClient
from typing import List
from models import User, Meeting, MeetingInDB, UserCreate, MeetingStatus
from database import db
from bson import ObjectId
from typing import Optional
from database import users_collection
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def str_id(id: ObjectId) -> str:
    return str(id)


# ✅testing done
async def get_user_by_email(email: str) -> Optional[User]:
    user = await users_collection.find_one({"email": email})
    # print(user)
    if user:
        user["_id"] = str(user["_id"])
        return User(**user)
    return None


# ✅testing done
async def create_user(user: UserCreate) -> User:
    try:
        hashed_password = pwd_context.hash(user.password)
        user_data = user.dict(exclude_unset=True, exclude={"id"})
        user_data["password"] = hashed_password
        result = await users_collection.insert_one(user_data)
        created_user = await users_collection.find_one({"_id": result.inserted_id})
        created_user["_id"] = str(created_user["_id"])
        return User(**created_user)
    
    except Exception as e:
        print(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create user")


# ✅testing done
async def update_user_with_password(user_id: str, update_data: dict) -> User:
    update_data = update_data.dict(exclude_unset=True)
    try:
        if "password" in update_data:
            update_data["password"] = pwd_context.hash(update_data["password"])

        result = await users_collection.update_one(
            {"_id": ObjectId(user_id)}, {"$set": update_data}
        )
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="User not found or no changes")

        updated_user = await users_collection.find_one({"_id": ObjectId(user_id)})
        updated_user["_id"] = str(updated_user["_id"])
        return User(**updated_user)
    except Exception as e:
        print(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Failed to update user with password")



# ✅testing done
async def create_Meeting(meeting: Meeting) -> MeetingInDB:
    match_dict = meeting.dict()
    result = await db.matches.insert_one(match_dict)
    created_match = await db.matches.find_one({"_id": result.inserted_id})
    created_match["id"] = str(created_match["_id"])
    user = await db.users.find_one({"email": meeting.user_id})
    if user:
        await db.users.update_one(
            {"email": meeting.user_id},
            {"$push": {"matches": str_id(created_match["_id"])}}
        )
    return MeetingInDB(**created_match)


# ✅testing done
async def update_meeting_status(meeting_id: str, meeting_status: MeetingStatus) -> str:
    created_meeting = await db.meetings.find_one({"_id": ObjectId(meeting_id)})
    if not created_meeting:
        return "Meeting not found"
    await db.meetings.update_one(
        {"_id": ObjectId(meeting_id)},
        {"$set": {"status": meeting_status}}
    )
    print("Match status updated to " + meeting_status)
    return "Match status updated to " + meeting_status

# ✅testing done
async def update_meeting_zip_file(meeting_id: str, zip_file: str) -> str:
    created_meeting = await db.meetings.find_one({"_id": ObjectId(meeting_id)})
    if not created_meeting:
        return "Meeting not found"
    await db.meetings.update_one(
        {"_id": ObjectId(meeting_id)},
        {"$set": {"zip_file_link": zip_file}}
    )
    print("Meeting status updated to " + zip_file)
    return "Meeting status updated to " + zip_file


# ✅testing done
async def get_user_meetings(user_id: str) -> List[MeetingInDB]:
    meetings_cursor = db.meetings.find({"user_id": user_id})
    meetings = await meetings_cursor.to_list(length=100)
    for meeting in meetings:
        meeting["id"] = str(meeting["_id"])
    return [MeetingInDB(**match) for match in meetings]

async def link_meeting_to_user(user_id: str, meeting_id: str) -> User:
    result = await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$push": {"matches": meeting_id}}
    )
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    return User(**user)


# ✅testing done
async def get_all_users() -> List[User]:
    users_cursor = db.users.find()
    users = await users_cursor.to_list(length=100)
    for user in users:
        user["_id"] = str(user["_id"])
    return [User(**user) for user in users]