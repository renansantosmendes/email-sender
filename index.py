"""Vercel entry point: exposes the FastAPI application as ``app``.

Vercel detects this module and runs ``app`` as a serverless function, and
``vercel.json`` sends every path to it. Locally, run the same application
with ``uv run uvicorn api:app --reload``.
"""

from api import app

__all__ = ["app"]
