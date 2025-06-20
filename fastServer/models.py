from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
from bson import ObjectId
from datetime import datetime
from enum import Enum


class ProcessRequest(BaseModel):
    meeting_url: str
    choice: str
    meeting_slug: str


class MeetingStatus(str, Enum):
    in_queue = "in_queue"
    successfully_done = "successfully_done"
    failed = "failed"


# ------------------ USER MODELS ------------------ #

class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    state: Optional[str] = None
    password: Optional[str] = None


class UserBase(BaseModel):
    name: str
    email: EmailStr
    phone: str
    city: str
    country: str
    state: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class UserCreate(UserBase):
    password: str


class User(UserBase):
    id: str = Field(alias="_id")
    matches: List[str] = []

    class Config:
        orm_mode = True
        allow_population_by_field_name = True
        json_encoders = {
            ObjectId: str
        }


# ------------------ MEETING MODELS ------------------ #

class Meeting(BaseModel):
    meeting_url: str
    meeting_slug: str
    zip_file_link: str
    user_id: str
    status: MeetingStatus
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class MeetingInDB(Meeting):
    id: str

    class Config:
        orm_mode = True
