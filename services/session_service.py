"""
Session Service — Business logic for Class Sessions and Bulk Entry.

Handles:
  - Session creation (live mode vs immediate bulk mode)
  - Student roster generation (class-based, imported, or pasted)
  - Live barcode scan processing with late detection and PC auto-assignment
  - Manual attendance adjustments
  - Session finalization (marking absentees, calculating durations)
  - Roster and class metadata queries
"""

import aiosqlite
from datetime import datetime
from typing import Optional, List, Dict, Any


async def get_classes_list(db: aiosqlite.Connection) -> List[Dict[str, Any]]:
    """
    Get list of unique classes/sections and their students from the database.
    Classes are grouped by `department-section` or department (e.g. 'ECE-A', 'CSE-B').
    """
    cursor = await db.execute("""
        SELECT id, roll_no, name, department, section, year
        FROM students
        WHERE active = 1
        ORDER BY department, section, roll_no
    """)
    rows = await cursor.fetchall()

    classes_map: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        dept = r["department"].strip()
        sec = r["section"].strip()
        if dept and sec:
            class_name = f"{dept}-{sec}"
        elif dept:
            class_name = dept
        else:
            class_name = "General"

        if class_name not in classes_map:
            classes_map[class_name] = []

        classes_map[class_name].append({
            "id": r["id"],
            "roll_no": r["roll_no"],
            "name": r["name"] or r["roll_no"],
            "department": r["department"],
            "section": r["section"],
            "year": r["year"],
        })

    return [
        {"class_name": k, "student_count": len(v), "students": v}
        for k, v in sorted(classes_map.items())
    ]


