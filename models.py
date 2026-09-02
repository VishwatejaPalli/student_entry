"""
Pydantic schemas for request/response validation.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


# ── Student ──────────────────────────────────────────────────────

class StudentCreate(BaseModel):
    roll_no: str = Field(..., min_length=1)
    name: str = ""
    department: str = ""
    section: str = ""
    batch: str = ""
    year: str = ""


class StudentUpdate(BaseModel):
    name: Optional[str] = None
    department: Optional[str] = None
    section: Optional[str] = None
    batch: Optional[str] = None
    year: Optional[str] = None
    active: Optional[bool] = None


class StudentOut(BaseModel):
    id: int
    roll_no: str
    name: str
    department: str
    section: str
    batch: str = ""
    year: str
    active: bool
    created_at: str


# ── Form ─────────────────────────────────────────────────────────

class FormCreate(BaseModel):
    name: str = Field(..., min_length=1)
    description: str = ""


class FormUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class FormOut(BaseModel):
    id: int
    name: str
    description: str
    version: int
    active: bool
    created_at: str
    updated_at: str


# ── Form Field ───────────────────────────────────────────────────

class FieldCreate(BaseModel):
    field_type: str = Field(..., pattern=r"^(text|number|dropdown|radio|checkbox|textarea|date|time|heading|paragraph|divider)$")
    field_name: str = ""
    label: str = ""
    required: bool = False
    position: Optional[int] = None
    configuration: dict = Field(default_factory=dict)


class FieldUpdate(BaseModel):
    field_type: Optional[str] = None
    field_name: Optional[str] = None
    label: Optional[str] = None
    required: Optional[bool] = None
    position: Optional[int] = None
    configuration: Optional[dict] = None


class FieldOut(BaseModel):
    id: int
    form_id: int
    field_type: str
    field_name: str
    label: str
    required: bool
    position: int
    configuration: dict
    is_active: bool


class FieldReorder(BaseModel):
    field_ids: list[int]


# ── Entry / Exit ─────────────────────────────────────────────────

class IdentifyRequest(BaseModel):
    roll_no: str = Field(..., min_length=1)


class RollNoRequest(BaseModel):
    roll_no: str = Field(..., min_length=1)


class IdentifyResponse(BaseModel):
    roll_no: str
    student_name: str
    department: str = ""
    section: str = ""
    batch: str = ""
    year: str = ""
    is_inside: bool
    record_id: Optional[int] = None


class EntryRequest(BaseModel):
    roll_no: str = Field(..., min_length=1)
    field_values: dict[str, str] = Field(default_factory=dict)


class ExitRequest(BaseModel):
    roll_no: str = Field(..., min_length=1)


class RecordOut(BaseModel):
    id: int
    form_id: int
    roll_no: str
    student_name: str = ""
    entry_time: str
    exit_time: Optional[str] = None
    duration_minutes: Optional[int] = None
    status: str = ""
    custom_fields: dict[str, str] = Field(default_factory=dict)


# ── Dashboard ────────────────────────────────────────────────────

class DashboardStats(BaseModel):
    currently_inside: int
    today_visits: int
    recent_records: list[RecordOut]


# ── Class Session & Bulk Entry ───────────────────────────────────

class SessionCreate(BaseModel):
    session_name: str = Field(..., min_length=1)
    class_name: str = ""
    subject: str = ""
    room: str = ""
    faculty: str = ""
    scheduled_start: str  # ISO string
    scheduled_end: str    # ISO string
    late_threshold_min: int = 15
    pc_strategy: str = "none"  # 'none', 'auto_sequential', 'manual'
    pc_prefix: str = "PC-"
    students: list[str] = Field(default_factory=list)  # list of roll numbers
    is_completed_bulk: bool = False  # If true, records are immediately marked as COMPLETED/PRESENT
    bulk_status: str = "PRESENT"     # Default status for immediate bulk log
    custom_fields: dict[str, Any] = Field(default_factory=dict)


class SessionStudentUpdate(BaseModel):
    status: Optional[str] = None  # 'PRESENT', 'ABSENT', 'LATE', 'LEFT_EARLY', 'PENDING'
    pc_assigned: Optional[str] = None
    actual_entry: Optional[str] = None
    actual_exit: Optional[str] = None


class SessionScanRequest(BaseModel):
    roll_no: str = Field(..., min_length=1)
    pc_assigned: Optional[str] = None


class SessionScanResponse(BaseModel):
    success: bool
    status: str
    message: str
    roll_no: str
    student_name: str
    pc_assigned: str
    is_walk_in: bool
    sound: str  # 'success', 'late', 'warning', 'info'


class SessionStudentOut(BaseModel):
    id: int
    session_id: int
    roll_no: str
    student_name: str
    scheduled_status: str
    actual_entry: Optional[str] = None
    actual_exit: Optional[str] = None
    duration_minutes: Optional[int] = None
    status: str
    pc_assigned: str
    record_id: Optional[int] = None


class SessionOut(BaseModel):
    id: int
    session_name: str
    class_name: str
    subject: str
    room: str
    faculty: str
    scheduled_start: str
    scheduled_end: str
    late_threshold_min: int
    pc_strategy: str
    pc_prefix: str
    custom_fields: dict[str, Any] = Field(default_factory=dict)
    status: str
    created_at: str
    ended_at: Optional[str] = None
    total_students: int = 0
    present_count: int = 0
    absent_count: int = 0
    late_count: int = 0
    pending_count: int = 0
    students: list[SessionStudentOut] = Field(default_factory=list)


# ── Bulk / Session Custom Configuration ──────────────────────────

class SessionCustomFieldDef(BaseModel):
    field_name: str
    label: str
    field_type: str = "text"
    required: bool = False
    placeholder: str = ""
    options: List[str] = Field(default_factory=list)


class SessionConfigModel(BaseModel):
    rooms: List[str] = Field(default_factory=list)
    subjects: List[str] = Field(default_factory=list)
    faculties: List[str] = Field(default_factory=list)
    batches: List[str] = Field(default_factory=list)
    defaults: dict[str, Any] = Field(default_factory=dict)
    custom_fields: List[SessionCustomFieldDef] = Field(default_factory=list)


class BatchAssignRequest(BaseModel):
    class_name: str
    split_count: int = 2
    prefix: str = "Batch "
    ranges: Optional[List[dict[str, Any]]] = None
