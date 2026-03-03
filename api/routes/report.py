from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Dict, Any
from api.services.auth_utils import get_github_token
from api.services.report_generator import generate_pdf_report
from api.services.astra_changelogs import ChangelogStore
from api.services.gemini_llm import generate_migration_fix
import asyncio

router = APIRouter()

_store = None
def _get_store() -> ChangelogStore:
    global _store
    if _store is None:
        _store = ChangelogStore()
    return _store

class ReportRequest(BaseModel):
    analysis: Dict[str, Any]

async def _ai_fix_for_breakage(b: dict) -> str:
    """Fetch changelog data on demand and generate an AI fix for one breakage."""
    package     = b.get("package", "")
    old_version = b.get("old_version", "")
    new_version = b.get("new_version", "")
    query       = b.get("reason") or package

    store = _get_store()
    similar = await store.query_similar_breakages(query, top_k=3)

    # On-demand fetch if no package data exists
    package_found = any(
        r.get("package", "").lower() == package.lower()
        for r in similar
        if isinstance(r, dict) and "error" not in r
    )
    if not package_found and package:
        try:
            await store.fetch_and_store_changelogs(package, old_version, new_version)
            similar = await store.query_similar_breakages(query, top_k=3)
        except Exception:
            pass  # non-fatal

    try:
        return await generate_migration_fix(b, "", similar)
    except Exception as e:
        return f"(AI fix unavailable: {e})"


@router.post("/report/download/pdf")
async def download_pdf_report(
    body: ReportRequest,
    github_token: str = Depends(get_github_token),
):
    analysis = body.analysis

    # Auto-generate AI fixes for ALL packages in breaking_changes concurrently
    breaking = analysis.get("breaking_changes", [])

    # Build fix tasks for every entry — AI uses PyPI/GitHub changelogs regardless of Griffe result
    tasks = [_ai_fix_for_breakage(b) for b in breaking]

    ai_fixes: Dict[int, str] = {}
    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for idx, result in enumerate(results):
            ai_fixes[idx] = str(result) if isinstance(result, Exception) else result


    buffer = generate_pdf_report(analysis, ai_fixes=ai_fixes)
    owner = analysis["repo"]["owner"]
    repo  = analysis["repo"]["repo"]
    filename = f"parsec_{owner}_{repo}_report.pdf"

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
