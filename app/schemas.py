"""Pydantic schemas for request/response validation."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from datetime import date
from typing import Optional
from app.models import AttendanceStatus, AssessmentType


# ── Auth ───────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1)

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    must_change_password: bool

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator('new_password')
    @classmethod
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if v.isdigit():
            raise ValueError('Password cannot be all digits')
        if v.isalpha():
            raise ValueError('Password must contain at least one number')
        return v


# ── Student ────────────────────────────────────────────

class StudentCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    dob: date
    branch_code: str = Field(min_length=1, max_length=10)  # e.g. 733 for CSE
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, pattern=r'^\d{10,15}$')
    address: Optional[str] = Field(None, max_length=500)

class StudentUpdate(BaseModel):
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, pattern=r'^\d{10,15}$')
    address: Optional[str] = Field(None, max_length=500)

class StudentOut(BaseModel):
    id: int
    user_id: int
    username: str
    roll_number: Optional[str] = None
    branch_code: Optional[str] = None
    first_name: str
    last_name: str
    dob: date
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    enrollment_date: Optional[date] = None

    model_config = ConfigDict(from_attributes=True)


# ── Teacher ────────────────────────────────────────────

class TeacherCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    dob: date
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, pattern=r'^\d{10,15}$')
    department: Optional[str] = Field(None, max_length=200)

class TeacherUpdate(BaseModel):
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, pattern=r'^\d{10,15}$')
    department: Optional[str] = Field(None, max_length=200)

class TeacherOut(BaseModel):
    id: int
    user_id: int
    username: str
    first_name: str
    last_name: str
    dob: date
    email: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ── Course ─────────────────────────────────────────────

class CourseCreate(BaseModel):
    code: str = Field(min_length=2, max_length=20, pattern=r'^[A-Za-z0-9]+$')
    name: str = Field(min_length=1, max_length=200)
    credits: int = Field(default=3, ge=1, le=12)
    department: Optional[str] = Field(None, max_length=200)

class CourseUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    credits: Optional[int] = Field(None, ge=1, le=12)
    department: Optional[str] = Field(None, max_length=200)

class CourseOut(BaseModel):
    id: int
    code: str
    name: str
    credits: int
    department: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ── Attendance ─────────────────────────────────────────

class AttendanceRecord(BaseModel):
    student_id: int
    status: AttendanceStatus   # Use actual enum instead of plain str (#9)

class AttendanceMark(BaseModel):
    course_id: int
    date: date
    records: list[AttendanceRecord]


# ── Assessment ─────────────────────────────────────────

class AssessmentCreate(BaseModel):
    course_id: int
    name: str = Field(min_length=1, max_length=200)
    type: AssessmentType       # Use actual enum instead of plain str (#9)
    max_marks: float = Field(gt=0, le=1000)
    date: Optional[date] = None

class AssessmentOut(BaseModel):
    id: int
    course_id: int
    name: str
    type: str
    max_marks: float
    date: Optional[date] = None

    model_config = ConfigDict(from_attributes=True)


# ── Marks ──────────────────────────────────────────────

class MarkEntry(BaseModel):
    student_id: int
    marks_obtained: float = Field(ge=0)    # Cannot be negative (#9)

class MarksUpload(BaseModel):
    assessment_id: int
    marks: list[MarkEntry]


# ── Dashboard Stats ───────────────────────────────────

class DashboardStats(BaseModel):
    total_students: int
    total_teachers: int
    total_courses: int
