from groq import Groq
import os

_client = None
_client_key = None


def _get_client() -> Groq:
    global _client, _client_key
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY is not set. Add it to your .env file. "
            "Get a free key at https://console.groq.com/keys"
        )
    if _client is None or api_key != _client_key:
        print(f"[Groq] Creating client with key ...{api_key[-6:]}")
        _client = Groq(api_key=api_key)
        _client_key = api_key
    return _client


async def generate_migration_fix(
    breakage: dict,
    code_usage: str,
    similar_docs: list,
) -> str:
    """
    Groq (llama-3.3-70b): given a breaking change + changelog context,
    always produce a concrete code fix — never ask for more info.
    """
    package     = breakage.get("package", "unknown")
    old_version = breakage.get("old_version", "?")
    new_version = breakage.get("new_version", "latest")
    location    = breakage.get("location", "?")
    kind        = breakage.get("kind", "?")
    reason      = breakage.get("reason", "?")

    # Build changelog context from AstraDB results
    changelog_lines = []
    for d in similar_docs:
        if not isinstance(d, dict) or "error" in d:
            continue
        content = d.get("content") or d.get("reason") or ""
        raw = d.get("raw", {}) or {}
        desc = raw.get("description", "") or raw.get("body", "") or ""
        if content:
            changelog_lines.append(f"- {content[:300]}")
        elif desc:
            changelog_lines.append(f"- {desc[:300]}")

    changelog_context = "\n".join(changelog_lines) if changelog_lines else (
        f"No pre-fetched changelog entries. Use your knowledge of {package} "
        f"version {old_version} → {new_version} change history."
    )

    prompt = "\n".join([
        f"Package   : {package}",
        f"Versions  : {old_version} → {new_version}",
        f"Location  : {location}",
        f"Kind      : {kind}",
        f"Reason    : {reason}",
        "",
        f"User code that uses this package:",
        f"{code_usage or '(no specific code snippet provided)'}",
        "",
        f"Real changelog / release notes context:",
        changelog_context,
        "",
        "TASK: Provide the exact minimal code fix for this breaking change.",
        "Show the old line(s) and new line(s) with a one-sentence explanation.",
        "Do NOT ask for more information. Do NOT give a hypothetical example.",
        "If you are unsure of the exact new API, use your training knowledge of",
        f"the {package} library to give the most accurate fix possible.",
    ])

    response = _get_client().chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an expert Python developer specialising in library migrations. "
                    "You ALWAYS provide a concrete, working code fix — you NEVER say "
                    "'I need more information' or give hypothetical examples. "
                    "Use the changelog context provided, combined with your knowledge, "
                    "to produce the most accurate minimal fix. "
                    "Format: show OLD code line(s), NEW code line(s), one-line explanation."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        max_tokens=600,
        temperature=0.1,   # Lower = more deterministic, less hallucination
    )
    return response.choices[0].message.content
