"""
Database initialization, connection management, and schema for the
Configurable Room Entry & Data Management System.

Uses aiosqlite for async SQLite access. The schema separates:
  - Configuration (forms, form_fields) from
  - Data (records, record_values)
  - Identity (students)
"""

import aiosqlite
import json
import os
from pathlib import Path
from datetime import datetime

DATABASE_DIR = Path(__file__).parent / "data"
DATABASE_PATH = DATABASE_DIR / "student_entry.db"


async def get_db() -> aiosqlite.Connection:
    """Get a database connection. Caller must close or use as context manager."""
    db = await aiosqlite.connect(str(DATABASE_PATH))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def init_db():
    """Initialize the database: create tables and seed default data."""
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(str(DATABASE_PATH)) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys=ON")

        # ── Students ──────────────────────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                roll_no     TEXT    NOT NULL UNIQUE,
                name        TEXT    NOT NULL DEFAULT '',
                department  TEXT    NOT NULL DEFAULT '',
                section     TEXT    NOT NULL DEFAULT '',
                year        TEXT    NOT NULL DEFAULT '',
                active      INTEGER NOT NULL DEFAULT 1,
                created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """)

        # ── Forms ─────────────────────────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS forms (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT    NOT NULL,
                description TEXT    NOT NULL DEFAULT '',
                version     INTEGER NOT NULL DEFAULT 1,
                active      INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
                updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """)

        # ── Form Fields ──────────────────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS form_fields (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                form_id       INTEGER NOT NULL,
                field_type    TEXT    NOT NULL,
                field_name    TEXT    NOT NULL DEFAULT '',
                label         TEXT    NOT NULL DEFAULT '',
                required      INTEGER NOT NULL DEFAULT 0,
                position      INTEGER NOT NULL DEFAULT 0,
                configuration TEXT    NOT NULL DEFAULT '{}',
                is_active     INTEGER NOT NULL DEFAULT 1,
                created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (form_id) REFERENCES forms(id) ON DELETE CASCADE
            )
        """)

        # ── Records (system fields) ──────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS records (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                form_id          INTEGER NOT NULL,
                roll_no          TEXT    NOT NULL,
                session_id       INTEGER,
                entry_time       TEXT    NOT NULL DEFAULT (datetime('now')),
                exit_time        TEXT,
                duration_minutes INTEGER,
                created_at       TEXT    NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (form_id) REFERENCES forms(id),
                FOREIGN KEY (roll_no) REFERENCES students(roll_no),
                FOREIGN KEY (session_id) REFERENCES class_sessions(id) ON DELETE SET NULL
            )
        """)

        # ── Record Values (EAV for custom fields) ────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS record_values (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                record_id INTEGER NOT NULL,
                field_id  INTEGER NOT NULL,
                value     TEXT    NOT NULL DEFAULT '',
                FOREIGN KEY (record_id) REFERENCES records(id) ON DELETE CASCADE,
                FOREIGN KEY (field_id)  REFERENCES form_fields(id)
            )
        """)

        # ── Class Sessions ───────────────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS class_sessions (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                session_name       TEXT    NOT NULL,
                class_name         TEXT    NOT NULL DEFAULT '',
                subject            TEXT    NOT NULL DEFAULT '',
                room               TEXT    NOT NULL DEFAULT '',
                faculty            TEXT    NOT NULL DEFAULT '',
                scheduled_start    TEXT    NOT NULL,
                scheduled_end      TEXT    NOT NULL,
                late_threshold_min INTEGER NOT NULL DEFAULT 15,
                pc_strategy        TEXT    NOT NULL DEFAULT 'none',
                pc_prefix          TEXT    NOT NULL DEFAULT 'PC-',
                status             TEXT    NOT NULL DEFAULT 'ACTIVE',
                created_at         TEXT    NOT NULL DEFAULT (datetime('now')),
                ended_at           TEXT
            )
        """)

        # ── Session Students ─────────────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS session_students (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id       INTEGER NOT NULL,
                roll_no          TEXT    NOT NULL,
                student_name     TEXT    NOT NULL DEFAULT '',
                scheduled_status TEXT    NOT NULL DEFAULT 'EXPECTED',
                actual_entry     TEXT,
                actual_exit      TEXT,
                duration_minutes INTEGER,
                status           TEXT    NOT NULL DEFAULT 'PENDING',
                pc_assigned      TEXT    NOT NULL DEFAULT '',
                record_id        INTEGER,
                FOREIGN KEY (session_id) REFERENCES class_sessions(id) ON DELETE CASCADE,
                FOREIGN KEY (roll_no)    REFERENCES students(roll_no)
            )
        """)

        # ── Migration: ensure session_id column exists on records ─
        try:
            await db.execute("ALTER TABLE records ADD COLUMN session_id INTEGER")
        except Exception:
            pass  # Column already exists

        # ── Indexes ──────────────────────────────────────────────
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_records_roll_no
            ON records(roll_no)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_records_entry_time
            ON records(entry_time)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_records_exit_time
            ON records(exit_time)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_record_values_record_id
            ON record_values(record_id)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_form_fields_form_id
            ON form_fields(form_id)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_class_sessions_status
            ON class_sessions(status)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_session_students_session_id
            ON session_students(session_id)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_session_students_roll_no
            ON session_students(roll_no)
        """)

        await db.commit()

        # ── Seed sample students if none exist ───────────────────
        cursor_st = await db.execute("SELECT COUNT(*) as cnt FROM students")
        row_st = await cursor_st.fetchone()
        if row_st["cnt"] == 0:
            await _seed_sample_students(db)

        # ── Seed default form if none exists ─────────────────────
        cursor = await db.execute("SELECT COUNT(*) as cnt FROM forms")
        row = await cursor.fetchone()
        if row["cnt"] == 0:
            await _seed_default_form(db)


