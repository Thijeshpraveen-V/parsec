import subprocess
import tempfile
import os
from typing import Dict, List
from pathlib import Path

async def perform_git_operation(
    owner: str,
    repo: str,
    github_token: str,
    operation: str,       # "rebase" | "merge" | "cherry-pick"
    source_branch: str,   # e.g. "main"
    target_branch: str,   # e.g. "feature"
) -> Dict:
    """
    Safely run git ops in isolated temp clone.
    Never touches the real repo.
    """
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        repo_url = f"https://x-access-token:{github_token}@github.com/{owner}/{repo}.git"

        # 1. Clone both branches (shallow=100 for speed)
        clone = subprocess.run([
            "git", "clone", repo_url,
            "--depth", "100",
            "--no-single-branch",
            tmp_dir,
        ], capture_output=True, text=True, timeout=60)

        if clone.returncode != 0:
            return {"success": False, "error": clone.stderr}

        # 2. Configure git identity (required for rebase/merge)
        subprocess.run(["git", "config", "user.email", "bot@parsec.dev"], cwd=tmp_dir)
        subprocess.run(["git", "config", "user.name", "Parsec Bot"], cwd=tmp_dir)

        # 3. Capture BEFORE log
        before_log = subprocess.run([
            "git", "log", "--oneline", "--graph", "--all", "-10"
        ], capture_output=True, text=True, cwd=tmp_dir).stdout

        # 4. Checkout target branch
        subprocess.run(["git", "checkout", target_branch], cwd=tmp_dir, capture_output=True)

        # 5. Perform the operation
        if operation == "rebase":
            op_result = subprocess.run([
                "git", "rebase", source_branch
            ], capture_output=True, text=True, cwd=tmp_dir, timeout=120)

        elif operation == "merge":
            op_result = subprocess.run([
                "git", "merge", source_branch, "--no-ff", "-m",
                f"Merge {source_branch} into {target_branch}"
            ], capture_output=True, text=True, cwd=tmp_dir, timeout=120)

        elif operation == "cherry-pick":
            # Cherry-pick latest commit from source_branch
            latest = subprocess.run([
                "git", "rev-parse", source_branch
            ], capture_output=True, text=True, cwd=tmp_dir).stdout.strip()
            op_result = subprocess.run([
                "git", "cherry-pick", latest
            ], capture_output=True, text=True, cwd=tmp_dir, timeout=120)
        else:
            return {"success": False, "error": f"Unknown operation: {operation}"}

        # 6. Capture AFTER log
        after_log = subprocess.run([
            "git", "log", "--oneline", "--graph", "--all", "-10"
        ], capture_output=True, text=True, cwd=tmp_dir).stdout

        # 7. Get diff summary
        diff_stat = subprocess.run([
            "git", "diff", "--stat", f"{target_branch}..{source_branch}"
        ], capture_output=True, text=True, cwd=tmp_dir).stdout

        return {
            "success": op_result.returncode == 0,
            "operation": operation,
            "source_branch": source_branch,
            "target_branch": target_branch,
            "output": op_result.stdout or op_result.stderr,
            "before_log": before_log,
            "after_log": after_log,
            "diff_stat": diff_stat,
            "conflicts": "CONFLICT" in (op_result.stdout + op_result.stderr),
        }
