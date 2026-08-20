from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import (OAuth2PasswordRequestForm, OAuth2PasswordBearer)
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.user import User
from app.schemas.user import UserRegister, UserResponse, UserLogin, TokenResponse
from app.auth.security import(
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token
    )


router = APIRouter(
    prefix="/users",
    tags=["Users"]
)

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="users/login"
)
#==================
# Get Current User
#==================
def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    try:
        payload = decode_access_token(token)

        user_id = payload.get("sub")

        if user_id is None:
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication token"
            )

    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )

    user = (
        db.query(User)
        .filter(User.id == int(user_id))
        .first()
    )

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="User not found"
        )

    return user

# ==================
# User Registration
# ==================

@router.post("/register", response_model=UserResponse)
def register_user(user: UserRegister, db: Session = Depends(get_db)):

    # Check if email already exists
    existing_user = (db.query(User).filter(User.email == user.email).first())

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )

    # Create new user
    new_user = User(
        full_name=user.full_name,
        email=user.email,
        password=hash_password(user.password),
        phone=user.phone,
        city=user.city
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user

#==================
# User Login
#==================

@router.post("/login", response_model=TokenResponse)
def Login_user(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    #find user by email
    existing_user = (db.query(User)
    .filter(User.email == form_data.username)
    .first())

    if not existing_user:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )  

      # Verify password
    if not verify_password(
        form_data.password,
        existing_user.password
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    # Create JWT token
    access_token = create_access_token(
        data={
            "sub": str(existing_user.id),
            "email": existing_user.email,
        }
    )

    return{
        "access_token": access_token,
        "token_type": "bearer"
    }
#==================
# Get Current User Profile
#==================

@router.get("/me", response_model=UserResponse)
def get_my_profile(
    current_user: User = Depends(get_current_user)
):
    return current_user
