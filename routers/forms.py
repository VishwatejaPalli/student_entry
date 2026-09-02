"""
Forms Router — Admin form builder CRUD.

Routes:
  GET    /admin/forms                        → List all forms
  GET    /admin/forms/builder                → Form builder page (new)
  GET    /admin/forms/builder/{id}           → Form builder page (edit)
  GET    /admin/forms/preview/{id}           → Live preview
  POST   /api/forms                          → Create form
  PUT    /api/forms/{id}                     → Update form metadata
  POST   /api/forms/{id}/fields              → Add field
  PUT    /api/forms/{id}/fields/{field_id}   → Update field
  DELETE /api/forms/{id}/fields/{field_id}   → Soft-delete field
  PUT    /api/forms/{id}/fields/reorder      → Reorder fields
  PUT    /api/forms/{id}/activate            → Set as active form
  GET    /api/forms/{id}                     → Get form with fields (JSON)
"""

import json
from datetime import datetime
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from database import get_db
from models import FormCreate, FormUpdate, FieldCreate, FieldUpdate, FieldReorder
from services.form_engine import render_form_html

router = APIRouter()
templates = Jinja2Templates(directory="templates")


# ── Pages ─────────────────────────────────────────────────────────

@router.get("/admin/forms", response_class=HTMLResponse)
async def forms_list_page(request: Request):
    """List all forms."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM forms ORDER BY created_at DESC")
        forms = [dict(r) for r in await cursor.fetchall()]
        return templates.TemplateResponse(request, name="admin/form-builder.html", context={
            "forms": forms,
            "mode": "list",
        })
    finally:
        await db.close()


@router.get("/admin/forms/builder", response_class=HTMLResponse)
async def form_builder_new(request: Request):
    """Form builder — create new form."""
    return templates.TemplateResponse(request, name="admin/form-builder.html", context={
        "form": None,
        "fields": [],
        "mode": "builder",
    })


@router.get("/admin/forms/builder/{form_id}", response_class=HTMLResponse)
async def form_builder_edit(request: Request, form_id: int):
    """Form builder — edit existing form."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM forms WHERE id = ?", (form_id,))
        form = await cursor.fetchone()
        if not form:
            return HTMLResponse("Form not found", status_code=404)

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

        return templates.TemplateResponse(request, name="admin/form-builder.html", context={
            "form": dict(form),
            "fields": fields,
            "mode": "builder",
        })
    finally:
        await db.close()


@router.get("/admin/forms/preview/{form_id}", response_class=HTMLResponse)
async def form_preview(request: Request, form_id: int):
    """Live preview of a form."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM forms WHERE id = ?", (form_id,))
        form = await cursor.fetchone()
        if not form:
            return HTMLResponse("Form not found", status_code=404)

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

        form_html = render_form_html(fields)

        return templates.TemplateResponse(request, name="admin/form-preview.html", context={
            "form": dict(form),
            "form_html": form_html,
        })
    finally:
        await db.close()


# ── API ───────────────────────────────────────────────────────────

@router.get("/api/forms/{form_id}")
async def api_get_form(form_id: int):
    """Get a form with all its fields."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM forms WHERE id = ?", (form_id,))
        form = await cursor.fetchone()
        if not form:
            return JSONResponse({"error": "Form not found"}, status_code=404)

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

        result = dict(form)
        result["fields"] = fields

        return JSONResponse(content=result)
    finally:
        await db.close()


@router.post("/api/forms")
async def api_create_form(data: FormCreate):
    """Create a new form."""
    db = await get_db()
    try:
        now = datetime.utcnow().isoformat()
        cursor = await db.execute(
            """INSERT INTO forms (name, description, version, active, created_at, updated_at)
               VALUES (?, ?, 1, 0, ?, ?)""",
            (data.name, data.description, now, now),
        )
        await db.commit()
        form_id = cursor.lastrowid
        return JSONResponse({"success": True, "id": form_id}, status_code=201)
    finally:
        await db.close()


