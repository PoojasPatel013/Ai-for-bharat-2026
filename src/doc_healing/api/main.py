"""Main FastAPI application."""

from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(
    title="Self-Healing Documentation Engine",
    description="A GitHub/GitLab bot that validates and auto-corrects code snippets in documentation",
    version="0.1.0",
)


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {"message": "Self-Healing Documentation Engine API", "version": "0.1.0"}


@app.get("/health")
async def health() -> JSONResponse:
    """Health check endpoint."""
    return JSONResponse(content={"status": "healthy"}, status_code=200)
