from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import (OAuth2PasswordRequestForm, OAuth2PasswordBearer)
from sqlalchemy.orm import Session
from sqlalchemy import func
from jose import jwt, JWTError

from app.database.database import get_db
from app.models.user import User
from app.schemas.user import UserRegister, UserResponse, UserLogin, TokenResponse, PreferenceUpdate, PreferenceResponse, FCMTokenUpdate,ProfileUpdate,ForgotPasswordRequest, ResetPasswordRequest
from app.auth.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    create_reset_token,
    SECRET_KEY, 
    ALGORITHM
    )
from app.models.preference import UserPreference
from app.models.incident import Incident

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
# Get Current Admin
# ==================

def get_current_admin(
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )

    return current_user

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


@router.post("/preferences", response_model=PreferenceResponse)
def set_preferences(
    payload: PreferenceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    existing = db.query(UserPreference).filter(
        UserPreference.user_id == current_user.id
    ).first()

    if existing:
        existing.preferred_areas = payload.preferred_areas
        existing.preferred_categories = payload.preferred_categories
    else:
        existing = UserPreference(
            user_id=current_user.id,
            preferred_areas=payload.preferred_areas,
            preferred_categories=payload.preferred_categories
        )
        db.add(existing)

    db.commit()
    db.refresh(existing)

    return existing

#===================
# Get User Preferences
#===================
@router.get("/preferences", response_model=PreferenceResponse)
def get_preferences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    prefs = db.query(UserPreference).filter(
        UserPreference.user_id == current_user.id
    ).first()

    if not prefs:
        return PreferenceResponse(preferred_areas=[], preferred_categories=[])

    return prefs

#===================
# Update FCM Token
#===================

@router.post("/fcm-token")
def update_fcm_token(
    payload: FCMTokenUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    current_user.fcm_token = payload.fcm_token
    db.commit()
    return {"message": "FCM token updated successfully"}

#===================
# Update User Profile
#===================
from app.schemas.user import ProfileUpdate

@router.patch("/me", response_model=UserResponse)
def update_profile(
    payload: ProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if payload.full_name is not None:
        current_user.full_name = payload.full_name
    if payload.phone is not None:
        current_user.phone = payload.phone
    if payload.city is not None:
        current_user.city = payload.city

    db.commit()
    db.refresh(current_user)
    return current_user

#====================
# Get User's Incidents
#====================
@router.get("/me/stats")
def get_my_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    total = db.query(func.count(Incident.id)).filter(Incident.user_id == current_user.id).scalar()
    verified = db.query(func.count(Incident.id)).filter(
        Incident.user_id == current_user.id, Incident.status == "Verified"
    ).scalar()
    resolved = db.query(func.count(Incident.id)).filter(
        Incident.user_id == current_user.id, Incident.status == "Resolved"
    ).scalar()

    return {
        "total_reports": total,
        "verified_reports": verified,
        "resolved_reports": resolved
    }

#====================
# Forgot Password
#====================
@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        # Security: yeh bata nahi rahe ke email exist karta hai ya nahi
        return {"message": "If this email exists, a reset token has been generated"}

    reset_token = create_reset_token({"sub": str(user.id)})
    # TODO: Production mein yeh token email se bhejna hai, response mein nahi
    return {"message": "Reset token generated", "reset_token": reset_token}

#====================
# Reset Password
#====================
@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    try:
        decoded = jwt.decode(payload.token, SECRET_KEY, algorithms=[ALGORITHM])
        if decoded.get("type") != "reset":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user_id = decoded.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired reset token")

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.password = hash_password(payload.new_password)
    db.commit()
    return {"message": "Password reset successful"}