"""
End-to-end backend verification script for Parsec.
Tests: PyPI fetch, GitHub fetch, AstraDB store/query, LLM prompt building.
Run with: uv run python test_backend.py
"""
import asyncio
import os

from dotenv import load_dotenv
load_dotenv()

SEP = "-" * 60

def section(title):
    print(f"\n{SEP}\n  {title}\n{SEP}")

def ok(msg):   print(f"  [OK]   {msg}")
def fail(msg): print(f"  [FAIL] {msg}")
def info(msg): print(f"  [i]    {msg}")


# ══════════════════════════════════════════════════════════════════════
# 1. ENV CHECK
# ══════════════════════════════════════════════════════════════════════
section("1  Environment Variables")
required = {
    "ASTRA_DB_APPLICATION_TOKEN": os.getenv("ASTRA_DB_APPLICATION_TOKEN"),
    "ASTRA_DB_API_ENDPOINT":      os.getenv("ASTRA_DB_API_ENDPOINT"),
    "GROQ_API_KEY":               os.getenv("GROQ_API_KEY"),
    "GITHUB_TOKEN":               os.getenv("GITHUB_TOKEN"),
}
all_env_ok = True
for key, val in required.items():
    if val:
        ok(f"{key} = ...{val[-8:]}")
    else:
        fail(f"{key} is NOT set")
        all_env_ok = False

if not all_env_ok:
    print("\n[WARN] Some env vars are missing - tests may fail.\n")


# ══════════════════════════════════════════════════════════════════════
# 2. PYPI FETCH
# ══════════════════════════════════════════════════════════════════════
async def test_pypi():
    section("2  PyPI Changelog Fetch  (requests  2.28.0 -> 2.31.0)")
    from api.services.astra_changelogs import ChangelogStore
    store = ChangelogStore.__new__(ChangelogStore)
    result = await store._fetch_pypi_changelog("requests", "2.28.0", "2.31.0")
    if "error" in result:
        fail(f"PyPI fetch error: {result['error']}")
    else:
        ok(f"source        : {result.get('source')}")
        ok(f"description   : {result.get('description', '')[:80]}")
        ok(f"old_date      : {result.get('old_release_date')}")
        ok(f"new_date      : {result.get('new_release_date')}")
        ok(f"changelog_url : {result.get('changelog_url') or '(not listed on PyPI)'}")
    return result


# ══════════════════════════════════════════════════════════════════════
# 3. GITHUB RELEASES FETCH
# ══════════════════════════════════════════════════════════════════════
async def test_github():
    section("3  GitHub Releases Fetch  (flask  2.3.0 -> 3.0.0)")
    from api.services.astra_changelogs import ChangelogStore
    store = ChangelogStore.__new__(ChangelogStore)
    releases = await store._fetch_github_releases("flask", "2.3.0", "3.0.0")
    if not releases:
        fail("No GitHub releases returned (check GITHUB_TOKEN or repo URL logic)")
    elif isinstance(releases[0], dict) and "error" in releases[0]:
        fail(f"GitHub fetch error: {releases[0]['error']}")
    else:
        ok(f"Found {len(releases)} releases between 2.3.0 and 3.0.0")
        for r in releases[:3]:
            info(f"tag={r['tag']}  name={r['name']}  date={r['published_at']}")
            body_preview = (r['body'] or "")[:120].strip().replace("\n", " ")
            info(f"body preview: {body_preview!r}")
    return releases


# ══════════════════════════════════════════════════════════════════════
# 4. ASTRA: FETCH + STORE
# ══════════════════════════════════════════════════════════════════════
async def test_astra_store():
    section("4  AstraDB: fetch_and_store_changelogs  (requests  2.28.0 -> 2.31.0)")
    if not os.getenv("ASTRA_DB_APPLICATION_TOKEN"):
        fail("Skipping - ASTRA_DB_APPLICATION_TOKEN not set")
        return None

    from api.services.astra_changelogs import ChangelogStore
    store = ChangelogStore()  # real connection

    result = await store.fetch_and_store_changelogs("requests", "2.28.0", "2.31.0")
    ok(f"docs_stored     : {result['docs_stored']}")
    ok(f"pypi status     : {result['pypi']}")
    ok(f"github_releases : {result['github_releases']}")
    return store


