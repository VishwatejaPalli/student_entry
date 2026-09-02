"""
Entry Service — Core business logic for student entry/exit.

Handles:
  - Student identification (lookup + auto-create)
  - Entry creation with custom field values
  - Exit recording with duration calculation
  - Occupancy queries
"""

import json
from datetime import datetime
from typing import Optional
import aiosqlite


async def identify_student(db: aiosqlite.Connection, roll_no: str) -> dict:
    """
    Look up a student by roll number.
    If not found, auto-creates a minimal record.
    Returns student info and current inside/outside status.
    """
    roll_no = roll_no.strip().upper()

    # Find or create student
    cursor = await db.execute(
        "SELECT * FROM students WHERE roll_no = ?", (roll_no,)
    )
    student = await cursor.fetchone()

    if not student:
        await db.execute(
            "INSERT INTO students (roll_no, name) VALUES (?, ?)",
            (roll_no, ""),
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT * FROM students WHERE roll_no = ?", (roll_no,)
        )
        student = await cursor.fetchone()

    # Check if currently inside (has entry but no exit)
    cursor = await db.execute(
        """SELECT id FROM records
           WHERE roll_no = ? AND exit_time IS NULL
           ORDER BY entry_time DESC LIMIT 1""",
        (roll_no,),
    )
    active_record = await cursor.fetchone()

    return {
        "roll_no": student["roll_no"],
        "student_name": student["name"],
        "department": student["department"],
        "year": student["year"],
        "is_inside": active_record is not None,
        "record_id": active_record["id"] if active_record else None,
    }


async def create_entry(
    db: aiosqlite.Connection,
    roll_no: str,
    form_id: int,
    field_values: dict[str, str],
    fields: list[dict],
) -> int:
    """
    Create a new entry record with custom field values.

    Args:
        db: database connection
        roll_no: student roll number
        form_id: active form id
        field_values: dict of field_name -> value
        fields: list of active data field definitions

    Returns:
        The new record ID
    """
    roll_no = roll_no.strip().upper()
    now = datetime.utcnow().isoformat()

    # Ensure student exists in master directory
    cursor_st = await db.execute("SELECT id FROM students WHERE roll_no = ?", (roll_no,))
    if not await cursor_st.fetchone():
        await db.execute("INSERT OR IGNORE INTO students (roll_no, name) VALUES (?, '')", (roll_no,))

    cursor = await db.execute(
        """INSERT INTO records (form_id, roll_no, entry_time, created_at)
           VALUES (?, ?, ?, ?)""",
        (form_id, roll_no, now, now),
    )
    record_id = cursor.lastrowid

    # Store custom field values
    for field in fields:
        fname = field["field_name"]
        if fname in field_values:
            value = field_values[fname]
            # Checkbox: if not submitted, value is "false"
            if field["field_type"] == "checkbox" and not value:
                value = "false"
            await db.execute(
                "INSERT INTO record_values (record_id, field_id, value) VALUES (?, ?, ?)",
                (record_id, field["id"], value),
            )

    await db.commit()
    return record_id


async def record_exit(db: aiosqlite.Connection, roll_no: str) -> Optional[dict]:
    """
    Record exit for a student currently inside.

    Returns:
        Dict with record_id, roll_no, student_name, entry_time, exit_time, duration_minutes,
        duration_formatted, and exit_message; or None if student is not currently inside.
    """
    roll_no = roll_no.strip().upper()
    now = datetime.utcnow()
    now_iso = now.isoformat()

    cursor = await db.execute(
        """SELECT r.id, r.entry_time, COALESCE(s.name, '') as student_name
           FROM records r
           LEFT JOIN students s ON r.roll_no = s.roll_no
           WHERE r.roll_no = ? AND r.exit_time IS NULL
           ORDER BY r.entry_time DESC LIMIT 1""",
        (roll_no,),
    )
    record = await cursor.fetchone()

    if not record:
        return None

    # Calculate duration
    try:
        entry_time = datetime.fromisoformat(record["entry_time"])
        duration = max(0, int((now - entry_time).total_seconds() / 60))
    except Exception:
        duration = 0

    h = duration // 60
    m = duration % 60
    if h > 0:
        duration_formatted = f"{h}h {m}m" if m > 0 else f"{h} hr"
    else:
        duration_formatted = f"{m} mins" if m > 0 else "Just entered (<1 min)"

    student_name = record["student_name"] or roll_no

    await db.execute(
        """UPDATE records SET exit_time = ?, duration_minutes = ?
           WHERE id = ?""",
        (now_iso, duration, record["id"]),
    )
    await db.commit()

    return {
        "record_id": record["id"],
        "roll_no": roll_no,
        "student_name": student_name,
        "entry_time": record["entry_time"],
        "exit_time": now_iso,
        "duration_minutes": duration,
        "duration_formatted": duration_formatted,
        "exit_message": f"Goodbye {student_name}! Your exit has been recorded.",
    }


