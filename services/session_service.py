"""
Session Service — Business logic for Class Sessions and Bulk Entry.

Handles:
  - Session creation (live mode vs immediate bulk mode)
  - Student roster generation (class-based, imported, or pasted) with batch grouping
  - Live barcode scan processing with late detection and PC auto-assignment
  - Manual attendance adjustments
  - Session finalization (marking absentees, calculating durations)
  - Customizable session settings & presets CRUD
  - Roster and class metadata queries
"""

import json
import aiosqlite
from datetime import datetime
from typing import Optional, List, Dict, Any


async def get_classes_list(db: aiosqlite.Connection) -> List[Dict[str, Any]]:
    """
    Get list of unique classes/sections, their available batches, and students.
    Classes are grouped by `department-section` or department (e.g. 'ECE-A', 'ECE-B').
    """
    cursor = await db.execute("""
        SELECT id, roll_no, name, department, section, batch, year
        FROM students
        WHERE active = 1
        ORDER BY department, section, roll_no
    """)
    rows = await cursor.fetchall()

    classes_map: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        dept = (r["department"] or "").strip()
        sec = (r["section"] or "").strip()
        batch = (r["batch"] or "").strip()

        if dept and sec:
            class_name = f"{dept}-{sec}"
        elif dept:
            class_name = dept
        else:
            class_name = "General"

        if class_name not in classes_map:
            classes_map[class_name] = {
                "class_name": class_name,
                "department": dept or "General",
                "section": sec,
                "students": [],
                "batches": set(),
            }

        if batch:
            classes_map[class_name]["batches"].add(batch)

        classes_map[class_name]["students"].append({
            "id": r["id"],
            "roll_no": r["roll_no"],
            "name": r["name"] or r["roll_no"],
            "department": dept,
            "section": sec,
            "batch": batch,
            "year": r["year"],
        })

    result = []
    for k, v in sorted(classes_map.items()):
        batches_list = sorted(list(v["batches"]))
        result.append({
            "class_name": k,
            "department": v["department"],
            "section": v["section"],
            "student_count": len(v["students"]),
            "batches": batches_list,
            "students": v["students"],
        })

    return result


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

    custom_fields_json = json.dumps(session_data.get("custom_fields", {}))

    cursor = await db.execute("""
        INSERT INTO class_sessions (
            session_name, class_name, subject, room, faculty,
            scheduled_start, scheduled_end, late_threshold_min,
            pc_strategy, pc_prefix, custom_fields, status, created_at, ended_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        custom_fields_json,
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
        # Look up or auto-register student in master table
        cursor_st = await db.execute("SELECT name, department FROM students WHERE roll_no = ?", (roll,))
        st_row = await cursor_st.fetchone()
        if not st_row:
            dept = session_data.get("department") or (session_data.get("class_name", "").split("-")[0] if "-" in session_data.get("class_name", "") else "ECE")
            sec = session_data.get("class_name", "").split("-")[1] if "-" in session_data.get("class_name", "") else ""
            await db.execute(
                "INSERT OR IGNORE INTO students (roll_no, name, department, section) VALUES (?, '', ?, ?)",
                (roll, dept, sec)
            )
            student_name = ""
        else:
            student_name = st_row["name"] or ""

        pc_assigned = ""
        if pc_strategy == "auto_sequential":
            pc_assigned = f"{pc_prefix}{str(idx).zfill(2)}"

        student_status = "PENDING"
        actual_entry = None
        actual_exit = None
        dur_mins = None
        record_id = None

        if is_completed_bulk:
            student_status = bulk_status
            actual_entry = session_data["scheduled_start"]
            actual_exit = session_data["scheduled_end"]
            dur_mins = duration

            # Create entry in central records table for dashboard analytics
            cursor_rec = await db.execute("""
                INSERT INTO records (form_id, roll_no, session_id, entry_time, exit_time, duration_minutes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                form_id,
                roll,
                session_id,
                actual_entry,
                actual_exit,
                dur_mins,
                now,
            ))
            record_id = cursor_rec.lastrowid

            # Attach purpose and PC values if form fields exist
            await _save_session_record_values(db, record_id, form_id, {
                "purpose": session_data.get("subject") or "Class Session",
                "pc_number": pc_assigned,
                "remarks": f"Bulk session: {session_data.get('session_name', '')}",
            })

        await db.execute("""
            INSERT INTO session_students (
                session_id, roll_no, student_name, scheduled_status,
                actual_entry, actual_exit, duration_minutes,
                status, pc_assigned, record_id
            ) VALUES (?, ?, ?, 'EXPECTED', ?, ?, ?, ?, ?, ?)
        """, (
            session_id,
            roll,
            student_name,
            actual_entry,
            actual_exit,
            dur_mins,
            student_status,
            pc_assigned if is_completed_bulk else "",
            record_id,
        ))

    await db.commit()
    return session_id


