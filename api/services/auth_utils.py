from fastapi import HTTPException, Header
from jose import jwt
import os

JWT_SECRET = os.getenv("JWT_SECRET_KEY", "fallback-secret")

async def get_github_token(authorization: str = Header(...)):
    """
    Expect header: Authorization: Bearer <jwt>
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid auth header")
    token = authorization.split(" ", 1)[1]

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        github_token = payload.get("github_token")
        if not github_token:
            raise HTTPException(status_code=401, detail="No GitHub token in JWT")
        return github_token
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
