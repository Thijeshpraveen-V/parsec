from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Dict, List
from api.services.auth_utils import get_github_token
from api.services.pr_generator import create_migration_pr
from api.services.gemini_llm import generate_migration_fix
from api.services.astra_changelogs import ChangelogStore

router = APIRouter()
changelog_store = ChangelogStore()

class PRRequest(BaseModel):
    owner: str
    repo: str
    breakage: Dict
    code_snippet: str
    affected_files: List[str] = []

@router.post("/pr/create")
async def create_pr(
    body: PRRequest,
    github_token: str = Depends(get_github_token),
):
    # 1. Query Astra for similar fixes
    similar = await changelog_store.query_similar_breakages(
        body.breakage.get("reason", ""), top_k=3
    )

    # 2. Get Gemini fix
    fix = await generate_migration_fix(body.breakage, body.code_snippet, similar)

    # 3. Create PR
    result = await create_migration_pr(
        owner=body.owner,
        repo=body.repo,
        github_token=github_token,
        breakage=body.breakage,
        fix_suggestion=fix,
        affected_files=body.affected_files,
    )

    return {
        **result,
        "ai_fix": fix,
    }