async def get_dashboard_stats(db: aiosqlite.Connection) -> dict:
    """Get comprehensive dashboard statistics."""
    # Currently inside
    cursor = await db.execute(
        "SELECT COUNT(*) as cnt FROM records WHERE exit_time IS NULL"
    )
    row = await cursor.fetchone()
    currently_inside = row["cnt"]

    # Today's visits
    today = datetime.utcnow().strftime("%Y-%m-%d")
    cursor = await db.execute(
        "SELECT COUNT(*) as cnt FROM records WHERE date(entry_time) = ?",
        (today,),
    )
    row = await cursor.fetchone()
    today_visits = row["cnt"]

    # Total students
    cursor = await db.execute("SELECT COUNT(*) as cnt FROM students WHERE active = 1")
    row = await cursor.fetchone()
    total_students = row["cnt"]

    # Active class sessions
    cursor = await db.execute("SELECT COUNT(*) as cnt FROM class_sessions WHERE status = 'ACTIVE'")
    row = await cursor.fetchone()
    active_sessions = row["cnt"]

    return {
        "currently_inside": currently_inside,
        "today_visits": today_visits,
        "total_students": total_students,
        "active_sessions": active_sessions,
    }


async def get_active_students_inside(db: aiosqlite.Connection) -> list[dict]:
    """Get list of students currently marked as inside with elapsed duration."""
    cursor = await db.execute("""
        SELECT r.id, r.roll_no, r.entry_time,
               COALESCE(s.name, '') as student_name,
               COALESCE(s.department, '') as department,
               COALESCE(s.section, '') as section,
               COALESCE(s.batch, '') as batch
        FROM records r
        LEFT JOIN students s ON r.roll_no = s.roll_no
        WHERE r.exit_time IS NULL
        ORDER BY r.entry_time DESC
    """)
    rows = await cursor.fetchall()

    now = datetime.utcnow()
    result = []
    for r in rows:
        entry_time_str = r["entry_time"]
        duration_mins = 0
        try:
            entry_dt = datetime.fromisoformat(entry_time_str)
            duration_mins = max(0, int((now - entry_dt).total_seconds() // 60))
        except Exception:
            pass

        h = duration_mins // 60
        m = duration_mins % 60
        duration_formatted = f"{h}h {m}m" if h > 0 else f"{m} min" if m > 0 else "Just now"

        result.append({
            "record_id": r["id"],
            "roll_no": r["roll_no"],
            "student_name": r["student_name"] or r["roll_no"],
            "department": r["department"],
            "section": r["section"],
            "batch": r["batch"],
            "entry_time": entry_time_str,
            "duration_minutes": duration_mins,
            "duration_formatted": duration_formatted,
        })
    return result


async def get_records(
    db: aiosqlite.Connection,
    page: int = 1,
    per_page: int = 50,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    roll_no: Optional[str] = None,
) -> dict:
    """Get paginated records with optional filtering."""
    conditions = []
    params = []

    if date_from:
        conditions.append("date(r.entry_time) >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("date(r.entry_time) <= ?")
        params.append(date_to)
    if roll_no:
        conditions.append("r.roll_no LIKE ?")
        params.append(f"%{roll_no.upper()}%")

    where = ""
    if conditions:
        where = "WHERE " + " AND ".join(conditions)

    # Count total
    cursor = await db.execute(
        f"SELECT COUNT(*) as cnt FROM records r {where}", params
    )
    row = await cursor.fetchone()
    total = row["cnt"]

    # Fetch page
    offset = (page - 1) * per_page
    cursor = await db.execute(
        f"""SELECT r.*,
                   COALESCE(s.name, '') as student_name,
                   COALESCE(s.batch, '') as student_batch,
                   cs.session_name, cs.class_name, cs.subject as session_subject, cs.room as session_room
            FROM records r
            LEFT JOIN students s ON r.roll_no = s.roll_no
            LEFT JOIN class_sessions cs ON r.session_id = cs.id
            {where}
            ORDER BY r.entry_time DESC
            LIMIT ? OFFSET ?""",
        params + [per_page, offset],
    )
    rows = await cursor.fetchall()

    records = []
    for row in rows:
        record = dict(row)
        record["status"] = "IN" if row["exit_time"] is None else "OUT"
        record["is_session"] = bool(row["session_id"])
        record["session_name"] = row["session_name"] or ""
        record["class_name"] = row["class_name"] or ""

        # Fetch custom field values
        cursor2 = await db.execute(
            """SELECT rv.value, ff.field_name, ff.label
               FROM record_values rv
               JOIN form_fields ff ON rv.field_id = ff.id
               WHERE rv.record_id = ?""",
            (row["id"],),
        )
        custom_rows = await cursor2.fetchall()
        record["custom_fields"] = {r["label"]: r["value"] for r in custom_rows}
        records.append(record)

    return {
        "records": records,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
    }


async def get_record_detail(db: aiosqlite.Connection, record_id: int) -> Optional[dict]:
    """Get a single record with all custom fields."""
    cursor = await db.execute(
        """SELECT r.*, COALESCE(s.name, '') as student_name
           FROM records r
           LEFT JOIN students s ON r.roll_no = s.roll_no
           WHERE r.id = ?""",
        (record_id,),
    )
    row = await cursor.fetchone()
    if not row:
        return None

    record = dict(row)
    record["status"] = "IN" if row["exit_time"] is None else "OUT"

    cursor = await db.execute(
        """SELECT rv.value, ff.field_name, ff.label, ff.field_type
           FROM record_values rv
           JOIN form_fields ff ON rv.field_id = ff.id
           WHERE rv.record_id = ?
           ORDER BY ff.position""",
        (record_id,),
    )
    custom_rows = await cursor.fetchall()
    record["custom_fields"] = {r["label"]: r["value"] for r in custom_rows}

    return record
