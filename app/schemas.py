"""Pydantic schemas for request/response validation."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from datetime import date
from typing import Optional
from app.models import (
    AttendanceStatus, AssessmentType, Gender, AdmissionCategory, Category, Area,
    MAX_PERIODS_PER_DAY, MAX_SUB_PERIODS
)


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


# ── Section ────────────────────────────────────────────

class SectionOut(BaseModel):
    id: int
    name: str
    branch_code: str
    year: int
    student_count: int = 0

    model_config = ConfigDict(from_attributes=True)


# ── Student ────────────────────────────────────────────

class StudentCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    dob: date
    branch_code: str = Field(min_length=1, max_length=10)  # e.g. 733 for CSE
    gender: Optional[Gender] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, pattern=r'^\d{10,15}$')
    address: Optional[str] = Field(None, max_length=500)
    father_name: Optional[str] = Field(None, max_length=200)
    blood_group: Optional[str] = Field(None, max_length=10)
    religion: Optional[str] = Field(None, max_length=50)
    nationality: Optional[str] = Field("Indian", max_length=50)
    admission_category: Optional[AdmissionCategory] = None
    category: Optional[Category] = None
    area: Optional[Area] = None
    cet_qualified: Optional[str] = Field(None, max_length=100)
    rank: Optional[int] = Field(None, ge=1)
    mentor_name: Optional[str] = Field(None, max_length=200)
    mentor_id: Optional[str] = Field(None, max_length=50)
    identification_mark1: Optional[str] = Field(None, max_length=300)
    identification_mark2: Optional[str] = Field(None, max_length=300)
    current_year: Optional[int] = Field(None, ge=1, le=4)
    current_semester: Optional[int] = Field(None, ge=1, le=8)

class StudentUpdate(BaseModel):
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, pattern=r'^\d{10,15}$')
    address: Optional[str] = Field(None, max_length=500)
    gender: Optional[Gender] = None
    father_name: Optional[str] = Field(None, max_length=200)
    blood_group: Optional[str] = Field(None, max_length=10)
    religion: Optional[str] = Field(None, max_length=50)
    nationality: Optional[str] = Field(None, max_length=50)
    admission_category: Optional[AdmissionCategory] = None
    category: Optional[Category] = None
    area: Optional[Area] = None
    cet_qualified: Optional[str] = Field(None, max_length=100)
    rank: Optional[int] = Field(None, ge=1)
    mentor_name: Optional[str] = Field(None, max_length=200)
    mentor_id: Optional[str] = Field(None, max_length=50)
    identification_mark1: Optional[str] = Field(None, max_length=300)
    identification_mark2: Optional[str] = Field(None, max_length=300)
    current_year: Optional[int] = Field(None, ge=1, le=4)
    current_semester: Optional[int] = Field(None, ge=1, le=8)
    photo_url: Optional[str] = Field(None, max_length=500)

class StudentOut(BaseModel):
    id: int
    user_id: int
    username: str
    roll_number: Optional[str] = None
    roll_college_code: Optional[str] = None
    roll_joining_year: Optional[int] = None
    roll_serial: Optional[int] = None
    branch_code: Optional[str] = None
    section_name: Optional[str] = None
    first_name: str
    last_name: str
    gender: Optional[str] = None
    dob: date
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    father_name: Optional[str] = None
    enrollment_date: Optional[date] = None
    current_year: Optional[int] = None
    current_semester: Optional[int] = None
    blood_group: Optional[str] = None
    cet_qualified: Optional[str] = None
    rank: Optional[int] = None
    religion: Optional[str] = None
    nationality: Optional[str] = None
    admission_category: Optional[str] = None
    category: Optional[str] = None
    area: Optional[str] = None
    mentor_name: Optional[str] = None
    mentor_id: Optional[str] = None
    identification_mark1: Optional[str] = None
    identification_mark2: Optional[str] = None
    photo_url: Optional[str] = None

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
    status: AttendanceStatus

class AttendanceMark(BaseModel):
    course_id: int
    date: date
    period: int = Field(ge=1, le=MAX_PERIODS_PER_DAY)
    sub_period: int = Field(default=1, ge=1, le=MAX_SUB_PERIODS)
    records: list[AttendanceRecord]


# ── Assessment ─────────────────────────────────────────

class AssessmentCreate(BaseModel):
    course_id: int
    name: str = Field(min_length=1, max_length=200)
    type: AssessmentType
    max_marks: Optional[float] = Field(None, gt=0, le=1000)
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
    marks_obtained: float = Field(ge=0)

class MarksUpload(BaseModel):
    assessment_id: int
    marks: list[MarkEntry]


# ── Marks Report (mirrors VCE ERP marks view) ─────────

class SubjectMarksDetail(BaseModel):
    """Single subject row in the VCE marks report table."""
    subject_code: str
    subject_name: str
    int1_max: float = 30
    int1_secured: Optional[float] = None
    int2_max: float = 30
    int2_secured: Optional[float] = None
    asst1_max: float = 5
    asst1_secured: Optional[float] = None
    asst2_max: float = 5
    asst2_secured: Optional[float] = None
    asst3_max: float = 5
    asst3_secured: Optional[float] = None
    quiz1_max: float = 5
    quiz1_secured: Optional[float] = None
    quiz2_max: float = 5
    quiz2_secured: Optional[float] = None
    quiz3_max: float = 5
    quiz3_secured: Optional[float] = None
    sessional_max: float = 40
    sessional_secured: Optional[float] = None
    grade: Optional[str] = None
    sub_credits: int = 3
    grade_points: Optional[int] = None

class MarksReport(BaseModel):
    """Full marks report for a student (one semester)."""
    student_name: str
    roll_number: str
    branch: str
    year: Optional[int] = None
    semester: Optional[int] = None
    subjects: list[SubjectMarksDetail]
    total_sessional_max: float = 0
    total_sessional_secured: float = 0
    sessional_percentage: float = 0
    sgpa: float = 0
    total_credits: int = 0
    total_grade_points: int = 0


# ── Dashboard Stats ───────────────────────────────────

class DashboardStats(BaseModel):
    total_students: int
    total_teachers: int
    total_courses: int
    total_sections: int = 0