async def record_session_scan(
    db: aiosqlite.Connection,
    session_id: int,
    roll_no: str,
    manual_pc: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Process a live barcode scan or manual roll entry for an active session.
    """
    roll_no = roll_no.strip().upper()
    now = datetime.utcnow()
    now_iso = now.isoformat()

    # Get session details
    cursor_s = await db.execute("SELECT * FROM class_sessions WHERE id = ?", (session_id,))
    session = await cursor_s.fetchone()
    if not session:
        return {"success": False, "status": "ERROR", "message": "Session not found", "sound": "warning"}

    if session["status"] != "ACTIVE":
        return {"success": False, "status": "ERROR", "message": "Session is already closed", "sound": "warning"}

    # Check if student is in session roster
    cursor_ss = await db.execute("""
        SELECT * FROM session_students
        WHERE session_id = ? AND roll_no = ?
    """, (session_id, roll_no))
    session_student = await cursor_ss.fetchone()

    # Look up or create student in master table
    cursor_st = await db.execute("SELECT * FROM students WHERE roll_no = ?", (roll_no,))
    student = await cursor_st.fetchone()
    if not student:
        await db.execute("INSERT INTO students (roll_no, name) VALUES (?, '')", (roll_no,))
        await db.commit()
        student_name = ""
    else:
        student_name = student["name"] or ""

    is_walk_in = session_student is None

    # Check if already scanned (PRESENT or LATE)
    if session_student and session_student["status"] in ("PRESENT", "LATE"):
        return {
            "success": False,
            "status": "ALREADY_PRESENT",
            "message": f"{roll_no} ({student_name or 'Student'}) is already marked {session_student['status']}",
            "roll_no": roll_no,
            "student_name": student_name,
            "pc_assigned": session_student["pc_assigned"] or "None",
            "is_walk_in": is_walk_in,
            "sound": "info",
        }

    # Determine status (PRESENT vs LATE)
    late_threshold_min = session["late_threshold_min"]
    scheduled_start_str = session["scheduled_start"]
    status = "PRESENT"
    sound = "success"

    try:
        sched_start = datetime.fromisoformat(scheduled_start_str)
        diff_mins = (now - sched_start).total_seconds() / 60
        if diff_mins > late_threshold_min:
            status = "LATE"
            sound = "late"
    except Exception:
        pass

    # Determine PC assignment
    pc_strategy = session["pc_strategy"]
    pc_prefix = session["pc_prefix"]
    pc_assigned = manual_pc or ""

    if not pc_assigned and pc_strategy == "auto_sequential":
        cursor_pc = await db.execute("""
            SELECT COUNT(*) as count FROM session_students
            WHERE session_id = ? AND status IN ('PRESENT', 'LATE')
        """, (session_id,))
        pc_row = await cursor_pc.fetchone()
        next_pc_num = (pc_row["count"] or 0) + 1
        pc_assigned = f"{pc_prefix}{str(next_pc_num).zfill(2)}"

    # Get active form for central record
    cursor_f = await db.execute("SELECT id FROM forms WHERE active = 1 LIMIT 1")
    form_row = await cursor_f.fetchone()
    form_id = form_row["id"] if form_row else 1

    # Create central record
    cursor_rec = await db.execute("""
        INSERT INTO records (form_id, roll_no, session_id, entry_time, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (
        form_id,
        roll_no,
        session_id,
        now_iso,
        now_iso,
    ))
    record_id = cursor_rec.lastrowid

    # Store custom fields for central record
    await _save_session_record_values(db, record_id, form_id, {
        "purpose": session["subject"] or "Live Class Session",
        "pc_number": pc_assigned,
        "remarks": f"Live scan in {session['session_name']}",
    })

    # Update or insert into session_students
    if session_student:
        await db.execute("""
            UPDATE session_students
            SET status = ?, actual_entry = ?, pc_assigned = ?, record_id = ?
            WHERE id = ?
        """, (
            status,
            now_iso,
            pc_assigned,
            record_id,
            session_student["id"],
        ))
    else:
        # Walk-in student (not originally on roster)
        await db.execute("""
            INSERT INTO session_students (
                session_id, roll_no, student_name, scheduled_status,
                actual_entry, status, pc_assigned, record_id
            ) VALUES (?, ?, ?, 'WALK_IN', ?, ?, ?, ?)
        """, (
            session_id,
            roll_no,
            student_name,
            now_iso,
            status,
            pc_assigned,
            record_id,
        ))

    await db.commit()

    msg = f"✓ {roll_no} {student_name} marked {status}"
    if pc_assigned:
        msg += f" → Assigned {pc_assigned}"
    if is_walk_in:
        msg += " (Walk-in)"

    return {
        "success": True,
        "status": status,
        "message": msg,
        "roll_no": roll_no,
        "student_name": student_name,
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
    actual_entry: Optional[str] = None,
    actual_exit: Optional[str] = None,
) -> bool:
    """Manually update student attendance status or PC assignment in a session, syncing with central records table."""
    roll_no = roll_no.strip().upper()
    now_iso = datetime.utcnow().isoformat()
    updates = []
    params = []

    if status is not None:
        updates.append("status = ?")
        params.append(status)
        if status in ("PRESENT", "LATE") and not actual_entry:
            updates.append("actual_entry = COALESCE(actual_entry, datetime('now'))")
    if pc_assigned is not None:
        updates.append("pc_assigned = ?")
        params.append(pc_assigned)
    if actual_entry is not None:
        updates.append("actual_entry = ?")
        params.append(actual_entry)
    if actual_exit is not None:
        updates.append("actual_exit = ?")
        params.append(actual_exit)

    if not updates:
        return True

    params.extend([session_id, roll_no])
    query = f"UPDATE session_students SET {', '.join(updates)} WHERE session_id = ? AND roll_no = ?"
    await db.execute(query, params)

    # Sync with central records table for dashboard & analytics
    cursor_ss = await db.execute("""
        SELECT id, record_id, status, actual_entry, actual_exit, duration_minutes
        FROM session_students
        WHERE session_id = ? AND roll_no = ?
    """, (session_id, roll_no))
    row = await cursor_ss.fetchone()
    if row:
        if row["status"] in ("PRESENT", "LATE"):
            if not row["record_id"]:
                cursor_f = await db.execute("SELECT id FROM forms WHERE active = 1 LIMIT 1")
                form_row = await cursor_f.fetchone()
                form_id = form_row["id"] if form_row else 1
                cursor_ins = await db.execute("""
                    INSERT INTO records (form_id, roll_no, session_id, entry_time, exit_time, duration_minutes, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    form_id,
                    roll_no,
                    session_id,
                    row["actual_entry"] or now_iso,
                    row["actual_exit"],
                    row["duration_minutes"],
                    now_iso,
                ))
                r_id = cursor_ins.lastrowid
                await db.execute("UPDATE session_students SET record_id = ? WHERE id = ?", (r_id, row["id"]))
            else:
                await db.execute("""
                    UPDATE records
                    SET entry_time = ?, exit_time = ?, duration_minutes = ?
                    WHERE id = ?
                """, (row["actual_entry"] or now_iso, row["actual_exit"], row["duration_minutes"], row["record_id"]))
        elif row["status"] == "ABSENT" and row["record_id"]:
            await db.execute("DELETE FROM records WHERE id = ?", (row["record_id"],))
            await db.execute("UPDATE session_students SET record_id = NULL WHERE id = ?", (row["id"],))

    await db.commit()
    return True


async def end_session(db: aiosqlite.Connection, session_id: int) -> Optional[Dict[str, Any]]:
    """
    End and finalize an active class session:
      - Marks all remaining 'PENDING' students as 'ABSENT'
      - Sets actual_exit and calculates duration for all present students
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
    """Get full details of a session including student roster and parsed custom fields."""
    cursor = await db.execute("SELECT * FROM class_sessions WHERE id = ?", (session_id,))
    session = await cursor.fetchone()
    if not session:
        return None

    result = dict(session)
    try:
        result["custom_fields"] = json.loads(result.get("custom_fields") or "{}")
    except Exception:
        result["custom_fields"] = {}

    # Get student roster
    cursor_st = await db.execute("""
        SELECT ss.*, COALESCE(s.name, ss.student_name, '') as student_name, COALESCE(s.batch, '') as batch
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


async def get_session_config(db: aiosqlite.Connection) -> Dict[str, Any]:
    """Retrieve customizable session presets, batch lists, and dynamic field settings."""
    cursor = await db.execute(
        "SELECT config_val FROM session_configs WHERE config_key = 'bulk_session_settings' LIMIT 1"
    )
    row = await cursor.fetchone()
    if row and row["config_val"]:
        try:
            return json.loads(row["config_val"])
        except Exception:
            pass

    # Fallback default configuration
    return {
        "rooms": ["VLSI Lab 204", "IoT Lab 205", "Computing Lab 101", "AI Lab 301"],
        "subjects": ["VLSI Design Lab", "Microprocessors Lab", "Python Programming", "Data Structures Lab"],
        "faculties": ["Dr. Kumar", "Prof. Sharma", "Dr. Rao", "Prof. Lakshmi"],
        "batches": ["A1", "A2", "A3", "B1", "B2", "B3", "C1", "C2"],
        "defaults": {
            "pc_strategy": "auto_sequential",
            "pc_prefix": "PC-",
            "late_threshold_min": 15,
            "duration_hours": 2,
            "bulk_status": "PRESENT",
        },
        "custom_fields": [],
    }


async def save_session_config(db: aiosqlite.Connection, config_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Save updated bulk presets, batches, and dynamic fields."""
    now = datetime.utcnow().isoformat()
    config_json = json.dumps(config_dict)

    await db.execute("""
        INSERT INTO session_configs (config_key, config_val, updated_at)
        VALUES ('bulk_session_settings', ?, ?)
        ON CONFLICT(config_key) DO UPDATE SET
            config_val = excluded.config_val,
            updated_at = excluded.updated_at
    """, (config_json, now))
    await db.commit()

    return config_dict


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


async def assign_batches_to_class(
    db: aiosqlite.Connection,
    class_name: str,
    split_count: int = 2,
    prefix: str = "Batch ",
    ranges: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Permanently divide and assign students of a class into semester batches in the database.
    Supports dividing into N equal batches (e.g. 2 or 3) or custom roll ranges.
    """
    parts = class_name.split("-")
    if len(parts) >= 2:
        dept, sec = parts[0], parts[1]
        cursor = await db.execute("""
            SELECT id, roll_no, name, department, section, batch
            FROM students
            WHERE active = 1 AND department = ? AND section = ?
            ORDER BY roll_no
        """, (dept, sec))
    elif class_name != "General":
        cursor = await db.execute("""
            SELECT id, roll_no, name, department, section, batch
            FROM students
            WHERE active = 1 AND department = ?
            ORDER BY roll_no
        """, (class_name,))
    else:
        cursor = await db.execute("""
            SELECT id, roll_no, name, department, section, batch
            FROM students
            WHERE active = 1
            ORDER BY roll_no
        """)

    students = [dict(r) for r in await cursor.fetchall()]
    if not students:
        raise ValueError(f"No active students found in class '{class_name}'")

    total = len(students)
    batch_map: Dict[str, List[str]] = {}

    if ranges and len(ranges) > 0:
        for r in ranges:
            b_name = r["batch"].strip()
            start_roll = r.get("start_roll", "").strip().upper()
            end_roll = r.get("end_roll", "").strip().upper()
            batch_map[b_name] = []

            for st in students:
                roll = st["roll_no"].upper()
                if start_roll <= roll <= end_roll:
                    await db.execute("UPDATE students SET batch = ? WHERE id = ?", (b_name, st["id"]))
                    batch_map[b_name].append(roll)
    else:
        chunk_size = (total + split_count - 1) // split_count
        for idx, st in enumerate(students):
            batch_num = min(split_count, (idx // chunk_size) + 1)
            b_name = f"{prefix}{batch_num}".strip()
            if b_name not in batch_map:
                batch_map[b_name] = []
            await db.execute("UPDATE students SET batch = ? WHERE id = ?", (b_name, st["id"]))
            batch_map[b_name].append(st["roll_no"])

    await db.commit()

    return {
        "success": True,
        "class_name": class_name,
        "total_students": total,
        "split_count": split_count,
        "batches": {k: len(v) for k, v in batch_map.items()},
        "message": f"Successfully allocated {total} students of {class_name} into {len(batch_map)} semester batches",
    }
