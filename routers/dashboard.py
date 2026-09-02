"""
Dashboard Router — Live dashboard with stats, currently inside roster, and records.

Routes:
  GET  /dashboard              → Dashboard page
  GET  /api/dashboard/stats    → JSON stats
  GET  /api/dashboard/inside   → JSON currently inside students
  GET  /api/dashboard/records  → Paginated records
  POST /api/dashboard/quick-scan → Smart 1-scan auto entry/exit
  GET  /api/records/{id}       → Single record detail
"""

from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from typing import Optional

from database import get_db
from models import RollNoRequest
from services.entry_service import (
    get_dashboard_stats,
    get_records,
    get_record_detail,
    get_active_students_inside,
    identify_student,
    record_exit,
    create_entry,
)
from services.form_engine import get_data_fields

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    """Render the enhanced dashboard page."""
    db = await get_db()
    try:
        stats = await get_dashboard_stats(db)
        inside_students = await get_active_students_inside(db)
        result = await get_records(db, page=1, per_page=50)

        return templates.TemplateResponse(request, name="dashboard.html", context={
            "stats": stats,
            "inside_students": inside_students,
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


@router.get("/api/dashboard/inside")
async def api_dashboard_inside():
    """Get students currently inside the room."""
    db = await get_db()
    try:
        inside = await get_active_students_inside(db)
        return JSONResponse(content={"inside": inside, "count": len(inside)})
    finally:
        await db.close()


@router.post("/api/dashboard/quick-scan")
async def api_dashboard_quick_scan(data: RollNoRequest):
    """Smart single-scan handler: auto-checks out if inside, or auto-checks in if outside."""
    db = await get_db()
    try:
        roll_no = data.roll_no.strip().upper()
        if not roll_no:
            return JSONResponse({"error": "Roll number is required"}, status_code=400)

        student = await identify_student(db, roll_no)

        if student["is_inside"]:
            # Record exit
            exit_res = await record_exit(db, roll_no)
            return JSONResponse({
                "action": "EXIT",
                "message": f"👋 Checked OUT: {student['student_name'] or roll_no} ({exit_res['duration_formatted']})",
                "student": student,
                "exit_details": exit_res,
            })
        else:
            # Get active form
            cursor = await db.execute("SELECT id FROM forms WHERE active = 1 LIMIT 1")
            form = await cursor.fetchone()
            form_id = form["id"] if form else 1

            record_id = await create_entry(db, roll_no, form_id, {}, [])
            return JSONResponse({
                "action": "ENTRY",
                "message": f"✓ Checked IN: {student['student_name'] or roll_no}",
                "record_id": record_id,
                "student": student,
            })
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
