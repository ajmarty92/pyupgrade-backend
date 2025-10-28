import os
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from celery.result import AsyncResult
import json

from database import get_db, engine
import models, schemas, security, auth
from celery_worker import celery_app, run_repository_scan

models.Base.metadata.create_all(bind=engine)
app = FastAPI()

if os.getenv("PRODUCTION"):
    origins = ["https://pyupgrade.com"] 
else:
    origins = ["http://localhost", "http://localhost:3000", "http://127.0.0.1", "http://127.0.0.1:8000", "null"]

app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

app.include_router(auth.router)

@app.get("/api/me", response_model=schemas.User)
async def read_users_me(current_user: models.User = Depends(auth.get_current_active_user)):
    return current_user

@app.get("/api/repositories")
async def get_repositories(current_user: models.User = Depends(auth.get_current_active_user)):
    return await auth.get_user_repositories(current_user)

@app.post("/api/scan", status_code=202)
async def start_scan(repo_data: schemas.RepoScanRequest, current_user: models.User = Depends(auth.get_current_active_user)):
    if not current_user.github_access_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="GitHub account not linked.")
    try:
        decrypted_token = security.decrypt_data(current_user.github_access_token)
        await auth.verify_repo_permission(repo_data.repo_name, decrypted_token)
        task = run_repository_scan.delay(repo_data.repo_name, decrypted_token, current_user.id)
        return {"task_id": task.id}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An unexpected error occurred: {str(e)}")

@app.get("/api/scan/status/{task_id}")
async def get_scan_status(task_id: str):
    task_result = AsyncResult(task_id, app=celery_app)
    if task_result.failed():
        return {"status": "FAILURE", "detail": str(task_result.result)}
    if task_result.ready():
        return {"status": "SUCCESS", "result": task_result.get()}
    return {"status": task_result.status}

@app.post("/api/generate-fix")
async def generate_fix(fix_request: schemas.GenerateFixRequest, current_user: models.User = Depends(auth.get_current_active_user)):
    return await auth.generate_ai_fix(fix_request)

@app.post("/api/public/modernize-snippet")
async def modernize_snippet(snippet_request: schemas.ModernizeSnippetRequest):
    return await auth.modernize_public_snippet(snippet_request)

# --- NEW AI FEATURE ENDPOINTS ---

@app.post("/api/create-pr", response_model=schemas.PullRequestResponse)
async def create_pr(pr_request: schemas.CreatePRRequest, current_user: models.User = Depends(auth.get_current_active_user)):
    """Creates an automated pull request with the AI-suggested code fix."""
    if not current_user.github_access_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="GitHub account not linked.")
    try:
        decrypted_token = security.decrypt_data(current_user.github_access_token)
        pr_url = await auth.create_github_pr(pr_request, decrypted_token)
        return {"pr_url": pr_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate-tests", response_model=schemas.GenerateTestsResponse)
async def generate_tests(test_request: schemas.GenerateTestsRequest, current_user: models.User = Depends(auth.get_current_active_user)):
    """Generates unit tests for a given code fix."""
    try:
        test_code = await auth.generate_ai_unit_tests(test_request)
        return {"test_code": test_code}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/strategic-summary", response_model=schemas.StrategicSummaryResponse)
async def get_strategic_summary(current_user: models.User = Depends(auth.get_current_active_user), db: Session = Depends(get_db)):
    """Generates a high-level strategic summary of all scanned repositories."""
    try:
        summary = await auth.generate_ai_strategic_summary(current_user, db)
        return {"summary": summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

