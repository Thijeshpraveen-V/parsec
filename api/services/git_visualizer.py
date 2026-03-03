import subprocess
import tempfile
import os
from typing import Dict, List

async def visualize_git_repo(owner: str, repo: str, github_token: str, branch: str = "main") -> Dict:
    """
    1. Clone repo to temp dir
    2. Get git log --graph → parse into JSON tree
    3. Return branches + commits for frontend visualization
    """
    # ignore_cleanup_errors=True avoids a Windows 500 on rare lock races
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        # Clone shallow (fast) — cwd stays as original dir, NOT tmp_dir
        clone_cmd = [
            "git", "clone",
            f"https://x-access-token:{github_token}@github.com/{owner}/{repo}.git",
            "--depth", "50",
            "--single-branch",
            tmp_dir,
        ]

        result = subprocess.run(clone_cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            raise Exception(f"Clone failed: {result.stderr}")

        # Pass cwd= instead of os.chdir — keeps the process CWD unlocked
        # so Windows can delete the temp dir on cleanup.
        branches_result = subprocess.run(
            ["git", "branch", "-r"],
            capture_output=True, text=True,
            cwd=tmp_dir,
        )
        branches = [
            b.strip().replace("origin/", "")
            for b in branches_result.stdout.splitlines()
            if b.strip()
        ]

        log_result = subprocess.run(
            ["git", "log", "--graph", "--oneline", "--decorate", "--all", "-20"],
            capture_output=True, text=True,
            cwd=tmp_dir,
        )

        commits = []
        for line in log_result.stdout.splitlines()[:20]:
            if line.strip():
                parts = line.split(" ", 1)
                commit_hash = parts[0].replace("*", "").strip()
                rest = parts[1] if len(parts) > 1 else ""
                commits.append({
                    "hash": commit_hash[:8],
                    "message": rest,
                    "branches": [b for b in branches if f"({b})" in rest],
                })

        return {
            "repo": f"{owner}/{repo}",
            "branches": branches[:10],
            "commits": commits,
            "log_sample": log_result.stdout.splitlines()[:10],
        }
