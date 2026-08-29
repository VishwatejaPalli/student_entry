"""
Export Router — Excel and CSV export endpoints.

Routes:
  GET  /admin/export      → Export page
  GET  /api/export/excel   → Download Excel
  GET  /api/export/csv     → Download CSV
"""

from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.templating import Jinja2Templates
from typing import Optional
from datetime import datetime
import io

from database import get_db
from services.export_service import export_excel, export_csv

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/admin/export", response_class=HTMLResponse)
async def export_page(request: Request):
    """Export page with filtering options."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM forms ORDER BY name")
        forms = [dict(r) for r in await cursor.fetchall()]

        return templates.TemplateResponse(request, name="admin/export.html", context={
            "forms": forms,
        })
    finally:
        await db.close()


@router.get("/api/export/excel")
async def api_export_excel(
    form_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    """Download entry records as Excel file."""
    db = await get_db()
    try:
        data = await export_excel(db, form_id, date_from, date_to)
        filename = f"entry_records_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx"

        return Response(
            content=data,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    finally:
        await db.close()


@router.get("/api/export/csv")
async def api_export_csv(
    form_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    """Download entry records as CSV file."""
    db = await get_db()
    try:
        data = await export_csv(db, form_id, date_from, date_to)
        filename = f"entry_records_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"

        return Response(
            content=data.encode("utf-8"),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    finally:
        await db.close()


@router.get("/api/export/session/{session_id}/excel")
async def api_export_session_excel(session_id: int):
    """Download attendance sheet for a specific class session."""
    from services.export_service import export_session_excel
    db = await get_db()
    try:
        data = await export_session_excel(db, session_id)
        filename = f"session_{session_id}_attendance_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return Response(
            content=data,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    finally:
        await db.close()