async def _seed_sample_students(db: aiosqlite.Connection):
    """Seed sample students for ECE-A and CSE-B to demonstrate class roster selection."""
    sample_students = [
        ("24885A0401", "Aarav Sharma", "ECE", "A", "3"),
        ("24885A0402", "Aditi Patel", "ECE", "A", "3"),
        ("24885A0403", "Ananya Rao", "ECE", "A", "3"),
        ("24885A0404", "Bhavya Reddy", "ECE", "A", "3"),
        ("24885A0405", "Chetan Kumar", "ECE", "A", "3"),
        ("24885A0406", "Deepak Verma", "ECE", "A", "3"),
        ("24885A0407", "Divya Nair", "ECE", "A", "3"),
        ("24885A0408", "Gautam Singh", "ECE", "A", "3"),
        ("24885A0409", "Harini Murthy", "ECE", "A", "3"),
        ("24885A0410", "Ishaan Joshi", "ECE", "A", "3"),
        ("24881A0501", "Kavya Iyer", "CSE", "B", "2"),
        ("24881A0502", "Manish Gupta", "CSE", "B", "2"),
        ("24881A0503", "Neha Deshmukh", "CSE", "B", "2"),
        ("24881A0504", "Pranav Menon", "CSE", "B", "2"),
        ("24881A0505", "Rohan Pillai", "CSE", "B", "2"),
    ]
    for roll_no, name, dept, sec, yr in sample_students:
        await db.execute(
            """INSERT OR IGNORE INTO students (roll_no, name, department, section, year)
               VALUES (?, ?, ?, ?, ?)""",
            (roll_no, name, dept, sec, yr)
        )
    await db.commit()


async def _seed_default_form(db: aiosqlite.Connection):
    """Create the default Laboratory Entry Form with common fields."""
    now = datetime.utcnow().isoformat()

    cursor = await db.execute(
        """INSERT INTO forms (name, description, version, active, created_at, updated_at)
           VALUES (?, ?, 1, 1, ?, ?)""",
        ("Laboratory Entry Form", "Default form for laboratory access tracking.", now, now),
    )
    form_id = cursor.lastrowid

    default_fields = [
        {
            "field_type": "heading",
            "field_name": "",
            "label": "",
            "required": False,
            "position": 1,
            "configuration": json.dumps({"level": 2, "text": "Laboratory Entry"}),
        },
        {
            "field_type": "paragraph",
            "field_name": "",
            "label": "",
            "required": False,
            "position": 2,
            "configuration": json.dumps(
                {"text": "Please provide the following information before entering the laboratory.", "style": "info"}
            ),
        },
        {
            "field_type": "dropdown",
            "field_name": "purpose",
            "label": "Purpose",
            "required": True,
            "position": 3,
            "configuration": json.dumps(
                {"options": ["Project", "Lab Work", "Assignment", "Class", "Exam", "Other"], "default": None}
            ),
        },
        {
            "field_type": "dropdown",
            "field_name": "pc_number",
            "label": "PC Number",
            "required": True,
            "position": 4,
            "configuration": json.dumps(
                {"options": [f"PC-{str(i).zfill(2)}" for i in range(1, 31)], "default": None}
            ),
        },
        {
            "field_type": "textarea",
            "field_name": "remarks",
            "label": "Remarks",
            "required": False,
            "position": 5,
            "configuration": json.dumps({"placeholder": "Any additional notes...", "max_length": 1000, "rows": 3}),
        },
    ]

    for field in default_fields:
        await db.execute(
            """INSERT INTO form_fields
               (form_id, field_type, field_name, label, required, position, configuration, is_active, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)""",
            (
                form_id,
                field["field_type"],
                field["field_name"],
                field["label"],
                1 if field["required"] else 0,
                field["position"],
                field["configuration"],
                now,
            ),
        )

    await db.commit()
