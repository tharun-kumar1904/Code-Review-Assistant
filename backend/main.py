"""
FastAPI entry point — AI Code Review Assistant.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from database import init_db
from config import get_settings
from routers import analysis, insights, webhooks, rl

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup & shutdown events."""
    await init_db()
    yield


app = FastAPI(
    title="AI Code Review Assistant",
    description="Intelligent GitHub Pull Request Reviewer powered by LLMs",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Prometheus Metrics ───────────────────────────────────────────────────
Instrumentator().instrument(app).expose(app, include_in_schema=False)

# ── Routers ──────────────────────────────────────────────────────────────
app.include_router(analysis.router, prefix="/api", tags=["Analysis"])
app.include_router(insights.router, prefix="/api", tags=["Insights"])
app.include_router(webhooks.router, prefix="/api", tags=["Webhooks"])
app.include_router(rl.router, prefix="/api", tags=["RL Engine"])


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "ai-code-review-assistant"}
