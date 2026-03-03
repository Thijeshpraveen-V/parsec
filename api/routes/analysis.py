from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List
from api.services.auth_utils import get_github_token
from api.routes.repo import (
    analyze_repo_dependencies, AnalyzeDepsRequest,
    analyze_repo_usage, AnalyzeUsageRequest,
)
from api.services.griffe_analyser import analyze_package_breaking_changes  # ✅ Fixed typo
from api.services.astra_changelogs import ChangelogStore
from api.services.gemini_llm import generate_migration_fix

router = APIRouter()

_changelog_store = None
def _get_changelog_store() -> ChangelogStore:
    global _changelog_store
    if _changelog_store is None:
        _changelog_store = ChangelogStore()
    return _changelog_store

class FullAnalysisRequest(BaseModel):
    owner: str
    repo: str
    branch: str | None = None

@router.post("/analyze/full")
async def full_analysis(
    body: FullAnalysisRequest,
    github_token: str = Depends(get_github_token),
):
    branch = body.branch or "main"

    # 1) Get deps + usage
    deps_result = await analyze_repo_dependencies(
        AnalyzeDepsRequest(owner=body.owner, repo=body.repo, branch=branch),
        github_token=github_token,
    )
    usage_result = await analyze_repo_usage(
        AnalyzeUsageRequest(owner=body.owner, repo=body.repo, branch=branch),
        github_token=github_token,
    )

    # 2) Run Griffe on pinned deps
    breakages = []
    pinned_deps = [
        dep for dep in deps_result["dependencies"][:5] 
        if dep.get("version_spec", "").startswith(("==", ">=", "<=", "~="))
    ]
    for dep in pinned_deps:
        griffe_result = await analyze_package_breaking_changes(
            package=dep["name"],
            version_spec=dep.get("version_spec", ""),
        )
        breakages.extend(griffe_result)

    # 3) Store in Astra
    try:
        await _get_changelog_store().store_analysis_breakages(breakages)
    except Exception as e:
        print(f"Astra store failed: {e}")

    return {
        "repo": {"owner": body.owner, "repo": body.repo, "branch": branch},
        "dependency_files": deps_result["dependency_files"],
        "dependencies": deps_result["dependencies"],
        "package_usage": usage_result["package_usage"],
        "breaking_changes": breakages,
        "astra_status": "stored" if len(breakages) > 0 else "no breakages",
    }

@router.post("/astra/query")
async def query_astra(query: str):
    """Test Astra similarity search."""
    results = await _get_changelog_store().query_similar_breakages(query, top_k=3)
    return {"query": query, "similar_breakages": results}

@router.post("/ai/fix")
async def ai_fix_breakage(body: Dict[str, Any]):
    """AI migration fix — fetches real changelog data if AstraDB has none for this package."""
    breakage = body["breakage"]
    code_snippet = body.get("code_snippet", "")
    package     = breakage.get("package", "")
    old_version = breakage.get("old_version", "")
    new_version = breakage.get("new_version", "")

    store = _get_changelog_store()
    query = breakage.get("reason") or package

    # Step 1: query existing AstraDB data
    similar = await store.query_similar_breakages(query, top_k=3)

    # Step 2: if no package-specific results, fetch real changelog data on demand
    package_in_results = any(
        r.get("package", "").lower() == package.lower()
        for r in similar
        if isinstance(r, dict) and "error" not in r
    )

    if not package_in_results and package:
        print(f"[AI Fix] No AstraDB data for '{package}' — fetching from PyPI/GitHub...")
        try:
            await store.fetch_and_store_changelogs(package, old_version, new_version)
            # Re-query now that data is stored
            similar = await store.query_similar_breakages(query, top_k=3)
            print(f"[AI Fix] Fetched and re-queried. Got {len(similar)} results.")
        except Exception as fetch_err:
            print(f"[AI Fix] Fetch failed (non-fatal): {fetch_err}")

    # Step 3: generate fix with whatever context we have
    try:
        fix = await generate_migration_fix(breakage, code_snippet, similar)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        err = str(e)
        print(f"[Groq ERROR] {err}")
        if "429" in err or "RESOURCE_EXHAUSTED" in err:
            raise HTTPException(
                status_code=429,
                detail="Groq API quota exceeded. Please wait a moment and try again.",
            )
        raise HTTPException(status_code=500, detail=f"AI fix failed: {err}")

    return {
        "original_breakage": breakage,
        "similar_examples": similar,
        "suggested_fix": fix,
    }
