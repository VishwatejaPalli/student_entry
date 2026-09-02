"""
Database initialization, connection management, and schema for the
Configurable Room Entry & Data Management System.

Uses aiosqlite for async SQLite access. The schema separates:
  - Configuration (forms, form_fields, session_configs) from
  - Data (records, record_values, class_sessions, session_students)
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
    """Initialize the database: create tables, run migrations, and seed default data."""
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
                batch       TEXT    NOT NULL DEFAULT '',
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
                custom_fields      TEXT    NOT NULL DEFAULT '{}',
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

        # ── Session / Bulk Configurations & Presets ──────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS session_configs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                config_key  TEXT    NOT NULL UNIQUE,
                config_val  TEXT    NOT NULL DEFAULT '{}',
                updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """)

        # ── Migrations ───────────────────────────────────────────
        # Ensure session_id column exists on records
        try:
            await db.execute("ALTER TABLE records ADD COLUMN session_id INTEGER")
        except Exception:
            pass

        # Ensure batch column exists on students
        try:
            await db.execute("ALTER TABLE students ADD COLUMN batch TEXT NOT NULL DEFAULT ''")
        except Exception:
            pass

        # Ensure custom_fields column exists on class_sessions
        try:
            await db.execute("ALTER TABLE class_sessions ADD COLUMN custom_fields TEXT NOT NULL DEFAULT '{}'")
        except Exception:
            pass

        # Sync historical session_students with status PRESENT/LATE that lack records rows
        try:
            cursor_unlinked = await db.execute("""
                SELECT ss.id, ss.session_id, ss.roll_no, ss.actual_entry, ss.actual_exit, ss.duration_minutes,
                       cs.scheduled_start, cs.scheduled_end, cs.session_name, cs.subject
                FROM session_students ss
                JOIN class_sessions cs ON ss.session_id = cs.id
                WHERE ss.status IN ('PRESENT', 'LATE') AND ss.record_id IS NULL
            """)
            unlinked = await cursor_unlinked.fetchall()
            for u in unlinked:
                in_time = u["actual_entry"] or u["scheduled_start"] or datetime.utcnow().isoformat()
                out_time = u["actual_exit"] or u["scheduled_end"]
                dur = u["duration_minutes"] if u["duration_minutes"] is not None else 60
                c_ins = await db.execute("""
                    INSERT INTO records (form_id, roll_no, session_id, entry_time, exit_time, duration_minutes, created_at)
                    VALUES (1, ?, ?, ?, ?, ?, datetime('now'))
                """, (u["roll_no"], u["session_id"], in_time, out_time, dur))
                r_id = c_ins.lastrowid
                await db.execute("UPDATE session_students SET record_id = ? WHERE id = ?", (r_id, u["id"]))
            await db.commit()
        except Exception:
            pass

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

        # ── Migration: Ensure only ECE department and ECE-specific configurations ──
        await db.execute("UPDATE students SET department = 'ECE' WHERE department = 'CSE'")
        await db.execute("UPDATE class_sessions SET class_name = 'ECE-B' WHERE class_name = 'CSE-B'")
        await db.execute("UPDATE class_sessions SET session_name = REPLACE(session_name, 'CSE-', 'ECE-') WHERE session_name LIKE '%CSE-%'")
        await db.commit()

        # ── Seed sample students if none exist ───────────────────
        cursor_st = await db.execute("SELECT COUNT(*) as cnt FROM students WHERE department = 'ECE'")
        row_st = await cursor_st.fetchone()
        if row_st["cnt"] == 0:
            await _seed_sample_students(db)
        else:
            # Backfill batches for sample students if missing
            await _backfill_sample_batches(db)

        # ── Seed default form if none exists ─────────────────────
        cursor = await db.execute("SELECT COUNT(*) as cnt FROM forms")
        row = await cursor.fetchone()
        if row["cnt"] == 0:
            await _seed_default_form(db)

        # ── Seed default session config if none exists or update to ECE ─────
        cursor_cfg = await db.execute("SELECT COUNT(*) as cnt FROM session_configs")
        row_cfg = await cursor_cfg.fetchone()
        if row_cfg["cnt"] == 0:
            await _seed_default_session_config(db)


