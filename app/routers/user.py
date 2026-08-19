from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.user import User
from app.schemas.user import UserRegister, UserResponse, UserLogin, TokenResponse
from app.auth.security import(
    hash_password,
    verify_password,
    create_access_token
    )

router = APIRouter(
    prefix="/users",
    tags=["Users"]
)

@router.post("/register", response_model=UserResponse)
def register_user(user: UserRegister, db: Session = Depends(get_db)):

    # Check if email already exists
    existing_user = db.query(User).filter(User.email == User.email).first()

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
@router.post("/login", response_model=TokenResponse)
def Login_user(
    USer: UserLogin,
    db: Session = Depends(get_db)
):
    #find user by email
    existing_user = (db.query(User)
    .filter(User.email == User.email)
    .first())

    if not existing_user:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )  

      # Verify password
    if not verify_password(
        USer.password,
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

