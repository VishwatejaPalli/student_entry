"""
Configurable Room Entry & Data Management System
Main FastAPI Application

Serves:
  - Student entry/exit interface
  - Live dashboard
  - Admin form builder
  - Student management
  - Excel/CSV export
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from database import init_db
from routers import entry, dashboard, forms, students, export, sessions


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Initialize database and seed default data
    await init_db()
    print("✓ Database initialized")
    print("✓ Room Entry System ready at http://0.0.0.0:8000")
    yield
    print("Shutting down...")


app = FastAPI(
    title="Room Entry System",
    description="Configurable Room Entry & Data Management System",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Routers
app.include_router(entry.router)
app.include_router(dashboard.router)
app.include_router(sessions.router)
app.include_router(forms.router)
app.include_router(students.router)
app.include_router(export.router)

