"""SQLAlchemy ORM models for the student management system."""

from datetime import datetime
import enum

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


# ── Enums ──────────────────────────────────────────────


class AttendanceStatus(str, enum.Enum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"


MAX_PERIODS_PER_DAY = 7
MAX_SUB_PERIODS = 4


class AssessmentType(str, enum.Enum):
    INTERNAL = "INTERNAL"
    QUIZ = "QUIZ"
    ASSIGNMENT = "ASSIGNMENT"


class Gender(str, enum.Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"
    OTHER = "OTHER"


class AdmissionCategory(str, enum.Enum):
    CONVENER = "CONVENER"
    MANAGEMENT = "MANAGEMENT"
    SPOT = "SPOT"
    NRI = "NRI"


class Category(str, enum.Enum):
    OC = "OC"
    BC_A = "BC_A"
    BC_B = "BC_B"
    BC_C = "BC_C"
    BC_D = "BC_D"
    BC_E = "BC_E"
    SC = "SC"
    ST = "ST"
    EWS = "EWS"


class Area(str, enum.Enum):
    RURAL = "RURAL"
    URBAN = "URBAN"


# ── Role ───────────────────────────────────────────────


class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)

    users = relationship("User", back_populates="role")


# ── User (central auth table) ─────────────────────────


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    must_change_password = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)

    role = relationship("Role", back_populates="users")
    student = relationship("Student", back_populates="user", uselist=False)
    teacher = relationship("Teacher", back_populates="user", uselist=False)


# ── Section ────────────────────────────────────────────


class Section(Base):
    __tablename__ = "sections"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(10), nullable=False)
    branch_code = Column(String(10), nullable=False)
    year = Column(Integer, nullable=False)

    __table_args__ = (UniqueConstraint("name", "branch_code", "year"),)

    students = relationship("Student", back_populates="section")
    course_offerings = relationship("CourseOffering", back_populates="section")


# ── Student ────────────────────────────────────────────


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    roll_number = Column(String(20), unique=True, nullable=True, index=True)
    branch_code = Column(String(10), nullable=True)
    section_id = Column(Integer, ForeignKey("sections.id"), nullable=True)

    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    gender = Column(Enum(Gender), nullable=True)
    dob = Column(Date, nullable=False)
    email = Column(String(200))
    phone = Column(String(20))
    address = Column(String(500))
    photo_url = Column(String(500), nullable=True)

    enrollment_date = Column(Date)
    current_year = Column(Integer, nullable=True)
    current_semester = Column(Integer, nullable=True)

    cet_qualified = Column(String(100), nullable=True)
    rank = Column(Integer, nullable=True)

    blood_group = Column(String(10), nullable=True)
    religion = Column(String(50), nullable=True)
    nationality = Column(String(50), nullable=True, default="Indian")

    admission_category = Column(Enum(AdmissionCategory), nullable=True)
    category = Column(Enum(Category), nullable=True)
    area = Column(Enum(Area), nullable=True)

    mentor_name = Column(String(200), nullable=True)
    mentor_id = Column(String(50), nullable=True)

    identification_mark1 = Column(String(300), nullable=True)
    identification_mark2 = Column(String(300), nullable=True)

    father_name = Column(String(200), nullable=True)

    user = relationship("User", back_populates="student")
    section = relationship("Section", back_populates="students")
    enrollments = relationship("Enrollment", back_populates="student", cascade="all, delete-orphan")
    marks = relationship("Mark", back_populates="student", cascade="all, delete-orphan")
    password_reset_audits = relationship("PasswordResetAudit", back_populates="student")


# ── Teacher ────────────────────────────────────────────


class Teacher(Base):
    __tablename__ = "teachers"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    dob = Column(Date, nullable=False)
    email = Column(String(200))
    phone = Column(String(20))
    department = Column(String(200))

    user = relationship("User", back_populates="teacher")
    teacher_courses = relationship("TeacherCourse", back_populates="teacher", cascade="all, delete-orphan")
    attendance_audits = relationship("AttendanceAudit", back_populates="teacher")
    mark_audits = relationship("MarkAudit", back_populates="teacher")


# ── Course Catalog ─────────────────────────────────────


class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(20), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    credits = Column(Integer, default=3)
    department = Column(String(200))

    offerings = relationship("CourseOffering", back_populates="course", cascade="all, delete-orphan")


