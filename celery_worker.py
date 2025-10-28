from celery import Celery
import os
from dotenv import load_dotenv

import scanner
from database import SessionLocal

load_dotenv()

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery('tasks', broker=redis_url, backend=redis_url)
celery_app.conf.update(task_track_started=True)

@celery_app.task(name='run_repository_scan')
def run_repository_scan(repo_name: str, github_token: str, user_id: int):
    """
    Celery task that runs the repository analysis and saves the result.
    """
    # Run the synchronous scanner function
    report = scanner.analyze_repository(repo_name, github_token)
    
    # Save the report to the database
    db = SessionLocal()
    try:
        scanner.save_scan_report(db, user_id, repo_name, report)
    finally:
        db.close()
        
    return report