async def create_session(
    db: aiosqlite.Connection,
    session_data: Dict[str, Any],
    student_roll_nos: List[str],
    is_completed_bulk: bool = False,
    bulk_status: str = "PRESENT",
) -> int:
    """
    Create a new class session and populate its student roster.
    
    If is_completed_bulk is True:
      - Sets status to 'COMPLETED'
      - Sets actual_entry to scheduled_start and actual_exit to scheduled_end
      - Auto-assigns PCs if configured
      - Automatically creates records in the central `records` table for dashboard & analytics.
    """
    now = datetime.utcnow().isoformat()
    status = "COMPLETED" if is_completed_bulk else "ACTIVE"
    ended_at = now if is_completed_bulk else None

    # Calculate scheduled duration in minutes
    try:
        dt_start = datetime.fromisoformat(session_data["scheduled_start"])
        dt_end = datetime.fromisoformat(session_data["scheduled_end"])
        duration = max(0, int((dt_end - dt_start).total_seconds() / 60))
    except Exception:
        duration = 120

    cursor = await db.execute("""
        INSERT INTO class_sessions (
            session_name, class_name, subject, room, faculty,
            scheduled_start, scheduled_end, late_threshold_min,
            pc_strategy, pc_prefix, status, created_at, ended_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        session_data.get("session_name") or f"{session_data.get('class_name', 'Class')} Session",
        session_data.get("class_name", ""),
        session_data.get("subject", ""),
        session_data.get("room", ""),
        session_data.get("faculty", ""),
        session_data["scheduled_start"],
        session_data["scheduled_end"],
        session_data.get("late_threshold_min", 15),
        session_data.get("pc_strategy", "none"),
        session_data.get("pc_prefix", "PC-"),
        status,
        now,
        ended_at,
    ))
    session_id = cursor.lastrowid

    # Get active form for linked record creation
    cursor_f = await db.execute("SELECT id FROM forms WHERE active = 1 LIMIT 1")
    form_row = await cursor_f.fetchone()
    form_id = form_row["id"] if form_row else 1

    # Clean and deduplicate roll numbers
    cleaned_rolls = []
    seen = set()
    for r in student_roll_nos:
        roll = r.strip().upper()
        if roll and roll not in seen:
            seen.add(roll)
            cleaned_rolls.append(roll)

    # Insert students into session_students
    pc_strategy = session_data.get("pc_strategy", "none")
    pc_prefix = session_data.get("pc_prefix", "PC-")

    for idx, roll in enumerate(cleaned_rolls, 1):
        # Look up student name
        cursor_st = await db.execute("SELECT name FROM students WHERE roll_no = ?", (roll,))
        st_row = await cursor_st.fetchone()
        if st_row:
            student_name = st_row["name"]
        else:
            # Auto-register unknown student
            student_name = ""
            await db.execute(
                "INSERT OR IGNORE INTO students (roll_no, name) VALUES (?, ?)",
                (roll, "")
            )

        # PC assignment
        pc_assigned = ""
        if pc_strategy == "auto_sequential":
            pc_assigned = f"{pc_prefix}{str(idx).zfill(2)}"

        if is_completed_bulk:
            student_status = bulk_status
            actual_entry = session_data["scheduled_start"]
            actual_exit = session_data["scheduled_end"]
            rec_duration = duration

            # Create entry in central `records` table
            cursor_rec = await db.execute("""
                INSERT INTO records (form_id, roll_no, session_id, entry_time, exit_time, duration_minutes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (form_id, roll, session_id, actual_entry, actual_exit, rec_duration, now))
            record_id = cursor_rec.lastrowid

            # Save basic custom fields
            if session_data.get("subject") or pc_assigned:
                await _save_session_record_values(db, record_id, form_id, {
                    "purpose": f"Class: {session_data.get('subject', 'Lab')}",
                    "pc_number": pc_assigned,
                    "remarks": f"Class Session #{session_id} - {session_data.get('class_name', '')}"
                })
        else:
            student_status = "PENDING"
            actual_entry = None
            actual_exit = None
            rec_duration = None
            record_id = None

        await db.execute("""
            INSERT INTO session_students (
                session_id, roll_no, student_name, scheduled_status,
                actual_entry, actual_exit, duration_minutes,
                status, pc_assigned, record_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id, roll, student_name, "EXPECTED",
            actual_entry, actual_exit, rec_duration,
            student_status, pc_assigned if is_completed_bulk else "", record_id
        ))

    await db.commit()
    return session_id


async def record_session_scan(
    db: aiosqlite.Connection,
    session_id: int,
    roll_no: str,
    pc_override: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Process a live barcode scan or manual roll entry for an active session.
    
    Determines:
      - PRESENT vs LATE (based on late_threshold_min relative to scheduled_start)
      - PC assignment (if pc_strategy == 'auto_sequential')
      - Creates a linked row in the `records` table
    """
    roll_no = roll_no.strip().upper()
    now_dt = datetime.utcnow()
    now_iso = now_dt.isoformat()

    # Get session details
    cursor = await db.execute("SELECT * FROM class_sessions WHERE id = ?", (session_id,))
    session = await cursor.fetchone()
    if not session:
        return {"success": False, "message": "Session not found", "sound": "warning"}

    if session["status"] != "ACTIVE":
        return {"success": False, "message": f"Session is {session['status']}", "sound": "warning"}

    # Check student roster in this session
    cursor = await db.execute("""
        SELECT * FROM session_students
        WHERE session_id = ? AND roll_no = ?
    """, (session_id, roll_no))
    student_entry = await cursor.fetchone()

    # Determine LATE vs PRESENT
    late_threshold = session["late_threshold_min"]
    status = "PRESENT"
    sound = "success"
    try:
        sched_start = datetime.fromisoformat(session["scheduled_start"])
        minutes_late = int((now_dt - sched_start).total_seconds() / 60)
        if minutes_late > late_threshold:
            status = "LATE"
            sound = "late"
    except Exception:
        pass

    # Determine PC assignment
    pc_assigned = pc_override or ""
    if not pc_assigned and session["pc_strategy"] == "auto_sequential":
        # Find next available PC index
        cursor_pc = await db.execute("""
            SELECT COUNT(*) as cnt FROM session_students
            WHERE session_id = ? AND actual_entry IS NOT NULL
        """, (session_id,))
        pc_cnt_row = await cursor_pc.fetchone()
        next_pc_num = (pc_cnt_row["cnt"] if pc_cnt_row else 0) + 1
        prefix = session["pc_prefix"] or "PC-"
        pc_assigned = f"{prefix}{str(next_pc_num).zfill(2)}"

    # Get active form for records table
    cursor_f = await db.execute("SELECT id FROM forms WHERE active = 1 LIMIT 1")
    form_row = await cursor_f.fetchone()
    form_id = form_row["id"] if form_row else 1

    # Student Name lookup / creation
    cursor_st = await db.execute("SELECT name FROM students WHERE roll_no = ?", (roll_no,))
    st_row = await cursor_st.fetchone()
    if st_row:
        student_name = st_row["name"]
    else:
        student_name = ""
        await db.execute("INSERT OR IGNORE INTO students (roll_no, name) VALUES (?, ?)", (roll_no, ""))

    if student_entry:
        if student_entry["actual_entry"]:
            # Already scanned!
            return {
                "success": True,
                "already_scanned": True,
                "status": student_entry["status"],
                "message": f"{roll_no} already marked {student_entry['status']} at {student_entry['actual_entry'][11:16]} (PC: {student_entry['pc_assigned'] or 'None'})",
                "roll_no": roll_no,
                "student_name": student_entry["student_name"] or roll_no,
                "pc_assigned": student_entry["pc_assigned"],
                "is_walk_in": False,
                "sound": "info",
            }

        # Create record in central records table
        cursor_rec = await db.execute("""
            INSERT INTO records (form_id, roll_no, session_id, entry_time, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (form_id, roll_no, session_id, now_iso, now_iso))
        record_id = cursor_rec.lastrowid

        # Update session_students entry
        await db.execute("""
            UPDATE session_students
            SET actual_entry = ?, status = ?, pc_assigned = ?, record_id = ?
            WHERE id = ?
        """, (now_iso, status, pc_assigned, record_id, student_entry["id"]))

        await _save_session_record_values(db, record_id, form_id, {
            "purpose": f"Class: {session['subject'] or session['class_name']}",
            "pc_number": pc_assigned,
            "remarks": f"Live Session #{session_id}"
        })
        is_walk_in = False
    else:
        # Walk-in student not on original roster
        cursor_rec = await db.execute("""
            INSERT INTO records (form_id, roll_no, session_id, entry_time, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (form_id, roll_no, session_id, now_iso, now_iso))
        record_id = cursor_rec.lastrowid

        await db.execute("""
            INSERT INTO session_students (
                session_id, roll_no, student_name, scheduled_status,
                actual_entry, status, pc_assigned, record_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (session_id, roll_no, student_name, "WALK_IN", now_iso, status, pc_assigned, record_id))

        await _save_session_record_values(db, record_id, form_id, {
            "purpose": f"Class (Walk-in): {session['subject'] or session['class_name']}",
            "pc_number": pc_assigned,
            "remarks": f"Live Session #{session_id}"
        })
        is_walk_in = True

    await db.commit()

    return {
        "success": True,
        "already_scanned": False,
        "status": status,
        "message": f"✓ {roll_no} marked {status}" + (f" (Assigned {pc_assigned})" if pc_assigned else ""),
        "roll_no": roll_no,
        "student_name": student_name or roll_no,
        "pc_assigned": pc_assigned,
        "is_walk_in": is_walk_in,
        "sound": sound,
    }


async def update_student_status(
    db: aiosqlite.Connection,
    session_id: int,
    roll_no: str,
    status: Optional[str] = None,
    pc_assigned: Optional[str] = None,
) -> bool:
    """Manually update student status or PC assignment in a session."""
    roll_no = roll_no.strip().upper()
    updates = []
    params = []

    if status is not None:
        updates.append("status = ?")
        params.append(status)
        if status in ("PRESENT", "LATE"):
            updates.append("actual_entry = COALESCE(actual_entry, datetime('now'))")
        elif status == "ABSENT":
            updates.append("actual_entry = NULL")
            updates.append("actual_exit = NULL")

    if pc_assigned is not None:
        updates.append("pc_assigned = ?")
        params.append(pc_assigned)

    if not updates:
        return False

    params.extend([session_id, roll_no])
    await db.execute(
        f"UPDATE session_students SET {', '.join(updates)} WHERE session_id = ? AND roll_no = ?",
        params
    )
    await db.commit()
    return True


async def end_session(db: aiosqlite.Connection, session_id: int) -> Dict[str, Any]:
    """
    Finalize an active session:
      - Any students still PENDING become ABSENT
      - Computes duration for PRESENT and LATE students
      - Updates linked `records` with exit_time and duration
      - Sets session status to COMPLETED
    """
    now = datetime.utcnow()
    now_iso = now.isoformat()

    # Mark remaining PENDING as ABSENT
    await db.execute("""
        UPDATE session_students
        SET status = 'ABSENT'
        WHERE session_id = ? AND status = 'PENDING'
    """, (session_id,))

    # Set exit time and calculate duration for PRESENT/LATE students who lack exit time
    cursor = await db.execute("""
        SELECT id, actual_entry, record_id
        FROM session_students
        WHERE session_id = ? AND actual_entry IS NOT NULL AND actual_exit IS NULL
    """, (session_id,))
    attended_students = await cursor.fetchall()

    for s in attended_students:
        try:
            entry_dt = datetime.fromisoformat(s["actual_entry"])
            dur = max(0, int((now - entry_dt).total_seconds() / 60))
        except Exception:
            dur = 60

        await db.execute("""
            UPDATE session_students
            SET actual_exit = ?, duration_minutes = ?
            WHERE id = ?
        """, (now_iso, dur, s["id"]))

        if s["record_id"]:
            await db.execute("""
                UPDATE records
                SET exit_time = ?, duration_minutes = ?
                WHERE id = ?
            """, (now_iso, dur, s["record_id"]))

    # Update session status
    await db.execute("""
        UPDATE class_sessions
        SET status = 'COMPLETED', ended_at = ?
        WHERE id = ?
    """, (now_iso, session_id))

    await db.commit()

    return await get_session_details(db, session_id)


async def get_active_sessions(db: aiosqlite.Connection) -> List[Dict[str, Any]]:
    """List all currently active sessions."""
    cursor = await db.execute("""
        SELECT cs.*,
               COUNT(ss.id) as total_students,
               SUM(CASE WHEN ss.status IN ('PRESENT', 'LATE') THEN 1 ELSE 0 END) as present_count,
               SUM(CASE WHEN ss.status = 'ABSENT' THEN 1 ELSE 0 END) as absent_count,
               SUM(CASE WHEN ss.status = 'PENDING' THEN 1 ELSE 0 END) as pending_count
        FROM class_sessions cs
        LEFT JOIN session_students ss ON cs.id = ss.session_id
        WHERE cs.status = 'ACTIVE'
        GROUP BY cs.id
        ORDER BY cs.scheduled_start DESC
    """)
    return [dict(r) for r in await cursor.fetchall()]


async def get_all_sessions(
    db: aiosqlite.Connection,
    limit: int = 50,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """List historical and active sessions."""
    cursor = await db.execute("""
        SELECT cs.*,
               COUNT(ss.id) as total_students,
               SUM(CASE WHEN ss.status IN ('PRESENT', 'LATE') THEN 1 ELSE 0 END) as present_count,
               SUM(CASE WHEN ss.status = 'ABSENT' THEN 1 ELSE 0 END) as absent_count,
               SUM(CASE WHEN ss.status = 'PENDING' THEN 1 ELSE 0 END) as pending_count
        FROM class_sessions cs
        LEFT JOIN session_students ss ON cs.id = ss.session_id
        GROUP BY cs.id
        ORDER BY cs.created_at DESC
        LIMIT ? OFFSET ?
    """, (limit, offset))
    return [dict(r) for r in await cursor.fetchall()]


async def get_session_details(
    db: aiosqlite.Connection,
    session_id: int
) -> Optional[Dict[str, Any]]:
    """Get full details of a session including student roster."""
    cursor = await db.execute("SELECT * FROM class_sessions WHERE id = ?", (session_id,))
    session = await cursor.fetchone()
    if not session:
        return None

    result = dict(session)

    # Get student roster
    cursor_st = await db.execute("""
        SELECT ss.*, COALESCE(s.name, ss.student_name, '') as student_name
        FROM session_students ss
        LEFT JOIN students s ON ss.roll_no = s.roll_no
        WHERE ss.session_id = ?
        ORDER BY
            CASE ss.status
                WHEN 'PRESENT' THEN 1
                WHEN 'LATE' THEN 2
                WHEN 'PENDING' THEN 3
                WHEN 'ABSENT' THEN 4
                ELSE 5
            END,
            ss.roll_no
    """, (session_id,))
    students = [dict(r) for r in await cursor_st.fetchall()]

    result["students"] = students
    result["total_students"] = len(students)
    result["present_count"] = sum(1 for s in students if s["status"] in ("PRESENT", "LATE"))
    result["late_count"] = sum(1 for s in students if s["status"] == "LATE")
    result["absent_count"] = sum(1 for s in students if s["status"] == "ABSENT")
    result["pending_count"] = sum(1 for s in students if s["status"] == "PENDING")

    return result


async def _save_session_record_values(
    db: aiosqlite.Connection,
    record_id: int,
    form_id: int,
    values: Dict[str, str]
):
    """Helper to attach Purpose and PC custom fields to records table."""
    cursor = await db.execute("""
        SELECT id, field_name FROM form_fields
        WHERE form_id = ? AND is_active = 1
    """, (form_id,))
    fields = await cursor.fetchall()
    field_map = {f["field_name"]: f["id"] for f in fields}

    for fname, val in values.items():
        if fname in field_map and val:
            await db.execute("""
                INSERT OR REPLACE INTO record_values (record_id, field_id, value)
                VALUES (?, ?, ?)
            """, (record_id, field_map[fname], val))