async def _seed_sample_students(db: aiosqlite.Connection):
    """Seed sample students for ECE-A and ECE-B with batch allocations."""
    sample_students = [
        # ECE-A (Year 3)
        ("24885A0401", "Aarav Sharma", "ECE", "A", "A1", "3"),
        ("24885A0402", "Aditi Patel", "ECE", "A", "A1", "3"),
        ("24885A0403", "Ananya Rao", "ECE", "A", "A1", "3"),
        ("24885A0404", "Bhavya Reddy", "ECE", "A", "A1", "3"),
        ("24885A0405", "Chetan Kumar", "ECE", "A", "A1", "3"),
        ("24885A0406", "Deepak Verma", "ECE", "A", "A2", "3"),
        ("24885A0407", "Divya Nair", "ECE", "A", "A2", "3"),
        ("24885A0408", "Gautam Singh", "ECE", "A", "A2", "3"),
        ("24885A0409", "Harini Murthy", "ECE", "A", "A2", "3"),
        ("24885A0410", "Ishaan Joshi", "ECE", "A", "A2", "3"),
        # ECE-B (Year 3)
        ("24885A0411", "Kavya Iyer", "ECE", "B", "B1", "3"),
        ("24885A0412", "Manish Gupta", "ECE", "B", "B1", "3"),
        ("24885A0413", "Neha Deshmukh", "ECE", "B", "B1", "3"),
        ("24885A0414", "Pranav Menon", "ECE", "B", "B2", "3"),
        ("24885A0415", "Rohan Pillai", "ECE", "B", "B2", "3"),
        ("24885A0416", "Sneha Kulkarni", "ECE", "B", "B2", "3"),
        ("24885A0417", "Tarun Reddy", "ECE", "B", "B3", "3"),
        ("24885A0418", "Varun Chakravarthy", "ECE", "B", "B3", "3"),
    ]
    for roll_no, name, dept, sec, batch, yr in sample_students:
        await db.execute(
            """INSERT OR REPLACE INTO students (roll_no, name, department, section, batch, year, active)
               VALUES (?, ?, ?, ?, ?, ?, 1)""",
            (roll_no, name, dept, sec, batch, yr)
        )
    await db.commit()


async def _backfill_sample_batches(db: aiosqlite.Connection):
    """Backfill batch allocations for sample ECE students."""
    sample_batches = {
        "24885A0401": "A1", "24885A0402": "A1", "24885A0403": "A1", "24885A0404": "A1", "24885A0405": "A1",
        "24885A0406": "A2", "24885A0407": "A2", "24885A0408": "A2", "24885A0409": "A2", "24885A0410": "A2",
        "24885A0411": "B1", "24885A0412": "B1", "24885A0413": "B1",
        "24885A0414": "B2", "24885A0415": "B2", "24885A0416": "B2",
        "24885A0417": "B3", "24885A0418": "B3",
    }
    for roll_no, batch in sample_batches.items():
        await db.execute(
            "UPDATE students SET batch = ? WHERE roll_no = ? AND (batch = '' OR batch IS NULL)",
            (batch, roll_no)
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


async def _seed_default_session_config(db: aiosqlite.Connection):
    """Seed default customizable presets for ECE Class Sessions & Bulk Entry."""
    default_config = {
        "rooms": [
            "VLSI Design Lab 204",
            "Embedded Systems & IoT Lab 205",
            "DSP & Communications Lab 206",
            "Microprocessors Lab 207",
            "Microwave & Optical Lab 208",
            "Electronics Systems Lab 209",
        ],
        "subjects": [
            "VLSI Design Lab",
            "Microprocessors & Microcontrollers Lab",
            "Digital Signal Processing Lab",
            "Analog & Digital Communications Lab",
            "Embedded Systems & IoT Lab",
            "Linear Integrated Circuits Lab",
            "Microwave Engineering Lab",
        ],
        "faculties": [
            "Dr. K. Srinivas (ECE)",
            "Prof. M. Sharma (ECE)",
            "Dr. Ananya Rao (ECE)",
            "Prof. G. Lakshmi (ECE)",
            "Prof. V. Reddy (ECE)",
        ],
        "batches": [
            "A1", "A2", "A3",
            "B1", "B2", "B3",
            "Batch 1", "Batch 2", "Batch 3",
        ],
        "defaults": {
            "pc_strategy": "auto_sequential",
            "pc_prefix": "PC-",
            "late_threshold_min": 15,
            "duration_hours": 2,
            "bulk_status": "PRESENT",
        },
        "custom_fields": [
            {
                "field_name": "experiment_no",
                "label": "Experiment / Lab Task",
                "field_type": "text",
                "required": False,
                "placeholder": "e.g. Exp 4: CMOS Inverter Simulation",
            },
            {
                "field_name": "lab_assistant",
                "label": "Lab Assistant / Staff",
                "field_type": "text",
                "required": False,
                "placeholder": "e.g. Mr. S. Varma",
            },
        ],
    }

    now = datetime.utcnow().isoformat()
    await db.execute(
        """INSERT OR REPLACE INTO session_configs (config_key, config_val, updated_at)
           VALUES (?, ?, ?)""",
        ("session_presets", json.dumps(default_config), now),
    )
    await db.execute(
        """INSERT OR REPLACE INTO session_configs (config_key, config_val, updated_at)
           VALUES (?, ?, ?)""",
        ("bulk_session_settings", json.dumps(default_config), now),
    )
    await db.commit()
