import subprocess
import tempfile
from typing import List, Dict
from griffe import find_breaking_changes, load
import httpx


async def get_latest_version(package: str) -> str:
    """Fetch the latest version from PyPI JSON API (no install needed)."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"https://pypi.org/pypi/{package}/json")
            if resp.status_code == 200:
                return resp.json()["info"]["version"]
    except Exception:
        pass
    return "latest"


def _uv_install_to(package_with_version: str, target_dir: str) -> bool:
    """
    Install a package into an isolated target dir using uv.
    Returns True on success, False on failure.
    """
    result = subprocess.run(
        ["uv", "pip", "install", package_with_version, "--target", target_dir],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


async def analyze_package_breaking_changes(package: str, version_spec: str = "") -> List[Dict]:
    """
    Uses Griffe to detect breaking changes between a pinned version and the latest.
    Installs into isolated temp directories — the live venv is never modified.
    Falls back gracefully if the old version cannot be installed (e.g. needs build tools).
    """
    breakages = []

    old_version = (
        version_spec.replace("==", "").replace(">=", "").replace("<=", "").strip()
        if version_spec
        else None
    )

    if not old_version:
        return [{"package": package, "info": "No pinned version provided, skipping comparison."}]

    try:
        latest_version = await get_latest_version(package)

        if old_version == latest_version:
            return [{"package": package, "info": f"Already at latest version ({latest_version}), no comparison needed."}]

        with tempfile.TemporaryDirectory() as old_dir, \
             tempfile.TemporaryDirectory() as new_dir:

            # Install old pinned version
            old_ok = _uv_install_to(f"{package}=={old_version}", old_dir)

            if not old_ok:
                return [{
                    "package": package,
                    "old_version": old_version,
                    "warning": f"Could not install {package}=={old_version} (may require build tools or version doesn't exist). Skipping analysis.",
                }]

            # Install latest version
            new_ok = _uv_install_to(package, new_dir)

            if not new_ok:
                return [{
                    "package": package,
                    "warning": f"Could not install latest {package}. Skipping analysis.",
                }]

            # Load both API trees from isolated dirs
            old_module = load(package, search_paths=[old_dir])
            new_module = load(package, search_paths=[new_dir])

            changes = list(find_breaking_changes(old_module, new_module))

            if not changes:
                breakages.append({
                    "package": package,
                    "old_version": old_version,
                    "new_version": latest_version,
                    "breaking_changes": 0,
                    "info": "No breaking changes detected.",
                })
            else:
                for change in changes:
                    breakages.append({
                        "package": package,
                        "old_version": old_version,
                        "new_version": latest_version,
                        "location": str(change.member.path),
                        "kind": change.kind.value,
                        "reason": str(change.reason),
                    })

    except Exception as e:
        breakages.append({
            "package": package,
            "error": str(e),
        })

    return breakages
