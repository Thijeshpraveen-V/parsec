# Dependency Analyser — AI-Powered Dependency Analysis Tool

> Analyse GitHub repositories for outdated or breaking dependencies, get AI-generated migration fixes, create pull requests, and visualize your git history — all from a single web UI.

---

## 🔍 The Problem

Modern Python projects accumulate dependencies over time. When a pinned library releases a new version, it may introduce **breaking API changes** — removed functions, renamed parameters, changed return types — that are invisible until the code actually breaks in production.

Developers face three painful questions:

1. **Which of my dependencies are outdated or have a newer version available?**
2. **Will upgrading them break my existing code, and exactly where?**
3. **What do I need to change in my code to migrate safely?**

Answering these manually requires reading changelogs, diffing library APIs, and hunting through source files — a slow, error-prone process.

---

## 💡 The Solution — Dependency Analyser

Dependency Analyser is a full-stack web application that automates the entire dependency audit-and-migration workflow for Python GitHub repositories.

Given a GitHub repo URL, Dependency Analyser will:

1. **Scan** the repo for dependency files (`requirements.txt`, `pyproject.toml`, etc.)
2. **Find** all pinned dependencies and their current version specs
3. **Detect breaking changes** between your pinned version and the latest version using **Griffe** (a static API analysis library that builds AST trees of the old and new library and compares them)
4. **Scan your Python source files** using Python's built-in **AST parser** to find exactly which files and lines import or call each dependency
5. **Pull real changelog data** from PyPI and GitHub Releases, then store it in **Astra DB** (a vector database) with NVIDIA NV-Embed-QA embeddings for semantic search
6. **Generate AI-powered migration fixes** using **Groq's LLaMA-3.3-70b** model, grounded with the real changelog context from Astra DB
7. **Create a GitHub Pull Request** directly from the UI with a migration guide Markdown file, a proper PR description, and the AI-suggested fix
8. **Visualize your git commit graph** — branches, commits, and a colour-coded SVG graph
9. **Perform git operations** (rebase, merge, cherry-pick) in an isolated temporary clone that never touches your real repo
10. **Export a PDF report** of the full analysis including all dependencies, breaking changes, and AI fixes

---

## 🏗️ Architecture

```
dependency-analyser/
├── api/                         # Python backend (FastAPI)
│   ├── main.py                  # App entry point, CORS config, router registration
│   ├── routes/
│   │   ├── auth.py              # GitHub OAuth login + JWT session management
│   │   ├── repo.py              # Repo tree fetch, dependency parsing, AST usage scan, Griffe
│   │   ├── analysis.py          # Full analysis pipeline + Astra storage + AI fix endpoint
│   │   ├── git.py               # Git graph visualization + git operations (rebase/merge/cherry-pick)
│   │   ├── pr.py                # Pull request creation via GitHub API
│   │   └── report.py            # PDF report generation
│   └── services/
│       ├── github_auth.py       # GitHub OAuth token exchange
│       ├── github_repo.py       # GitHub API: repo tree traversal + file content fetch
│       ├── dependency_parser.py # Parse requirements.txt and pyproject.toml into dep lists
│       ├── ast_analyzer.py      # Python AST visitor to find imports and function calls per package
│       ├── griffe_analyser.py   # Griffe-based breaking change detection (installs to temp dirs via uv)
│       ├── astra_changelogs.py  # Astra DB vector store: store + query changelogs with NVIDIA embeddings
│       ├── gemini_llm.py        # Groq (LLaMA-3.3-70b) AI fix generation
│       ├── git_visualizer.py    # Clone repo to temp dir, parse git log into JSON for frontend
│       ├── git_operations.py    # Run rebase/merge/cherry-pick in isolated temp clone
│       ├── pr_generator.py      # Clone, create branch, commit migration guide, push, open PR
│       ├── report_generator.py  # ReportLab PDF generation with tables, AI fixes, styled output
│       └── auth_utils.py        # JWT token extraction middleware
│
└── frontend/                    # React + Vite frontend
    └── src/
        ├── App.jsx              # Main app: login screen, home page, analysis page
        ├── GitGraph.jsx         # SVG commit graph visualizer + branch legend
        ├── GitOperations.jsx    # UI panel for rebase / merge / cherry-pick operations
        └── App.css              # All styling (dark theme, cards, tables, animations)
```