# ── Course Offering ────────────────────────────────────


class CourseOffering(Base):
    __tablename__ = "course_offerings"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    academic_year = Column(Integer, nullable=False)
    semester = Column(Integer, nullable=False)
    section_id = Column(Integer, ForeignKey("sections.id"), nullable=True)
    capacity = Column(Integer, default=65)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    is_active = Column(Boolean, default=True)

    __table_args__ = (
        UniqueConstraint("course_id", "academic_year", "semester", "section_id"),
        Index("ix_course_offerings_year_semester", "academic_year", "semester"),
        Index("ix_course_offerings_section_id", "section_id"),
    )

    course = relationship("Course", back_populates="offerings")
    section = relationship("Section", back_populates="course_offerings")
    teacher_courses = relationship("TeacherCourse", back_populates="course_offering", cascade="all, delete-orphan")
    enrollments = relationship("Enrollment", back_populates="course_offering", cascade="all, delete-orphan")
    assessments = relationship("Assessment", back_populates="course_offering", cascade="all, delete-orphan")


# ── TeacherCourse (teacher ↔ course offering) ─────────


class TeacherCourse(Base):
    __tablename__ = "teacher_courses"

    id = Column(Integer, primary_key=True, index=True)
    teacher_id = Column(Integer, ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False)
    offering_id = Column(Integer, ForeignKey("course_offerings.id", ondelete="CASCADE"), nullable=False)

    __table_args__ = (
        UniqueConstraint("teacher_id", "offering_id"),
        Index("ix_teacher_courses_offering_id", "offering_id"),
    )

    teacher = relationship("Teacher", back_populates="teacher_courses")
    course_offering = relationship("CourseOffering", back_populates="teacher_courses")


# ── Enrollment (student ↔ course offering) ────────────


class Enrollment(Base):
    __tablename__ = "enrollments"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    offering_id = Column(Integer, ForeignKey("course_offerings.id", ondelete="CASCADE"), nullable=False)
    enrolled_date = Column(Date)

    __table_args__ = (
        UniqueConstraint("student_id", "offering_id"),
        Index("ix_enrollments_offering_id", "offering_id"),
    )

    student = relationship("Student", back_populates="enrollments")
    course_offering = relationship("CourseOffering", back_populates="enrollments")
    attendances = relationship("Attendance", back_populates="enrollment", cascade="all, delete-orphan")
    attendance_audits = relationship("AttendanceAudit", back_populates="enrollment")


# ── Attendance ─────────────────────────────────────────


