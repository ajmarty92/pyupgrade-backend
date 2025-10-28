from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import httpx
import os
import traceback # For logging detailed errors

# Import modules instead of specific items where feasible
import models 
import schemas # Import the whole module
import security 
import database 
import ai_service 

# Import specific tools needed
from authlib.integrations.starlette_client import OAuth
from fastapi.responses import RedirectResponse
from github import Github, GithubException # PyGithub for creating PRs

router = APIRouter(prefix="/auth", tags=["Authentication"])

# --- OAuth2 Configuration ---
oauth = OAuth()
oauth.register( name='github', # ... config ...
    client_id=security.GITHUB_CLIENT_ID, client_secret=security.GITHUB_CLIENT_SECRET,
    access_token_url='https://github.com/login/oauth/access_token', authorize_url='https://github.com/login/oauth/authorize',
    api_base_url='https://api.github.com/', client_kwargs={'scope': 'user:email repo'},
)
oauth.register( name='google', # ... config ...
    client_id=security.GOOGLE_CLIENT_ID, client_secret=security.GOOGLE_CLIENT_SECRET,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'},
)

# --- Dependency ---
async def get_current_active_user(token: str = Depends(security.oauth2_scheme), db: Session = Depends(database.get_db)) -> models.User:
    """Dependency to get the current authenticated user from a token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = security.decode_access_token(token)
    if payload is None: raise credentials_exception
    user_id: str = payload.get("sub")
    if user_id is None: raise credentials_exception
    try:
        user = db.query(models.User).filter(models.User.id == int(user_id)).first()
    except ValueError: # Handle case where sub is not an int
         raise credentials_exception
    if user is None: raise credentials_exception
    return user

# --- Helper Functions ---
async def get_user_repositories(current_user: models.User):
    # ... (implementation is unchanged)
    pass

async def verify_repo_permission(repo_name: str, token: str):
    # ... (implementation is unchanged)
    pass

async def generate_ai_fix(fix_request: schemas.GenerateFixRequest):
    # ... (implementation is unchanged)
    pass

async def modernize_public_snippet(snippet_request: schemas.ModernizeSnippetRequest):
     # ... (implementation is unchanged)
     pass

# --- Standard Login/Signup Routes ---
@router.post("/signup", response_model=schemas.User) # Use schemas.User here
async def signup(user_data: schemas.UserCreate, db: Session = Depends(database.get_db)): # Use UserCreate for input
    db_user = db.query(models.User).filter(models.User.email == user_data.email).first()
    if db_user: raise HTTPException(status_code=400, detail="Email already registered")
    hashed_password = security.get_password_hash(user_data.password)
    new_user = models.User(email=user_data.email, hashed_password=hashed_password, provider='email')
    db.add(new_user); db.commit(); db.refresh(new_user)
    return new_user

@router.post("/login")
async def login(response: Response, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(database.get_db)):
    user = security.authenticate_user(db, form_data.username, form_data.password)
    if not user: raise HTTPException(status_code=401, detail="Incorrect email or password")
    access_token = security.create_access_token(data={"sub": str(user.id)})
    is_production = os.getenv("PRODUCTION", "false").lower() == "true"
    response.set_cookie(key="access_token", value=f"Bearer {access_token}", httponly=True, samesite='lax', secure=is_production)
    return {"message": "Login successful"}

# --- OAuth Routes ---
# ... (github_login, github_callback, google_login, google_callback are unchanged)

# --- NEW AI FEATURE HANDLERS ---

async def handle_create_pr(pr_request: schemas.CreatePRRequest, current_user: models.User) -> dict:
    """Handles logic for creating a GitHub PR."""
    if not current_user.github_access_token:
        raise HTTPException(status_code=403, detail="GitHub account not linked or token invalid.")
    
    try:
        token = security.decrypt_data(current_user.github_access_token)
        g = Github(token)
        repo = g.get_repo(pr_request.repo_name)
        
        # Generate branch name, title, body using AI
        branch_name = f"pyupgrade-fix/{pr_request.file_path.replace('/', '-')}-{os.urandom(3).hex()}"
        ai_pr_details = await ai_service.generate_pr_description(
            old_code=pr_request.old_code,
            new_code=pr_request.new_code,
            issue_type=pr_request.issue_type,
            file_path=pr_request.file_path
        )
        pr_title = ai_pr_details.get("title", f"PyUpgrade Fix: {pr_request.issue_type}")
        pr_body = ai_pr_details.get("body", f"Automated fix for {pr_request.issue_type} in `{pr_request.file_path}` generated by PyUpgrade.")

        # Get default branch and create new branch from it
        default_branch = repo.get_branch(repo.default_branch)
        repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=default_branch.commit.sha)

        # Get the file, update content, and commit
        contents = repo.get_contents(pr_request.file_path, ref=branch_name)
        repo.update_file(
            path=contents.path,
            message=pr_title, # Use PR title as commit message
            content=pr_request.new_code,
            sha=contents.sha,
            branch=branch_name
        )

        # Create the pull request
        pr = repo.create_pull(
            title=pr_title,
            body=pr_body,
            head=branch_name,
            base=repo.default_branch
        )
        
        return {"pr_url": pr.html_url}

    except GithubException as e:
        print(f"GitHub API Error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"GitHub Error: {e.data.get('message', 'Could not create PR. Check repository permissions.')}")
    except Exception as e:
        print(f"Error creating PR: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


async def handle_generate_tests(test_request: schemas.GenerateTestsRequest) -> dict:
    """Handles logic for generating unit tests."""
    try:
        test_code = await ai_service.generate_unit_tests(
            old_code=test_request.old_code,
            new_code=test_request.new_code
        )
        return {"test_code": test_code}
    except Exception as e:
        print(f"Error generating tests: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to generate tests: {str(e)}")


async def handle_strategic_summary(current_user: models.User, db: Session) -> dict:
    """Handles logic for generating the strategic summary."""
    try:
        # Fetch recent scan reports for the user
        recent_reports = db.query(models.ScanReport)\
                           .filter(models.ScanReport.user_id == current_user.id)\
                           .order_by(models.ScanReport.created_at.desc())\
                           .limit(20)\
                           .all() # Limit for performance

        if not recent_reports:
            return {"summary": "No scan reports found. Run some scans first!"}

        # Extract relevant data for the AI prompt
        report_summaries = [
            {
                "repoName": r.repo_name,
                "pythonVersion": r.report_data.get("pythonVersion", "N/A"),
                "riskScore": r.report_data.get("riskScore", "N/A"),
                "vulnerabilities": len(r.report_data.get("dependencies", [])),
                "syntaxIssues": len(r.report_data.get("syntaxIssues", [])),
                "date": r.created_at.strftime("%Y-%m-%d")
            } 
            for r in recent_reports
        ]
        
        summary = await ai_service.generate_strategic_summary(report_summaries)
        return {"summary": summary}
    except Exception as e:
        print(f"Error generating strategic summary: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to generate summary: {str(e)}")

