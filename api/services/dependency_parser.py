from typing import List, Dict
import re
import toml  # pip install toml

REQ_LINE_RE = re.compile(
    r"^\s*([A-Za-z0-9_.\-]+)"
    r"\s*"
    r"([<>=!~]{1,2}\s*[^#;\s]+)?"
)

def parse_requirements_text(text: str) -> List[Dict[str, str]]:
    deps: List[Dict[str, str]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith(("-", "--")):
            continue
        m = REQ_LINE_RE.match(line)
        if not m:
            continue
        name = m.group(1)
        spec = m.group(2).replace(" ", "") if m.group(2) else ""
        deps.append({"name": name, "version_spec": spec, "type": "requirements"})
    return deps

def parse_pyproject_toml(text: str) -> List[Dict[str, str]]:
    """
    Parses PEP 621 [project.dependencies] and [project.optional-dependencies].
    """
    deps: List[Dict[str, str]] = []
    try:
        data = toml.loads(text)

        # Primary dependencies
        if "project" in data:
            project = data["project"]
            if "dependencies" in project:
                for dep in project["dependencies"]:
                    deps.append({"name": dep, "version_spec": "", "type": "pyproject-primary"})
            
            # Optional dependencies
            if "optional-dependencies" in project:
                for group, group_deps in project["optional-dependencies"].items():
                    for dep in group_deps:
                        deps.append({"name": dep, "version_spec": "", "type": f"pyproject-{group}"})

    except Exception:
        pass  # Ignore parse errors

    return deps
