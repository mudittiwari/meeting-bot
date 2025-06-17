from fastapi import APIRouter, HTTPException, Depends, Path, Body
from typing import List
from models import UserCreate, User, UserUpdate
from crud import create_user, get_user_by_email, get_all_users, update_user_with_password
from fastapi.security import OAuth2PasswordRequestForm
from auth import create_access_token
from passlib.hash import bcrypt
from database import users_collection
from dependencies import get_current_user

router = APIRouter()

# ✅testing done
@router.post("/", response_model=User)
async def create_new_user(user: UserCreate):
    existing_user = await get_user_by_email(user.email)
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    return await create_user(user)

# ✅testing done
@router.put("/{user_id}", response_model=User)
async def update_user(user_id: str = Path(..., description="MongoDB ObjectId of the user"),
    user_update: UserUpdate = Body(...), current_user: dict = Depends(get_current_user)):
    # print(current_user)
    # print(user_id)
    # print(user_update)
    existing_user = await get_user_by_email(current_user["sub"])

    # print(existing_user)
    # print(str(existing_user.id))
    if existing_user and str(existing_user.id) == user_id:
        return await update_user_with_password(user_id, user_update)
    raise HTTPException(status_code=400, detail="Email not registered")

# ✅testing done
@router.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await users_collection.find_one({"email": form_data.username})
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    if not bcrypt.verify(form_data.password, user["password"]):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    access_token = create_access_token(data={"sub": user["email"]})
    user["_id"] = str(user["_id"])
    user_data = User(**user)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user_data
    }

# ✅testing done
@router.get("/", response_model=List[User])
async def get_users():
    return await get_all_users()