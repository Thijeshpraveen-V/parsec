from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes.auth import router as auth_router
from api.routes.repo import router as repo_router
from api.routes.analysis import router as analysis_router
from api.routes.git import router as git_router
from dotenv import load_dotenv
from pathlib import Path
from api.routes.report import router as report_router
from api.routes.pr import router as pr_router




load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

app = FastAPI(title="Dependency Analyser")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(repo_router)
app.include_router(analysis_router)
app.include_router(git_router)
app.include_router(report_router)
app.include_router(pr_router)

@app.get("/")
async def root():
    return {"message": "Dependency Analyser API is running"}
