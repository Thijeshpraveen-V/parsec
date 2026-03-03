from astrapy import DataAPIClient
from astrapy.info import (
    CollectionDefinition,
    VectorServiceOptions,
    CollectionVectorOptions,
)
import httpx
import os
from typing import List, Dict

COLLECTION_NAME = "package_changelogs"

# NVIDIA NV-Embed-QA via AstraDB vectorize — no local model needed
_NVIDIA_PROVIDER = "nvidia"
_NVIDIA_MODEL = "NV-Embed-QA"


class ChangelogStore:
    def __init__(self):
        token = os.getenv("ASTRA_DB_APPLICATION_TOKEN")
        endpoint = os.getenv("ASTRA_DB_API_ENDPOINT")

        if token and endpoint:
            client = DataAPIClient(token)
            self.db = client.get_database(endpoint)
            self._ensure_collection()
        else:
            self.db = None  # Graceful no-op when env vars are missing

    def _ensure_collection(self):
        try:
            existing = {c.name: c for c in self.db.list_collections()}

            if COLLECTION_NAME in existing:
                descriptor = existing[COLLECTION_NAME]
                # Check if the collection already has vectorize configured
                has_service = (
                    descriptor.definition
                    and descriptor.definition.vector
                    and descriptor.definition.vector.service is not None
                )
                if has_service:
                    print(f"AstraDB collection '{COLLECTION_NAME}' already configured with vectorize.")
                    return  # All good, nothing to do
                else:
                    # Old collection without vectorize — drop it so we can recreate
                    print(f"Collection '{COLLECTION_NAME}' exists without vectorize. Dropping and recreating...")
                    self.db.drop_collection(COLLECTION_NAME)

            # Create fresh with NVIDIA vectorize
            self.db.create_collection(
                COLLECTION_NAME,
                definition=CollectionDefinition(
                    vector=CollectionVectorOptions(
                        metric="cosine",
                        service=VectorServiceOptions(
                            provider=_NVIDIA_PROVIDER,
                            model_name=_NVIDIA_MODEL,
                        ),
                    )
                ),
            )
            print(f"Created AstraDB collection '{COLLECTION_NAME}' with NVIDIA vectorize")
        except Exception as e:
            print(f"Astra collection init failed: {e}")
            raise

    # ─────────────────────────────────────────────
    # Fetch PyPI changelog
    # ─────────────────────────────────────────────
    async def _fetch_pypi_changelog(self, package: str, old_version: str, new_version: str) -> Dict:
        """
        Fetches release history from PyPI JSON API.
        Returns: {current_version_info, latest_version_info, release_url}
        """
        url = f"https://pypi.org/pypi/{package}/json"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()

            info = data.get("info", {})
            releases = data.get("releases", {})

            old_release = releases.get(old_version, [])
            latest_release = releases.get(new_version, [])

            return {
                "source": "pypi",
                "package_url": info.get("project_url", ""),
                "description": info.get("summary", ""),
                "old_release_date": old_release[0].get("upload_time", "") if old_release else "",
                "new_release_date": latest_release[0].get("upload_time", "") if latest_release else "",
                "changelog_url": info.get("project_urls", {}).get("Changelog", ""),
            }
        except Exception as e:
            return {"source": "pypi", "error": str(e)}

    # ─────────────────────────────────────────────
    # Fetch GitHub release notes
    # ─────────────────────────────────────────────
    async def _fetch_github_releases(
        self, package: str, old_version: str, new_version: str
    ) -> List[Dict]:
        """
        1. Get PyPI project_urls to find GitHub repo link
        2. Fetch GitHub releases between old and new version
        """
        github_token = os.getenv("GITHUB_TOKEN", "")
        headers = {"Authorization": f"Bearer {github_token}"} if github_token else {}

        # Step 1: Find GitHub URL from PyPI
        github_url = None
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                pypi_resp = await client.get(f"https://pypi.org/pypi/{package}/json")
                pypi_data = pypi_resp.json()
                project_urls = pypi_data.get("info", {}).get("project_urls", {}) or {}
                for key in ["Source", "Repository", "Homepage", "GitHub", "Code"]:
                    url = project_urls.get(key, "")
                    if "github.com" in url:
                        github_url = url.rstrip("/")
                        break
        except Exception:
            return []

        if not github_url:
            return []

        # Step 2: Extract owner/repo from URL
        # e.g. https://github.com/pallets/flask → pallets/flask
        try:
            parts = github_url.replace("https://github.com/", "").split("/")
            owner, repo = parts[0], parts[1]
        except Exception:
            return []

        # Step 3: Fetch releases from GitHub API
        releases = []
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"https://api.github.com/repos/{owner}/{repo}/releases?per_page=20",
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()

            for release in data:
                tag = release.get("tag_name", "").lstrip("v")
                if old_version <= tag <= new_version:
                    releases.append({
                        "tag": release.get("tag_name"),
                        "name": release.get("name"),
                        "published_at": release.get("published_at"),
                        "body": release.get("body", "")[:2000],  # Limit size
                    })
        except Exception as e:
            return [{"error": str(e)}]

        return releases

    # ─────────────────────────────────────────────
    # Fetch + store changelogs for a package
    # ─────────────────────────────────────────────
    async def fetch_and_store_changelogs(
        self, package: str, old_version: str, new_version: str
    ):
        if self.db is None:
            return {"package": package, "docs_stored": 0, "pypi": "skipped", "github_releases": 0}

        pypi_info = await self._fetch_pypi_changelog(package, old_version, new_version)
        github_releases = await self._fetch_github_releases(package, old_version, new_version)

        collection = self.db.get_collection(COLLECTION_NAME)
        docs = []

        # PyPI doc — use $vectorize so NVIDIA embeds server-side
        if "error" not in pypi_info:
            text = (
                f"{package} {old_version} → {new_version}: "
                f"{pypi_info.get('description', '')} "
                f"Released: {pypi_info.get('new_release_date', '')}"
            )
            docs.append({
                "_id": f"{package}_{old_version}_{new_version}_pypi",
                "package": package,
                "old_version": old_version,
                "new_version": new_version,
                "source": "pypi",
                "content": text,
                "raw": pypi_info,
                "$vectorize": text,  # NVIDIA NV-Embed-QA embeds this server-side
            })

        # GitHub release docs
        for release in github_releases:
            if "error" not in release:
                text = (
                    f"{package} {release['tag']}: "
                    f"{release['name']} - {release['body']}"
                )
                docs.append({
                    "_id": f"{package}_{release['tag']}_github",
                    "package": package,
                    "old_version": old_version,
                    "new_version": new_version,
                    "source": "github_release",
                    "tag": release["tag"],
                    "content": text,
                    "raw": release,
                    "$vectorize": text[:1000],  # NVIDIA NV-Embed-QA embeds this server-side
                })

        # Upsert to Astra
        for doc in docs:
            try:
                collection.find_one_and_replace(
                    {"_id": doc["_id"]},
                    doc,
                    upsert=True,
                )
            except Exception as e:
                print(f"Astra upsert failed: {e}")

        return {
            "package": package,
            "docs_stored": len(docs),
            "pypi": "ok" if "error" not in pypi_info else "failed",
            "github_releases": len(github_releases),
        }

    # ─────────────────────────────────────────────
    # Store Griffe breakages
    # ─────────────────────────────────────────────
    async def store_analysis_breakages(self, breakages: List[Dict]):
        """Store Griffe breakages in AstraDB — NVIDIA vectorize embeds on the server."""
        if self.db is None:
            return

        collection = self.db.get_collection(COLLECTION_NAME)
        docs = []
        for b in breakages:
            if "error" not in b and "info" not in b:
                # Also fetch + store real changelogs
                await self.fetch_and_store_changelogs(
                    b["package"], b.get("old_version", ""), b.get("new_version", "")
                )
                text = f"{b['package']} {b.get('kind', '')}: {b.get('reason', '')}"
                doc = {
                    "_id": f"{b['package']}_{b.get('old_version', '')}_{b.get('location', '')}",
                    "package": b["package"],
                    "old_version": b.get("old_version", ""),
                    "new_version": b.get("new_version", ""),
                    "location": b.get("location", ""),
                    "kind": b.get("kind", ""),
                    "reason": b.get("reason", ""),
                    "source": "griffe",
                    "content": text,
                    "$vectorize": text,  # AstraDB sends this to NVIDIA for embedding
                }
                docs.append(doc)

        if docs:
            collection.upsert_many(docs)

    # ─────────────────────────────────────────────
    # Query similar breakages/changelogs
    # ─────────────────────────────────────────────
    async def query_similar_breakages(self, query: str, top_k: int = 3) -> List[Dict]:
        """Find similar breakages — NVIDIA vectorize embeds the query on the server."""
        if self.db is None:
            return []

        collection = self.db.get_collection(COLLECTION_NAME)
        cursor = collection.find(
            {},
            sort={"$vectorize": query},  # AstraDB embeds this string server-side
            limit=top_k,
            projection={"package": True, "kind": True, "reason": True, "location": True},
        )
        return list(cursor)
