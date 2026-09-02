"""
Entry Router — Handles student entry/exit flow.

Routes:
  GET  /              → Entry page (roll number input)
  POST /api/identify  → Identify student + check status
  GET  /entry/form/{roll_no} → Render dynamic form
  POST /api/entry     → Submit entry
  POST /api/exit      → Record exit
"""

import json
from datetime import datetime
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from database import get_db
from models import IdentifyRequest, EntryRequest, ExitRequest
from services.entry_service import identify_student, create_entry, record_exit
from services.form_engine import render_form_html, validate_submission, get_data_fields

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
async def entry_page(request: Request):
    """Main entry page — roll number input."""
    return templates.TemplateResponse(request, name="entry.html")


@router.post("/api/identify")
async def api_identify(data: IdentifyRequest):
    """Identify a student, check inside status, and auto check-in if form has no required fields."""
    db = await get_db()
    try:
        roll_no = data.roll_no.strip().upper()
        result = await identify_student(db, roll_no)

        # Check active form
        cursor = await db.execute("SELECT id FROM forms WHERE active = 1 LIMIT 1")
        form = await cursor.fetchone()
        form_id = form["id"] if form else 1

        cursor = await db.execute(
            """SELECT COUNT(*) as cnt FROM form_fields
               WHERE form_id = ? AND is_active = 1 AND required = 1""",
            (form_id,),
        )
        row = await cursor.fetchone()
        has_required = row["cnt"] > 0
        result["has_required_fields"] = has_required
        result["form_id"] = form_id

        # If outside and form has no required questions, record entry instantly
        if not result["is_inside"] and not has_required:
            record_id = await create_entry(db, roll_no, form_id, {}, [])
            now_iso = datetime.utcnow().isoformat()
            result["entry_recorded"] = True
            result["record_id"] = record_id
            result["entry_time"] = now_iso
        else:
            result["entry_recorded"] = False

        return JSONResponse(content=result)
    finally:
        await db.close()


@router.get("/entry/form/{roll_no}", response_class=HTMLResponse)
async def entry_form(request: Request, roll_no: str):
    """Render the active form dynamically for a student."""
    db = await get_db()
    try:
        # Get active form
        cursor = await db.execute("SELECT * FROM forms WHERE active = 1 LIMIT 1")
        form = await cursor.fetchone()
        if not form:
            return HTMLResponse("<p>No active form configured. Please contact admin.</p>", status_code=404)

        # Get fields
        cursor = await db.execute(
            """SELECT * FROM form_fields
               WHERE form_id = ? AND is_active = 1
               ORDER BY position""",
            (form["id"],),
        )
        rows = await cursor.fetchall()
        fields = []
        for r in rows:
            f = dict(r)
            f["configuration"] = json.loads(f["configuration"]) if isinstance(f["configuration"], str) else f["configuration"]
            fields.append(f)

        # Get student info
        student = await identify_student(db, roll_no)

        # Render form HTML
        form_html = render_form_html(fields)

        return templates.TemplateResponse(request, name="entry.html", context={
            "roll_no": roll_no,
            "student": student,
            "form": dict(form),
            "form_html": form_html,
            "show_form": True,
        })
    finally:
        await db.close()


@router.post("/api/entry")
async def api_entry(data: EntryRequest):
    """Submit a new entry record."""
    db = await get_db()
    try:
        # Get active form
        cursor = await db.execute("SELECT id FROM forms WHERE active = 1 LIMIT 1")
        form = await cursor.fetchone()
        if not form:
            return JSONResponse({"error": "No active form"}, status_code=400)

        form_id = form["id"]

        # Get data fields for validation
        cursor = await db.execute(
            """SELECT * FROM form_fields
               WHERE form_id = ? AND is_active = 1
               ORDER BY position""",
            (form_id,),
        )
        rows = await cursor.fetchall()
        fields = []
        for r in rows:
            f = dict(r)
            f["configuration"] = json.loads(f["configuration"]) if isinstance(f["configuration"], str) else f["configuration"]
            fields.append(f)

        data_fields = get_data_fields(fields)

        # Validate
        is_valid, errors = validate_submission(data_fields, data.field_values)
        if not is_valid:
            return JSONResponse({"error": "Validation failed", "errors": errors}, status_code=422)

        # Create entry
        record_id = await create_entry(db, data.roll_no, form_id, data.field_values, data_fields)

        return JSONResponse({
            "success": True,
            "record_id": record_id,
            "message": f"Entry recorded for {data.roll_no.upper()}",
        })
    finally:
        await db.close()


@router.post("/api/exit")
async def api_exit(data: ExitRequest):
    """Record exit for a student currently inside."""
    db = await get_db()
    try:
        result = await record_exit(db, data.roll_no)
        if result is None:
            return JSONResponse(
                {"error": f"{data.roll_no.upper()} is not currently marked as inside."},
                status_code=404,
            )
        return JSONResponse({
            "success": True,
            "record_id": result["record_id"],
            "roll_no": result["roll_no"],
            "student_name": result["student_name"],
            "entry_time": result["entry_time"],
            "exit_time": result["exit_time"],
            "duration_minutes": result["duration_minutes"],
            "duration_formatted": result["duration_formatted"],
            "message": result["exit_message"],
        })
    finally:
        await db.close()
