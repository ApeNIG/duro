"""Duro Dashboard API - FastAPI backend for real-time memory monitoring."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import stats, artifacts, stream, reviews, actions, insights, episodes, skills, incidents, search, graph, promotions, suggestions, security, health_maint, changes, emergence


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    print("Duro Dashboard API starting...")
    yield
    print("Duro Dashboard API shutting down...")


app = FastAPI(
    title="Duro Dashboard API",
    description="Real-time monitoring for the Duro memory system",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS for frontend (allow multiple ports for dev)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:5176",
        "http://localhost:5177",
        "http://localhost:5178",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
        "http://127.0.0.1:5176",
        "http://127.0.0.1:5177",
        "http://127.0.0.1:5178",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(stats.router, prefix="/api", tags=["stats"])
app.include_router(artifacts.router, prefix="/api", tags=["artifacts"])
app.include_router(stream.router, prefix="/api/stream", tags=["stream"])
app.include_router(reviews.router, prefix="/api", tags=["reviews"])
app.include_router(actions.router, prefix="/api/actions", tags=["actions"])
app.include_router(insights.router, prefix="/api", tags=["insights"])
app.include_router(episodes.router, prefix="/api", tags=["episodes"])
app.include_router(skills.router, prefix="/api", tags=["skills"])
app.include_router(incidents.router, prefix="/api", tags=["incidents"])
app.include_router(search.router, prefix="/api", tags=["search"])
app.include_router(graph.router, prefix="/api", tags=["graph"])
app.include_router(promotions.router, prefix="/api", tags=["promotions"])
app.include_router(suggestions.router, prefix="/api", tags=["suggestions"])
app.include_router(security.router, prefix="/api", tags=["security"])
app.include_router(health_maint.router, prefix="/api", tags=["health"])
app.include_router(changes.router, prefix="/api", tags=["changes"])
app.include_router(emergence.router, prefix="/api", tags=["emergence"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Duro Dashboard API", "version": "1.0.0"}

