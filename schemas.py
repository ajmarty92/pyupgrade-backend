from pydantic import BaseModel, EmailStr
from typing import Optional

class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    provider: str
    github_access_token: Optional[str] = None

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class RepoScanRequest(BaseModel):
    repo_name: str

class GenerateFixRequest(BaseModel):
    code_snippet: str
    issue_type: str
    file_path: str
    line: int

class ModernizeSnippetRequest(BaseModel):
    code_snippet: str

# --- NEW SCHEMAS FOR AI FEATURES ---

class CreatePRRequest(BaseModel):
    repo_name: str
    file_path: str
    old_code: str
    new_code: str
    issue_type: str

class PullRequestResponse(BaseModel):
    pr_url: str

class GenerateTestsRequest(BaseModel):
    old_code: str
    new_code: str

class GenerateTestsResponse(BaseModel):
    test_code: str

class StrategicSummaryResponse(BaseModel):
    summary: str

