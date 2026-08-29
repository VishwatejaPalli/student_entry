"""
Students Router — Student management CRUD.

Routes:
  GET    /admin/students          → Student management page
  POST   /api/students            → Add single student
  PUT    /api/students/{id}       → Edit student
  POST   /api/students/import     → Import from Excel/CSV
  GET    /api/students/search     → Search students
  GET    /api/students            → List all students (paginated)
"""

import csv
import io
from fastapi import APIRouter, Request, Query, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from typing import Optional

from database import get_db
from models import StudentCreate, StudentUpdate

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/admin/students", response_class=HTMLResponse)
async def students_page(request: Request):
    """Student management page."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM students WHERE active = 1 ORDER BY roll_no LIMIT 100"
        )
        students = [dict(r) for r in await cursor.fetchall()]

        cursor = await db.execute("SELECT COUNT(*) as cnt FROM students WHERE active = 1")
        row = await cursor.fetchone()
        total = row["cnt"]

        return templates.TemplateResponse(request, name="admin/students.html", context={
            "students": students,
            "total": total,
        })
    finally:
        await db.close()


@router.get("/api/students")
async def api_list_students(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    search: Optional[str] = None,
):
    """List students with optional search."""
    db = await get_db()
    try:
        conditions = ["active = 1"]
        params = []

        if search:
            conditions.append("(roll_no LIKE ? OR name LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])

        where = "WHERE " + " AND ".join(conditions)

        cursor = await db.execute(f"SELECT COUNT(*) as cnt FROM students {where}", params)
        row = await cursor.fetchone()
        total = row["cnt"]

        offset = (page - 1) * per_page
        cursor = await db.execute(
            f"""SELECT * FROM students {where}
                ORDER BY roll_no
                LIMIT ? OFFSET ?""",
            params + [per_page, offset],
        )
        students = [dict(r) for r in await cursor.fetchall()]

        return JSONResponse({
            "students": students,
            "total": total,
            "page": page,
            "pages": (total + per_page - 1) // per_page,
        })
    finally:
        await db.close()


@router.get("/api/students/search")
async def api_search_students(q: str = Query("", min_length=1)):
    """Search students by roll number or name."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT id, roll_no, name, department, year
               FROM students
               WHERE active = 1 AND (roll_no LIKE ? OR name LIKE ?)
               ORDER BY roll_no
               LIMIT 20""",
            (f"%{q.upper()}%", f"%{q}%"),
        )
        results = [dict(r) for r in await cursor.fetchall()]
        return JSONResponse(content=results)
    finally:
        await db.close()


@router.post("/api/students")
async def api_create_student(data: StudentCreate):
    """Add a single student."""
    db = await get_db()
    try:
        roll_no = data.roll_no.strip().upper()

        # Check for duplicate
        cursor = await db.execute(
            "SELECT id FROM students WHERE roll_no = ?", (roll_no,)
        )
        existing = await cursor.fetchone()
        if existing:
            return JSONResponse(
                {"error": f"Student {roll_no} already exists"},
                status_code=409,
            )

        await db.execute(
            """INSERT INTO students (roll_no, name, department, section, year)
               VALUES (?, ?, ?, ?, ?)""",
            (roll_no, data.name, data.department, data.section, data.year),
        )
        await db.commit()
        return JSONResponse({"success": True, "roll_no": roll_no}, status_code=201)
    finally:
        await db.close()


@router.put("/api/students/{student_id}")
async def api_update_student(student_id: int, data: StudentUpdate):
    """Update student details."""
    db = await get_db()
    try:
        updates = []
        params = []

        if data.name is not None:
            updates.append("name = ?")
            params.append(data.name)
        if data.department is not None:
            updates.append("department = ?")
            params.append(data.department)
        if data.section is not None:
            updates.append("section = ?")
            params.append(data.section)
        if data.year is not None:
            updates.append("year = ?")
            params.append(data.year)
        if data.active is not None:
            updates.append("active = ?")
            params.append(1 if data.active else 0)

        if not updates:
            return JSONResponse({"error": "No fields to update"}, status_code=400)

        params.append(student_id)
        await db.execute(
            f"UPDATE students SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        await db.commit()
        return JSONResponse({"success": True})
    finally:
        await db.close()


@router.post("/api/students/import")
async def api_import_students(file: UploadFile = File(...)):
    """
    Import students from CSV or Excel.
    Expected columns: roll_no, name, department, section, year
    """
    db = await get_db()
    try:
        content = await file.read()

        if file.filename and file.filename.endswith(('.xlsx', '.xls')):
            # Excel import
            try:
                from openpyxl import load_workbook
                wb = load_workbook(io.BytesIO(content))
                ws = wb.active
                rows_iter = ws.iter_rows(values_only=True)
                header = [str(h).strip().lower() if h else "" for h in next(rows_iter)]
                data_rows = []
                for row in rows_iter:
                    data_rows.append({header[i]: str(row[i]).strip() if row[i] else "" for i in range(len(header))})
            except Exception as e:
                return JSONResponse({"error": f"Failed to parse Excel: {str(e)}"}, status_code=400)
        else:
            # CSV import
            try:
                text = content.decode("utf-8")
                reader = csv.DictReader(io.StringIO(text))
                data_rows = []
                for row in reader:
                    cleaned = {k.strip().lower(): v.strip() for k, v in row.items()}
                    data_rows.append(cleaned)
            except Exception as e:
                return JSONResponse({"error": f"Failed to parse CSV: {str(e)}"}, status_code=400)

        imported = 0
        skipped = 0
        errors_list = []

        for row in data_rows:
            roll_no = row.get("roll_no", row.get("roll no", row.get("rollno", ""))).strip().upper()
            if not roll_no:
                skipped += 1
                continue

            name = row.get("name", row.get("student name", ""))
            department = row.get("department", row.get("dept", ""))
            section = row.get("section", "")
            year = row.get("year", "")

            try:
                cursor = await db.execute(
                    "SELECT id FROM students WHERE roll_no = ?", (roll_no,)
                )
                existing = await cursor.fetchone()

                if existing:
                    # Update existing
                    await db.execute(
                        """UPDATE students SET name = ?, department = ?, section = ?, year = ?
                           WHERE roll_no = ?""",
                        (name, department, section, year, roll_no),
                    )
                else:
                    await db.execute(
                        """INSERT INTO students (roll_no, name, department, section, year)
                           VALUES (?, ?, ?, ?, ?)""",
                        (roll_no, name, department, section, year),
                    )
                imported += 1
            except Exception as e:
                errors_list.append(f"{roll_no}: {str(e)}")
                skipped += 1

        await db.commit()

        return JSONResponse({
            "success": True,
            "imported": imported,
            "skipped": skipped,
            "errors": errors_list[:10],  # Limit error list
        })
    finally:
        await db.close()
