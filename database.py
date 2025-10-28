from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

# Get the database URL from environment variable (Heroku sets this)
DATABASE_URL = os.getenv("DATABASE_URL")

# --- FIX: Explicitly specify the psycopg2 driver ---
# If the URL starts with postgres://, replace it with postgresql+psycopg2://
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
# For local SQLite testing, keep the original logic
elif not DATABASE_URL:
     SQLALCHEMY_DATABASE_URL = "sqlite:///./sql_app.db"
# If DATABASE_URL is already set correctly (e.g., includes psycopg2), use it as is
else:
     SQLALCHEMY_DATABASE_URL = DATABASE_URL

# Ensure the URL was actually set
if not SQLALCHEMY_DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set correctly.")

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    # Remove connect_args for PostgreSQL, keep for SQLite
    connect_args={"check_same_thread": False} if "sqlite" in SQLALCHEMY_DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependency to get a DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

