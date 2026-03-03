from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Dict
from api.services.auth_utils import get_github_token
from api.services.github_repo import get_repo_tree, classify_repo_files, get_file_content
from api.services.dependency_parser import parse_requirements_text, parse_pyproject_toml
from api.services.ast_analyzer import find_package_usage
from api.services.griffe_analyser import analyze_package_breaking_changes

router = APIRouter()

class RepoRequest(BaseModel):
    owner: str
    repo: str
    branch: str | None = None

@router.post("/analyze/repo/tree")
async def analyze_repo_tree(
    body: RepoRequest,
    github_token: str = Depends(get_github_token),
):
    try:
        files = await get_repo_tree(
            owner=body.owner,
            repo=body.repo,
            github_token=github_token,
            branch=body.branch or "main",
        )
        classified = classify_repo_files(files)
        return {
            "owner": body.owner,
            "repo": body.repo,
            "file_count": len(files),
            "dependency_files": classified["dependency_files"],
            "python_files_count": len(classified["python_files"]),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

class AnalyzeDepsRequest(BaseModel):
    owner: str
    repo: str
    branch: str | None = None

@router.post("/analyze/repo/dependencies")
async def analyze_repo_dependencies(
    body: AnalyzeDepsRequest,
    github_token: str = Depends(get_github_token),
):
    branch = body.branch or "main"
    files = await get_repo_tree(
        owner=body.owner,
        repo=body.repo,
        github_token=github_token,
        branch=branch,
    )
    classified = classify_repo_files(files)
    dependency_files = classified["dependency_files"]

    all_deps = []

    for path in dependency_files:
        content = await get_file_content(
            owner=body.owner,
            repo=body.repo,
            path=path,
            github_token=github_token,
            branch=branch,
        )

        if path.lower().endswith(".txt") and "requirements" in path.lower():
            deps = parse_requirements_text(content)
        elif path.lower() == "pyproject.toml":
            deps = parse_pyproject_toml(content)
        else:
            continue  # Skip others for now

        all_deps.extend(
            {"file": path, **d}
            for d in deps
        )

    return {
        "owner": body.owner,
        "repo": body.repo,
        "branch": branch,
        "dependency_files": dependency_files,
        "dependencies": all_deps,
    }

class AnalyzeUsageRequest(BaseModel):
    owner: str
    repo: str
    branch: str | None = None

@router.post("/analyze/repo/usage")
async def analyze_repo_usage(
    body: AnalyzeUsageRequest,
    github_token: str = Depends(get_github_token),
):
    branch = body.branch or "main"
    files = await get_repo_tree(
        owner=body.owner,
        repo=body.repo,
        github_token=github_token,
        branch=branch,
    )
    python_files = [f for f in files if f.lower().endswith(".py")]

    # Get dependencies first
    deps_resp = await analyze_repo_dependencies(AnalyzeDepsRequest(**body.model_dump()), github_token=github_token)
    package_names = {dep["name"].lower() for dep in deps_resp["dependencies"]}

    usage_by_package = {}
    for pkg in package_names:
        usage_by_package[pkg] = []

    for py_file in python_files[:10]:  # Limit to first 10 files for speed
        content = await get_file_content(
            owner=body.owner,
            repo=body.repo,
            path=py_file,
            github_token=github_token,
            branch=branch,
        )
        usage = find_package_usage(content, package_names)

        for pkg in package_names:
            pkg_imports = [i for i in usage["imports"] if i.get("package") == pkg]
            pkg_calls   = [c for c in usage["calls"]   if c.get("package") == pkg]
            if pkg_imports or pkg_calls:
                usage_by_package[pkg].append({
                    "file": py_file,
                    "imports": pkg_imports,
                    "calls": pkg_calls,
                })

    return {
        "owner": body.owner,
        "repo": body.repo,
        "package_usage": usage_by_package,
    }

class GriffeRequest(BaseModel):
    packages: List[Dict[str, str]]  # [{"name": "fastapi", "version_spec": "==0.104.1"}]

@router.post("/analyze/griffe")
async def analyze_griffe(
    body: GriffeRequest,
    github_token: str = Depends(get_github_token),  # For auth, not used here
):
    all_breakages = []
    for pkg in body.packages:
        breakages = await analyze_package_breaking_changes(
            package=pkg["name"],
            version_spec=pkg["version_spec"],
        )
        all_breakages.extend(breakages)

    return {"breakages": all_breakages}