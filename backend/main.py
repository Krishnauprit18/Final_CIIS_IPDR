"""Compatibility entry point for the modular FastAPI application.

Run with: python -m uvicorn main:app --host 127.0.0.1 --port 8000
"""
from app.main import app, create_app, startup_event

__all__ = ["app", "create_app", "startup_event"]