class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True)
    enrollment_id = Column(Integer, ForeignKey("enrollments.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False)
    period = Column(Integer, nullable=False)
    sub_period = Column(Integer, nullable=False, default=1)
    status = Column(Enum(AttendanceStatus), nullable=False)

    __table_args__ = (
        UniqueConstraint("enrollment_id", "date", "period", "sub_period"),
        Index("ix_attendance_date_period_sub_period", "date", "period", "sub_period"),
    )

    enrollment = relationship("Enrollment", back_populates="attendances")


# ── Assessment ─────────────────────────────────────────


ASSESSMENT_LIMITS = {
    AssessmentType.INTERNAL: 2,
    AssessmentType.QUIZ: 3,
    AssessmentType.ASSIGNMENT: 3,
}

ASSESSMENT_DEFAULT_MAX = {
    AssessmentType.INTERNAL: 30,
    AssessmentType.QUIZ: 5,
    AssessmentType.ASSIGNMENT: 5,
}


class Assessment(Base):
    __tablename__ = "assessments"

    id = Column(Integer, primary_key=True, index=True)
    offering_id = Column(Integer, ForeignKey("course_offerings.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(200), nullable=False)
    type = Column(Enum(AssessmentType), nullable=False)
    max_marks = Column(Float, nullable=False)
    date = Column(Date)

    __table_args__ = (
        UniqueConstraint("offering_id", "type", "name"),
        Index("ix_assessments_offering_id", "offering_id"),
    )

    course_offering = relationship("CourseOffering", back_populates="assessments")
    marks = relationship("Mark", back_populates="assessment", cascade="all, delete-orphan")
    mark_audits = relationship("MarkAudit", back_populates="assessment")


# ── Mark ───────────────────────────────────────────────


class Mark(Base):
    __tablename__ = "marks"

    id = Column(Integer, primary_key=True, index=True)
    assessment_id = Column(Integer, ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    marks_obtained = Column(Float, nullable=False)

    __table_args__ = (
        UniqueConstraint("assessment_id", "student_id"),
        Index("ix_marks_student_id", "student_id"),
    )

    assessment = relationship("Assessment", back_populates="marks")
    student = relationship("Student", back_populates="marks")


# ── Audit Tables ───────────────────────────────────────


class PasswordResetAudit(Base):
    __tablename__ = "password_reset_audits"

    id = Column(Integer, primary_key=True, index=True)
    admin_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    reset_value_rule = Column(String(100), nullable=False)
    reset_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    admin_user = relationship("User")
    student = relationship("Student", back_populates="password_reset_audits")


class AttendanceAudit(Base):
    __tablename__ = "attendance_audits"

    id = Column(Integer, primary_key=True, index=True)
    teacher_id = Column(Integer, ForeignKey("teachers.id", ondelete="SET NULL"), nullable=True)
    enrollment_id = Column(Integer, ForeignKey("enrollments.id", ondelete="CASCADE"), nullable=False)
    action = Column(String(20), nullable=False)
    date = Column(Date, nullable=False)
    period = Column(Integer, nullable=False)
    sub_period = Column(Integer, nullable=False)
    old_status = Column(Enum(AttendanceStatus), nullable=True)
    new_status = Column(Enum(AttendanceStatus), nullable=False)
    changed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (Index("ix_attendance_audits_changed_at", "changed_at"),)

    teacher = relationship("Teacher", back_populates="attendance_audits")
    enrollment = relationship("Enrollment", back_populates="attendance_audits")


class MarkAudit(Base):
    __tablename__ = "mark_audits"

    id = Column(Integer, primary_key=True, index=True)
    teacher_id = Column(Integer, ForeignKey("teachers.id", ondelete="SET NULL"), nullable=True)
    assessment_id = Column(Integer, ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    old_marks = Column(Float, nullable=True)
    new_marks = Column(Float, nullable=False)
    changed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (Index("ix_mark_audits_changed_at", "changed_at"),)

    teacher = relationship("Teacher", back_populates="mark_audits")
    assessment = relationship("Assessment", back_populates="mark_audits")
    student = relationship("Student")


# ── Grade Computation Helpers ──────────────────────────


GRADE_MAP = [
    (90, "A+", 10),
    (80, "A", 9),
    (70, "B", 8),
    (60, "C", 7),
    (50, "D", 6),
    (40, "E", 5),
    (0, "F", 0),
]


def compute_sessional(marks_by_type: dict) -> tuple[float, float]:
    """Compute sessional marks out of 40 from assessment groups."""
    internals = marks_by_type.get(AssessmentType.INTERNAL, [])
    quizzes = marks_by_type.get(AssessmentType.QUIZ, [])
    assignments = marks_by_type.get(AssessmentType.ASSIGNMENT, [])

    if internals:
        best_internal = max(internals)
        internal_score = (best_internal / 30) * 20
    else:
        internal_score = 0

    quiz_total = sum(quizzes)
    quiz_score = (quiz_total / 15) * 10 if quizzes else 0

    assignment_total = sum(assignments)
    assignment_score = (assignment_total / 15) * 10 if assignments else 0

    sessional = round(internal_score + quiz_score + assignment_score, 2)
    return min(sessional, 40), 40


def compute_grade(percentage: float) -> tuple[str, int]:
    """Return (grade_letter, grade_points) based on percentage."""
    for threshold, grade, points in GRADE_MAP:
        if percentage >= threshold:
            return grade, points
    return "F", 0


def parse_roll_number(roll_number: str) -> dict:
    """Parse roll number format: COLLEGE-YY-BRANCH-SERIAL."""
    parts = roll_number.split("-") if roll_number else []
    if len(parts) != 4 or not parts[1].isdigit() or not parts[3].isdigit():
        raise ValueError("Invalid roll number format")
    return {
        "college_code": parts[0],
        "joining_year_short": parts[1],
        "joining_year": 2000 + int(parts[1]),
        "branch_code": parts[2],
        "serial": int(parts[3]),
    }
