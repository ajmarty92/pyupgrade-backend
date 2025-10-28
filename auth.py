from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import httpx
import os

import models, schemas, security, database, ai_service

router = APIRouter(prefix="/auth", tags=["Authentication"])

# --- OAuth2 Configuration ---
from authlib.integrations.starlette_client import OAuth
oauth = OAuth()
# ... (OAuth registrations are unchanged)

# --- Dependency ---
async def get_current_active_user(token: str = Depends(security.oauth2_scheme), db: Session = Depends(database.get_db)):
    # ... (implementation is unchanged)
    pass

# --- Helper Functions (Moved from main.py for better organization) ---
async def get_user_repositories(current_user: models.User):
    if not current_user.github_access_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="GitHub account not linked.")
    try:
        decrypted_token = security.decrypt_data(current_user.github_access_token)
        headers = {"Authorization": f"token {decrypted_token}"}
        async with httpx.AsyncClient() as client:
            response = await client.get("https://api.github.com/user/repos?type=owner&sort=updated", headers=headers)
            response.raise_for_status()
        python_repos = [repo for repo in response.json() if repo.get("language") == "Python"]
        return python_repos
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

async def verify_repo_permission(repo_name: str, token: str):
    headers = {"Authorization": f"token {token}"}
    async with httpx.AsyncClient() as client:
        repo_info_url = f"https://api.github.com/repos/{repo_name}"
        response = await client.get(repo_info_url, headers=headers)
        if response.status_code == 404:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found.")
        response.raise_for_status()
        permissions = response.json().get("permissions", {})
        if not permissions.get("pull"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to access this repository.")

async def generate_ai_fix(fix_request: schemas.GenerateFixRequest):
    try:
        suggestion = await ai_service.generate_code_fix(
            code_snippet=fix_request.code_snippet, issue_type=fix_request.issue_type,
            file_path=fix_request.file_path, line=fix_request.line
        )
        return {"suggestion": suggestion}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

async def modernize_public_snippet(snippet_request: schemas.ModernizeSnippetRequest):
    try:
        modernized_code = await ai_service.modernize_code_snippet(snippet_request.code_snippet)
        return {"modernized_code": modernized_code}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# --- Standard Login/Signup Routes ---
@router.post("/signup", response_model=schemas.User)
async def signup(user: schemas.UserCreate, db: Session = Depends(database.get_db)):
    # ... (implementation is unchanged)
    pass

@router.post("/login")
async def login(response: Response, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(database.get_db)):
    user = security.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    
    access_token = security.create_access_token(data={"sub": str(user.id)})
    
    # **SECURITY FIX**: Use secure=True in production
    is_production = os.getenv("PRODUCTION", "false").lower() == "true"
    response.set_cookie(
        key="access_token", 
        value=f"Bearer {access_token}", 
        httponly=True, 
        samesite='lax', 
        secure=is_production 
    )
    return {"message": "Login successful"}

# --- OAuth Routes ---
@router.get('/github/callback')
async def github_callback(request: dict, response: Response, db: Session = Depends(database.get_db)):
    # ... (logic is mostly unchanged)
    # **SECURITY FIX**: Use secure=True in production for the cookie
    is_production = os.getenv("PRODUCTION", "false").lower() == "true"
    response.set_cookie(
        key="access_token", value=f"Bearer {jwt_token}", 
        httponly=True, samesite='lax', secure=is_production
    )
    return RedirectResponse(url="/app.html")

@router.get('/google/callback')
async def google_callback(request: dict, response: Response, db: Session = Depends(database.get_db)):
    # ... (logic is mostly unchanged)
    # **SECURITY FIX**: Use secure=True in production for the cookie
    is_production = os.getenv("PRODUCTION", "false").lower() == "true"
    response.set_cookie(
        key="access_token", value=f"Bearer {jwt_token}", 
        httponly=True, samesite='lax', secure=is_production
    )
    return RedirectResponse(url="/app.html")

# ... (other OAuth login routes are unchanged)