---

## ✨ Features

### 🔐 GitHub OAuth Authentication
- Login with your GitHub account via OAuth 2.0
- A short-lived **JWT** (8 hours) stores your GitHub access token — no passwords, no separate account needed
- Token is stored in `localStorage` and auto-expires

### 📦 Dependency Detection
- Automatically scans the repo's full file tree using the **GitHub Trees API**
- Detects dependency files: `requirements.txt`, `requirements-dev.txt`, `pyproject.toml`, `setup.py`, `Pipfile`, `environment.yml`, and variants
- Parses each file to extract package names and version specifiers (e.g., `fastapi==0.104.1`, `httpx>=0.27`)
- Supports both `requirements.txt` format and **PEP 621** `pyproject.toml` format

### 🔬 Breaking Change Detection via Griffe + AST
- For each **pinned** dependency (with `==`, `>=`, `<=`, `~=` version specs), Dependency Analyser:
  1. Fetches the latest version from **PyPI JSON API** (no install needed for this step)
  2. Installs the **old pinned version** into an isolated temporary directory using `uv pip install --target`
  3. Installs the **latest version** into a second isolated temporary directory
  4. Loads both versions' full **API trees** using **Griffe** (`griffe.load()`)
  5. Runs `griffe.find_breaking_changes()` to compare the two API trees and detect removals, renames, signature changes, etc.
  6. Reports each breakage with its **kind**, **location** (dot-path to the changed symbol), and **reason**
- Alongside Griffe, Python's built-in **`ast`** module scans the repo's `.py` files to find where each dependency is imported or called, giving precise per-file, per-line usage information

### 🧠 AI-Powered Migration Fixes (Groq + Astra DB)
- Real changelog data is fetched from **PyPI** and **GitHub Releases** for broken packages
- Changelogs are stored in **Astra DB** (DataStax) as vector embeddings using **NVIDIA NV-Embed-QA** via AstraDB's server-side `$vectorize` — no local embedding model needed
- When an AI fix is requested, Dependency Analyser performs a **semantic similarity search** in Astra DB to retrieve the most relevant changelog entries for that breakage
- The breakage details + changelog context + user's code snippet are sent to **Groq (LLaMA-3.3-70b-versatile)** which returns a concrete, minimal code fix in "old line → new line" format
- The AI is instructed to always give a working fix — never ask for more information

### 🔀 Pull Request Creation
- For any detected breaking change, click **"Create PR"** to:
  1. Clone the repo to a temporary directory
  2. Create a new branch named `parsec/fix-{package}-{version}`
  3. Write a `parsec_migration_{package}.md` file with the breaking change details and the AI-suggested fix
  4. Commit and push the branch
  5. Open a GitHub Pull Request via the GitHub REST API with a formatted PR body including a summary table, the AI fix, and a list of affected files
- The real repo is cloned fresh into a temp directory — your working copy is never touched

### ⎇ Git Graph Visualization
- Clones the repository (shallow, last 50 commits) into a temp directory
- Parses `git log --graph --oneline --decorate --all` output into structured JSON
- Renders a colour-coded **SVG commit graph** in the browser with branch lanes
- Each branch gets a unique colour from a fixed palette; branch labels are shown as pills
- Shows commit hashes, messages, and branch tags per commit row
- Raw git log is also available in a collapsible `<details>` element

### ⚡ Git Operations (Safe, Isolated)
- From the Git Graph page, run **Rebase**, **Merge**, or **Cherry-pick** against any branch
- All operations run in a **fresh shallow clone** (`--depth 100`) in a temp directory — your real repo is never modified
- Results show: before/after `git log --graph` output, diff stat summary, raw command output, and a conflict detection flag
- Cherry-pick uses the latest commit from the source branch