@router.put("/api/forms/{form_id}")
async def api_update_form(form_id: int, data: FormUpdate):
    """Update form metadata."""
    db = await get_db()
    try:
        updates = []
        params = []
        if data.name is not None:
            updates.append("name = ?")
            params.append(data.name)
        if data.description is not None:
            updates.append("description = ?")
            params.append(data.description)

        if not updates:
            return JSONResponse({"error": "No fields to update"}, status_code=400)

        updates.append("updated_at = ?")
        params.append(datetime.utcnow().isoformat())
        updates.append("version = version + 1")

        params.append(form_id)
        await db.execute(
            f"UPDATE forms SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        await db.commit()
        return JSONResponse({"success": True})
    finally:
        await db.close()


@router.post("/api/forms/{form_id}/fields")
async def api_add_field(form_id: int, data: FieldCreate):
    """Add a field to a form."""
    db = await get_db()
    try:
        # Get max position
        if data.position is None:
            cursor = await db.execute(
                "SELECT COALESCE(MAX(position), 0) + 1 as next_pos FROM form_fields WHERE form_id = ? AND is_active = 1",
                (form_id,),
            )
            row = await cursor.fetchone()
            position = row["next_pos"]
        else:
            position = data.position

        now = datetime.utcnow().isoformat()
        cursor = await db.execute(
            """INSERT INTO form_fields
               (form_id, field_type, field_name, label, required, position, configuration, is_active, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)""",
            (
                form_id,
                data.field_type,
                data.field_name,
                data.label,
                1 if data.required else 0,
                position,
                json.dumps(data.configuration),
                now,
            ),
        )
        await db.commit()
        field_id = cursor.lastrowid

        # Update form timestamp
        await db.execute(
            "UPDATE forms SET updated_at = ?, version = version + 1 WHERE id = ?",
            (now, form_id),
        )
        await db.commit()

        return JSONResponse({"success": True, "id": field_id, "position": position}, status_code=201)
    finally:
        await db.close()


@router.put("/api/forms/{form_id}/fields/{field_id}")
async def api_update_field(form_id: int, field_id: int, data: FieldUpdate):
    """Update a field."""
    db = await get_db()
    try:
        updates = []
        params = []

        if data.field_type is not None:
            updates.append("field_type = ?")
            params.append(data.field_type)
        if data.field_name is not None:
            updates.append("field_name = ?")
            params.append(data.field_name)
        if data.label is not None:
            updates.append("label = ?")
            params.append(data.label)
        if data.required is not None:
            updates.append("required = ?")
            params.append(1 if data.required else 0)
        if data.position is not None:
            updates.append("position = ?")
            params.append(data.position)
        if data.configuration is not None:
            updates.append("configuration = ?")
            params.append(json.dumps(data.configuration))

        if not updates:
            return JSONResponse({"error": "No fields to update"}, status_code=400)

        params.extend([form_id, field_id])
        await db.execute(
            f"UPDATE form_fields SET {', '.join(updates)} WHERE form_id = ? AND id = ?",
            params,
        )

        # Update form timestamp
        now = datetime.utcnow().isoformat()
        await db.execute(
            "UPDATE forms SET updated_at = ?, version = version + 1 WHERE id = ?",
            (now, form_id),
        )
        await db.commit()
        return JSONResponse({"success": True})
    finally:
        await db.close()


@router.delete("/api/forms/{form_id}/fields/{field_id}")
async def api_delete_field(form_id: int, field_id: int):
    """Soft-delete a field (set is_active = 0)."""
    db = await get_db()
    try:
        await db.execute(
            "UPDATE form_fields SET is_active = 0 WHERE form_id = ? AND id = ?",
            (form_id, field_id),
        )

        now = datetime.utcnow().isoformat()
        await db.execute(
            "UPDATE forms SET updated_at = ?, version = version + 1 WHERE id = ?",
            (now, form_id),
        )
        await db.commit()
        return JSONResponse({"success": True})
    finally:
        await db.close()


@router.put("/api/forms/{form_id}/fields/reorder")
async def api_reorder_fields(form_id: int, data: FieldReorder):
    """Reorder fields by providing an ordered list of field IDs."""
    db = await get_db()
    try:
        for position, field_id in enumerate(data.field_ids, 1):
            await db.execute(
                "UPDATE form_fields SET position = ? WHERE id = ? AND form_id = ?",
                (position, field_id, form_id),
            )

        now = datetime.utcnow().isoformat()
        await db.execute(
            "UPDATE forms SET updated_at = ? WHERE id = ?",
            (now, form_id),
        )
        await db.commit()
        return JSONResponse({"success": True})
    finally:
        await db.close()


@router.put("/api/forms/{form_id}/activate")
async def api_activate_form(form_id: int):
    """Set this form as the active form (deactivate all others)."""
    db = await get_db()
    try:
        await db.execute("UPDATE forms SET active = 0")
        await db.execute("UPDATE forms SET active = 1 WHERE id = ?", (form_id,))
        await db.commit()
        return JSONResponse({"success": True, "message": "Form activated"})
    finally:
        await db.close()


@router.delete("/api/forms/{form_id}")
async def api_delete_form(form_id: int):
    """Delete a form and its form fields."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT id, name, active FROM forms WHERE id = ?", (form_id,))
        form = await cursor.fetchone()
        if not form:
            return JSONResponse({"error": "Form not found"}, status_code=404)

        # Check total forms count
        cursor_cnt = await db.execute("SELECT COUNT(*) as cnt FROM forms")
        cnt_row = await cursor_cnt.fetchone()
        total_forms = cnt_row["cnt"]

        if total_forms <= 1:
            return JSONResponse(
                {"error": "Cannot delete the only remaining form. Create another form first."},
                status_code=400
            )

        if form["active"] == 1:
            return JSONResponse(
                {"error": "Cannot delete the active form. Please set another form as Active first."},
                status_code=400
            )

        # Clean up records referencing this form and their record_values
        cursor_rec = await db.execute("SELECT id FROM records WHERE form_id = ?", (form_id,))
        rec_rows = await cursor_rec.fetchall()
        for rec in rec_rows:
            await db.execute("DELETE FROM record_values WHERE record_id = ?", (rec["id"],))
        await db.execute("DELETE FROM records WHERE form_id = ?", (form_id,))

        # Delete form fields and form
        await db.execute("DELETE FROM form_fields WHERE form_id = ?", (form_id,))
        await db.execute("DELETE FROM forms WHERE id = ?", (form_id,))
        await db.commit()

        return JSONResponse({
            "success": True,
            "message": f"Form '{form['name']}' deleted successfully."
        })
    finally:
        await db.close()
