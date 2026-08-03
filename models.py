from sqlalchemy import Column, Integer, String, ForeignKey, JSON, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=True)
    provider = Column(String, nullable=False, default="email")
    github_access_token = Column(String, nullable=True) # Encrypted
    
    # Relationship to scan reports
    scan_reports = relationship("ScanReport", back_populates="user")

class ScanReport(Base):
    __tablename__ = "scan_reports"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    repo_name = Column(String, index=True)
    report_data = Column(JSON) # Store the full JSON report
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="scan_reports")

class ScanTask(Base):
    """Maps a Celery task_id to the user who started it, so scan status can
    be scoped to its owner instead of being readable by anyone who knows/
    guesses the task_id."""
    __tablename__ = "scan_tasks"
    task_id = Column(String, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

