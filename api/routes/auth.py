from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from api.services.github_auth import get_github_login_url, exchange_code_for_token, get_github_user
from jose import jwt
import os
from datetime import datetime, timedelta, timezone

router = APIRouter()
JWT_SECRET = os.getenv("JWT_SECRET_KEY", "fallback-secret")

def create_jwt(user_data: dict) -> str:
    payload = {
        "sub": str(user_data["id"]),
        "username": user_data["login"],
        "avatar": user_data.get("avatar_url"),
        "github_token": user_data.get("github_token"),
        "exp": datetime.now(timezone.utc) + timedelta(hours=8),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

@router.get("/auth/github/login")
async def github_login():
    return RedirectResponse(get_github_login_url())

@router.get("/auth/github/callback")
async def github_callback(code: str):
    if not code:
        raise HTTPException(status_code=400, detail="No code provided")
    
    access_token = await exchange_code_for_token(code)
    if not access_token:
        raise HTTPException(status_code=401, detail="Failed to get access token")
    
    user = await get_github_user(access_token)
    user["github_token"] = access_token  # store for later API calls
    
    jwt_token = create_jwt(user)
    
    # Redirect to frontend with token
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3001")
    return RedirectResponse(f"{frontend_url}/?token={jwt_token}")

@router.get("/auth/me")
async def get_current_user(token: str):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return {"username": payload["username"], "avatar": payload["avatar"]}
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
