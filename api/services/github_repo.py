import httpx
from typing import List, Dict
import base64

GITHUB_API_BASE = "https://api.github.com"

async def get_repo_tree(owner: str, repo: str, github_token: str, branch: str = "main"):
    """
    Returns flat list of all files (paths) in the repo using Git Trees API.
    """
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
    }

    async with httpx.AsyncClient() as client:
        # 1) Get branch to find tree SHA
        branch_resp = await client.get(
            f"{GITHUB_API_BASE}/repos/{owner}/{repo}/branches/{branch}",
            headers=headers,
        )
        if branch_resp.status_code != 200:
            # try 'master' fallback
            branch_resp = await client.get(
                f"{GITHUB_API_BASE}/repos/{owner}/{repo}/branches/master",
                headers=headers,
            )
            branch_resp.raise_for_status()
        branch_data = branch_resp.json()
        tree_sha = branch_data["commit"]["commit"]["tree"]["sha"]

        # 2) Get full tree recursively
        tree_resp = await client.get(
            f"{GITHUB_API_BASE}/repos/{owner}/{repo}/git/trees/{tree_sha}?recursive=1",
            headers=headers,
        )
        tree_resp.raise_for_status()
        tree_data = tree_resp.json()

        files = [
            item["path"]
            for item in tree_data.get("tree", [])
            if item["type"] == "blob"
        ]
        return files

DEPENDENCY_FILENAMES = {
    "requirements.txt",
    "requirements-dev.txt",
    "requirements_dev.txt",
    "requirements-prod.txt",
    "requirements_prod.txt",
    "pyproject.toml",
    "pipfile",
    "pipfile.lock",
    "setup.py",
    "setup.cfg",
    "environment.yml",
    "environment.yaml",
}

def is_dependency_file(path: str) -> bool:
    lower = path.lower()
    name = lower.split("/")[-1]
    if name in DEPENDENCY_FILENAMES:
        return True
    if name.startswith("requirements") and name.endswith(".txt"):
        return True
    return False

def classify_repo_files(files: List[str]) -> Dict[str, List[str]]:
    dependency_files: List[str] = []
    python_files: List[str] = []

    for path in files:
        lower = path.lower()
        if is_dependency_file(path):
            dependency_files.append(path)
        if lower.endswith(".py"):
            python_files.append(path)

    return {
        "dependency_files": dependency_files,
        "python_files": python_files,
    }

async def get_file_content(owner: str, repo: str, path: str, github_token: str, branch: str = "main") -> str:
    """
    Fetch a single file's content from GitHub (as text).
    """
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
    }

    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}?ref={branch}"

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()

        if data.get("encoding") == "base64":
            return base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
        # Fallback if GitHub ever returns plain text
        return data.get("content", "")