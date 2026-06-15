from datetime import datetime, timedelta, timezone
from typing import Any, Union
from jose import jwt, JWTError
from passlib.context import CryptContext
from pydantic import ValidationError

from app.core.config import get_settings

settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(
    subject: Union[str, Any], expires_delta: timedelta = None
) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        # Default to 8 days expiration if not specified
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES if hasattr(settings, 'ACCESS_TOKEN_EXPIRE_MINUTES') else 11520)
        
    to_encode = {"exp": expire, "sub": str(subject)}
    
    # Use a secure key, defaulting to a static one if not found in settings for safety fallback
    secret = getattr(settings, 'SECRET_KEY', "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7")
    
    encoded_jwt = jwt.encode(to_encode, secret, algorithm=ALGORITHM)
    return encoded_jwt


def verify_access_token(token: str) -> str:
    try:
        secret = getattr(settings, 'SECRET_KEY', "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7")
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise ValueError("Token missing sub payload.")
        return user_id
    except (JWTError, ValidationError) as e:
        raise ValueError(f"Invalid token: {e}")
