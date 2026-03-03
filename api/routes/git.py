from fastapi import APIRouter, Depends
from pydantic import BaseModel
from api.services.auth_utils import get_github_token
from api.services.git_visualizer import visualize_git_repo
from api.services.git_operations import perform_git_operation

router = APIRouter()

class GitVizRequest(BaseModel):
    owner: str
    repo: str
    branch: str = "main"

@router.post("/git/visualize")
async def git_visualize(body: GitVizRequest, github_token: str = Depends(get_github_token)):
    result = await visualize_git_repo(body.owner, body.repo, github_token, body.branch)
    return result

class GitOpRequest(BaseModel):
    owner: str
    repo: str
    source_branch: str = "main"
    target_branch: str
    operation: str = "rebase"  # "rebase" | "merge" | "cherry-pick"

@router.post("/git/operation")
async def git_operation(
    body: GitOpRequest,
    github_token: str = Depends(get_github_token),
):
    result = await perform_git_operation(
        owner=body.owner,
        repo=body.repo,
        github_token=github_token,
        operation=body.operation,
        source_branch=body.source_branch,
        target_branch=body.target_branch,
    )
    return result