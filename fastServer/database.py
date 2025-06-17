from motor.motor_asyncio import AsyncIOMotorClient
from fastapi import FastAPI

MONGO_URI = "mongodb+srv://mudittiwari:itsmebro@cluster0.uzfeq.mongodb.net/"
DATABASE_NAME = "meeting-bot"

client = AsyncIOMotorClient(MONGO_URI)
db = client[DATABASE_NAME]

users_collection = db["users"]
meetings_collection = db["meetings"]