# ══════════════════════════════════════════════════════════════════════
# 5. ASTRA: QUERY SIMILARITY SEARCH
# ══════════════════════════════════════════════════════════════════════
async def test_astra_query(store):
    section("5  AstraDB: query_similar_breakages  ('SSL certificate verification removed')")
    if store is None:
        fail("Skipping - no AstraDB connection")
        return

    results = await store.query_similar_breakages(
        "SSL certificate verification removed", top_k=3
    )
    if not results:
        fail("No results returned (collection may be empty)")
    elif isinstance(results[0], dict) and "error" in results[0]:
        fail(f"Query error: {results[0]['error']}")
    else:
        ok(f"Returned {len(results)} result(s) from AstraDB")
        for r in results:
            info(f"package={r.get('package')}  kind={r.get('kind')}  reason={str(r.get('reason',''))[:80]}")


# ══════════════════════════════════════════════════════════════════════
# 6. ASTRA: store_analysis_breakages
# ══════════════════════════════════════════════════════════════════════
async def test_store_breakages(store):
    section("6  AstraDB: store_analysis_breakages  (synthetic breakage)")
    if store is None:
        fail("Skipping - no AstraDB connection")
        return

    fake_breakage = {
        "package": "requests",
        "old_version": "2.28.0",
        "new_version": "2.31.0",
        "location": "requests.auth.HTTPBasicAuth",
        "kind": "parameter-removed",
        "reason": "The stream kwarg was removed from HTTPBasicAuth.__call__",
    }
    try:
        await store.store_analysis_breakages([fake_breakage])
        ok("Breakage stored in AstraDB successfully")
    except Exception as e:
        fail(f"store_analysis_breakages raised: {e}")


# ══════════════════════════════════════════════════════════════════════
# 7. LLM PROMPT + CALL
# ══════════════════════════════════════════════════════════════════════
async def test_llm():
    section("7  Groq LLM: generate_migration_fix")
    if not os.getenv("GROQ_API_KEY"):
        fail("Skipping - GROQ_API_KEY not set")
        return

    from api.services.gemini_llm import generate_migration_fix

    breakage = {
        "package": "requests",
        "old_version": "2.28.0",
        "new_version": "2.31.0",
        "location": "requests.auth.HTTPBasicAuth",
        "kind": "parameter-removed",
        "reason": "The stream kwarg was removed from HTTPBasicAuth.__call__",
    }
    code_usage = "auth = HTTPBasicAuth(user, pwd, stream=True)"
    similar_docs = [{"reason": "stream kwarg deprecated in 2.29, removed in 2.31"}]

    info("Prompt fields sent to Groq:")
    info(f"  Package : {breakage['package']} {breakage['old_version']} -> {breakage['new_version']}")
    info(f"  Location: {breakage['location']}")
    info(f"  Kind    : {breakage['kind']}")
    info(f"  Reason  : {breakage['reason']}")
    info(f"  Code    : {code_usage}")
    info(f"  Similar : {similar_docs[0]['reason']}")

    try:
        fix = await generate_migration_fix(breakage, code_usage, similar_docs)
        ok("Groq responded successfully!")
        print("\n  -- Suggested Fix --")
        for line in fix.strip().splitlines():
            print(f"  {line}")
        print("  -------------------")
    except Exception as e:
        fail(f"LLM call failed: {e}")


# ══════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════
async def main():
    print("\n=== Parsec Backend Full Workflow Verification ===\n")
    await test_pypi()
    await test_github()
    store = await test_astra_store()
    await test_astra_query(store)
    await test_store_breakages(store)
    await test_llm()
    section("Done - check [OK]/[FAIL] above")

asyncio.run(main())
