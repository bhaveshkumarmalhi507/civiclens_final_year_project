from fastapi import FastAPI
from sqlalchemy import text
from app.database.database import engine
from app.database.database import Base, engine
from app.models import User
from app.routers.user import router as user_router
from fastapi.security import OAuth2PasswordBearer


oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="users/login"
)

app = FastAPI(
    title="CivicLens API",
    description="AI-Powered Citizen Journalism & Smart City Alerts",
    version="1.0.0"
)

# Create tables
Base.metadata.create_all(bind=engine)

app.include_router(user_router)

@app.get("/")
def home():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return {
            "status": "success",
            "database": "Connected",
            "message": "Welcome to CivicLens Backend 🚀"
        }

    except Exception as e:
        return {
            "status": "error",
            "database": str(e)
        }