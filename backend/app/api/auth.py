from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.security import verify_password, get_password_hash, create_access_token

router = APIRouter(prefix="/auth", tags=["Authentication"])
settings = get_settings()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/token")

# Mock database for demonstration
MOCK_USER_DB = {
    "admin": {
        "username": "admin",
        "email": "admin@edgebrain.local",
        "full_name": "EdgeBrain Administrator",
        # Hashed "secret"
        "hashed_password": get_password_hash("secret"),
        "disabled": False,
        "role": "admin"
    }
}

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: str | None = None

class User(BaseModel):
    username: str
    email: str | None = None
    full_name: str | None = None
    disabled: bool | None = None
    role: str

class UserInDB(User):
    hashed_password: str

def get_user(username: str):
    if username in MOCK_USER_DB:
        user_dict = MOCK_USER_DB[username]
        return UserInDB(**user_dict)
    return None

async def get_current_user(token: str = Depends(oauth2_scheme)):
    # Note: verify_access_token is defined in core.security
    from app.core.security import verify_access_token
    try:
        username = verify_access_token(token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = get_user(username)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = get_user(form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES if hasattr(settings, 'ACCESS_TOKEN_EXPIRE_MINUTES') else 11520)
    access_token = create_access_token(
        subject=user.username, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/users/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user
