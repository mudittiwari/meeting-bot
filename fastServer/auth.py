from datetime import datetime, timedelta
from jose import JWTError, jwt

SECRET_KEY = "12345678"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


# ✅testing done
def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    # expire = datetime.utcnow() + (expires_delta if expires_delta else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    # to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt



# ✅testing done
def verify_access_token(token: str):
    try:
        # print("Token received:",token)
        # print("SECRET_KEY:",SECRET_KEY)
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        # print("Payload:", payload)
        return payload
    except JWTError as e:
        print("JWT Error:", e)
        return None