### 📄 PDF Report Export
- Downloads a formatted **A4 PDF** generated by **ReportLab**
- Includes: title, repo info, generation timestamp, summary table (dep count, breaking changes count, AI fixes count), full dependency list table, and per-package breaking change section with AI fix text
- AI fixes are generated concurrently for all packages at PDF download time via `asyncio.gather`

---

## 🛠️ Tech Stack

### Backend
| Layer | Technology |
|---|---|
| Web framework | FastAPI (Python 3.13) |
| ASGI server | Uvicorn |
| GitHub OAuth | httpx + python-jose (JWT) |
| Dependency parsing | Custom regex parser + `toml` |
| AST analysis | Python built-in `ast` module |
| Breaking change detection | **Griffe** |
| Package installation (isolated) | **uv** (`uv pip install --target`) |
| Vector database | **Astra DB** (DataStax) via `astrapy` |
| Embeddings | NVIDIA NV-Embed-QA (server-side via AstraDB `$vectorize`) |
| AI / LLM | **Groq** — LLaMA-3.3-70b-versatile |
| PDF generation | ReportLab |
| HTTP client | httpx |
| Env management | python-dotenv |

### Frontend
| Layer | Technology |
|---|---|
| UI framework | React 18 |
| Build tool | Vite |
| HTTP client | axios |
| Auth | jwt-decode |
| Git graph rendering | Custom SVG (no third-party graph lib) |
| Styling | Vanilla CSS (dark theme) |

---

## ⚙️ Environment Variables

Copy `.env.example` to `.env` and fill in:

```env
GITHUB_CLIENT_ID=your_github_oauth_app_client_id
GITHUB_CLIENT_SECRET=your_github_oauth_app_client_secret
JWT_SECRET_KEY=any_long_random_string
FRONTEND_URL=http://localhost:3001

# Required for Astra DB vector store
ASTRA_DB_APPLICATION_TOKEN=AstraCS:...
ASTRA_DB_API_ENDPOINT=https://your-db-id.apps.astra.datastax.com

# Required for AI fixes via Groq
GROQ_API_KEY=gsk_...

# Optional — used to fetch GitHub release notes for changelogs
GITHUB_TOKEN=ghp_...
```

> **Note:** The app works without AstraDB and Groq, but the AI fix and vector search features will be disabled gracefully.

---

## 🚀 Running Locally

### Backend

```bash
# From the project root
pip install -r requirements.txt
# or using uv:
uv pip install -r requirements.txt

python -m uvicorn api.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend will be available at `http://localhost:3001` (configured in `vite.config.js`).

---

## 📡 API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/auth/github/login` | Redirect to GitHub OAuth |
| `GET` | `/auth/github/callback` | OAuth callback, issues JWT, redirects to frontend |
| `GET` | `/auth/me` | Decode JWT and return user info |
| `POST` | `/analyze/repo/tree` | Get repo file tree and classify files |
| `POST` | `/analyze/repo/dependencies` | Parse all dependency files in repo |
| `POST` | `/analyze/repo/usage` | AST-scan Python files for package import/call usage |
| `POST` | `/analyze/griffe` | Run Griffe breaking change analysis on given packages |
| `POST` | `/analyze/full` | Run full pipeline: deps + usage + Griffe + Astra store |
| `POST` | `/ai/fix` | Generate AI migration fix for a breakage using Groq + Astra |
| `POST` | `/astra/query` | Semantic similarity search in Astra DB |
| `POST` | `/git/visualize` | Clone repo and return git commit graph as JSON |
| `POST` | `/git/operation` | Run rebase/merge/cherry-pick in isolated clone |
| `POST` | `/pr/create` | Create a GitHub PR with migration guide |
| `POST` | `/report/download/pdf` | Generate and download PDF analysis report |

---

## 🔒 Security Notes

- Git operations and PR creation clone the repo into a **system temp directory** that is deleted after each request — the server's filesystem is not permanently modified
- Griffe package installs also use **isolated `--target` directories** in temp — the live virtual environment is never touched
- GitHub tokens are stored only in the JWT (HTTP-only in session, never logged)
