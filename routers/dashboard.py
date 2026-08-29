"""
Dashboard Router — Live dashboard with stats and records.

Routes:
  GET  /dashboard              → Dashboard page
  GET  /api/dashboard/stats    → JSON stats
  GET  /api/dashboard/records  → Paginated records
  GET  /api/records/{id}       → Single record detail
"""

from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from typing import Optional

from database import get_db
from services.entry_service import get_dashboard_stats, get_records, get_record_detail

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    """Render the dashboard page."""
    db = await get_db()
    try:
        stats = await get_dashboard_stats(db)
        result = await get_records(db, page=1, per_page=50)

        return templates.TemplateResponse(request, name="dashboard.html", context={
            "stats": stats,
            "records": result["records"],
            "pagination": {
                "page": result["page"],
                "pages": result["pages"],
                "total": result["total"],
            },
        })
    finally:
        await db.close()


@router.get("/api/dashboard/stats")
async def api_dashboard_stats():
    """Get dashboard statistics as JSON."""
    db = await get_db()
    try:
        stats = await get_dashboard_stats(db)
        return JSONResponse(content=stats)
    finally:
        await db.close()


@router.get("/api/dashboard/records")
async def api_dashboard_records(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    roll_no: Optional[str] = None,
):
    """Get paginated records with optional filtering."""
    db = await get_db()
    try:
        result = await get_records(db, page, per_page, date_from, date_to, roll_no)
        return JSONResponse(content=result)
    finally:
        await db.close()


@router.get("/api/records/{record_id}")
async def api_record_detail(record_id: int):
    """Get full detail of a single record."""
    db = await get_db()
    try:
        record = await get_record_detail(db, record_id)
        if not record:
            return JSONResponse({"error": "Record not found"}, status_code=404)
        return JSONResponse(content=record)
    finally:
        await db.close()
