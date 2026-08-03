import os
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session
from celery.result import AsyncResult
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import project modules (avoid importing specific items initially if possible)
import database 
import models 
import schemas # Import the whole module first
import security 
import auth # Import the router itself
from celery_worker import celery_app, run_repository_scan

# --- App Initialization ---
models.Base.metadata.create_all(bind=database.engine)
app = FastAPI()

# --- Security & Middleware ---
if os.getenv("PRODUCTION"):
    # The marketing site (public demo widget, no cookies) and the actual app
    # deployment (cookie-authenticated) are two different origins.
    origins = list({"https://pyupgrade.com", security.FRONTEND_URL})
else:
    origins = [
        "http://localhost", "http://localhost:3000",
        "http://127.0.0.1", "http://127.0.0.1:8000"
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Required by authlib to persist OAuth state/nonce between the redirect to
# GitHub/Google and the callback request.
is_production = os.getenv("PRODUCTION", "false").lower() == "true"
app.add_middleware(
    SessionMiddleware,
    secret_key=security.SESSION_SECRET_KEY,
    same_site="lax",
    https_only=is_production,
)

# --- Routers ---
# Include the auth router AFTER the app and middleware are set up
app.include_router(auth.router)

# --- API Endpoints ---
# Use the imported module 'schemas' to reference the User class
@app.get("/api/me", response_model=schemas.User) 
async def read_users_me(current_user: models.User = Depends(auth.get_current_active_user)):
    return current_user

@app.get("/api/repositories")
async def get_repositories(current_user: models.User = Depends(auth.get_current_active_user)):
    return await auth.get_user_repositories(current_user) # Delegate to auth module

@app.post("/api/scan", status_code=202)
async def start_scan(repo_data: schemas.RepoScanRequest, current_user: models.User = Depends(auth.get_current_active_user), db: Session = Depends(database.get_db)):
    if not current_user.github_access_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="GitHub account not linked.")
    try:
        decrypted_token = security.decrypt_data(current_user.github_access_token)
        await auth.verify_repo_permission(repo_data.repo_name, decrypted_token) # Delegate verification
        # Pass necessary primitive types to Celery task
        task = run_repository_scan.delay(repo_data.repo_name, decrypted_token, current_user.id)
        db.add(models.ScanTask(task_id=task.id, user_id=current_user.id))
        db.commit()
        return {"task_id": task.id}
    except HTTPException as e:
        raise e
    except Exception as e:
        # Log the full error for debugging
        logger.error("Error starting scan: %s", e, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred while starting the scan. Please try again later.")

@app.get("/api/scan/status/{task_id}")
async def get_scan_status(task_id: str, current_user: models.User = Depends(auth.get_current_active_user), db: Session = Depends(database.get_db)):
    scan_task = db.query(models.ScanTask).filter(models.ScanTask.task_id == task_id).first()
    if not scan_task or scan_task.user_id != current_user.id:
        # 404 rather than 403 so guessing task_ids can't even confirm one exists.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan task not found.")

    task_result = AsyncResult(task_id, app=celery_app)
    if task_result.failed():
        # Log the actual error from the worker
        logger.error(f"ERROR IN SCAN TASK {task_id}: {task_result.result}")
        return {"status": "FAILURE", "detail": "Scan failed. Check server logs."} # Avoid sending detailed errors to client
    if task_result.ready():
        return {"status": "SUCCESS", "result": task_result.get()}
    return {"status": task_result.status}

@app.post("/api/generate-fix")
async def generate_fix(fix_request: schemas.GenerateFixRequest, current_user: models.User = Depends(auth.get_current_active_user)):
    return await auth.generate_ai_fix(fix_request) # Delegate

@app.post("/api/public/modernize-snippet")
async def modernize_snippet(snippet_request: schemas.ModernizeSnippetRequest):
    return await auth.modernize_public_snippet(snippet_request) # Delegate

@app.post("/api/create-pr", response_model=schemas.PullRequestResponse)
async def create_pr(pr_request: schemas.CreatePRRequest, current_user: models.User = Depends(auth.get_current_active_user)):
    return await auth.handle_create_pr(pr_request, current_user) # Delegate

@app.post("/api/generate-tests", response_model=schemas.GenerateTestsResponse)
async def generate_tests(test_request: schemas.GenerateTestsRequest, current_user: models.User = Depends(auth.get_current_active_user)):
    return await auth.handle_generate_tests(test_request) # Delegate

@app.get("/api/strategic-summary", response_model=schemas.StrategicSummaryResponse)
async def get_strategic_summary(current_user: models.User = Depends(auth.get_current_active_user), db: Session = Depends(database.get_db)):
     return await auth.handle_strategic_summary(current_user, db) # Delegate

