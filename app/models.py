"""SQLAlchemy ORM models — all tables defined in one file for simplicity."""

from sqlalchemy import (
    Column, Integer, String, Boolean, Date, Float,
    ForeignKey, Enum, UniqueConstraint, Text
)
from sqlalchemy.orm import relationship
from app.database import Base
import enum


# ── Enums ──────────────────────────────────────────────

class AttendanceStatus(str, enum.Enum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"


class AssessmentType(str, enum.Enum):
    INTERNAL = "INTERNAL"      # 2 per course (max 30 marks each)
    QUIZ = "QUIZ"              # 3 per course (max 5 marks each)
    ASSIGNMENT = "ASSIGNMENT"  # 3 per course (max 5 marks each)


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
    name = Column(String(50), unique=True, nullable=False)  # ADMIN, TEACHER, STUDENT

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
    """Sections like CSE-A, CSE-B. First 65 roll serials → A, next 65 → B, etc."""
    __tablename__ = "sections"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(10), nullable=False)           # "A", "B", "C"
    branch_code = Column(String(10), nullable=False)    # "733" for CSE
    year = Column(Integer, nullable=False)              # Joining year, e.g. 2024

    __table_args__ = (UniqueConstraint("name", "branch_code", "year"),)

    students = relationship("Student", back_populates="section")


# ── Student ────────────────────────────────────────────

class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    roll_number = Column(String(20), unique=True, nullable=True, index=True)  # e.g. 1602-24-733-016
    branch_code = Column(String(10), nullable=True)   # e.g. 733 for CSE
    section_id = Column(Integer, ForeignKey("sections.id"), nullable=True)

    # Basic Info
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    gender = Column(Enum(Gender), nullable=True)
    dob = Column(Date, nullable=False)
    email = Column(String(200))
    phone = Column(String(20))
    address = Column(String(500))
    photo_url = Column(String(500), nullable=True)

    # Academic Info
    enrollment_date = Column(Date)                     # Date of Joining
    current_year = Column(Integer, nullable=True)      # e.g. 2
    current_semester = Column(Integer, nullable=True)  # e.g. 3

    # Entrance Exam & Rank
    cet_qualified = Column(String(100), nullable=True)  # e.g. "EAPCET-2024"
    rank = Column(Integer, nullable=True)

    # Personal Details
    blood_group = Column(String(10), nullable=True)    # e.g. "O+", "A-"
    religion = Column(String(50), nullable=True)
    nationality = Column(String(50), nullable=True, default="Indian")

    # Category & Admission
    admission_category = Column(Enum(AdmissionCategory), nullable=True)
    category = Column(Enum(Category), nullable=True)   # EWS, OC, BC, SC, ST
    area = Column(Enum(Area), nullable=True)           # Rural / Urban

    # Mentor
    mentor_name = Column(String(200), nullable=True)
    mentor_id = Column(String(50), nullable=True)

    # Identification Marks
    identification_mark1 = Column(String(300), nullable=True)
    identification_mark2 = Column(String(300), nullable=True)

    # Father's info
    father_name = Column(String(200), nullable=True)

    user = relationship("User", back_populates="student")
    section = relationship("Section", back_populates="students")
    enrollments = relationship("Enrollment", back_populates="student", cascade="all, delete-orphan")
    marks = relationship("Mark", back_populates="student", cascade="all, delete-orphan")


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


# ── Course ─────────────────────────────────────────────

class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(20), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    credits = Column(Integer, default=3)
    department = Column(String(200))

    teacher_courses = relationship("TeacherCourse", back_populates="course", cascade="all, delete-orphan")
    enrollments = relationship("Enrollment", back_populates="course", cascade="all, delete-orphan")
    assessments = relationship("Assessment", back_populates="course", cascade="all, delete-orphan")


# ── TeacherCourse (many-to-many: teacher ↔ course) ────

class TeacherCourse(Base):
    __tablename__ = "teacher_courses"

    id = Column(Integer, primary_key=True, index=True)
    teacher_id = Column(Integer, ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)

    __table_args__ = (UniqueConstraint("teacher_id", "course_id"),)

    teacher = relationship("Teacher", back_populates="teacher_courses")
    course = relationship("Course", back_populates="teacher_courses")


# ── Enrollment (many-to-many: student ↔ course) ───────

class Enrollment(Base):
    __tablename__ = "enrollments"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    enrolled_date = Column(Date)

    __table_args__ = (UniqueConstraint("student_id", "course_id"),)

    student = relationship("Student", back_populates="enrollments")
    course = relationship("Course", back_populates="enrollments")
    attendances = relationship("Attendance", back_populates="enrollment", cascade="all, delete-orphan")


# ── Attendance ─────────────────────────────────────────

class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True)
    enrollment_id = Column(Integer, ForeignKey("enrollments.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False)
    period = Column(Integer, nullable=False)  # 1–6 (each period = 1 hour)
    status = Column(Enum(AttendanceStatus), nullable=False)

    __table_args__ = (UniqueConstraint("enrollment_id", "date", "period"),)

    enrollment = relationship("Enrollment", back_populates="attendances")


# ── Assessment ─────────────────────────────────────────

# Limits per course:
#   INTERNAL  → max 2 (default max_marks: 30)
#   QUIZ      → max 3 (default max_marks: 5)
#   ASSIGNMENT→ max 3 (default max_marks: 5)

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
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(200), nullable=False)          # e.g. "Int1", "Quiz2", "Asst3"
    type = Column(Enum(AssessmentType), nullable=False)
    max_marks = Column(Float, nullable=False)
    date = Column(Date)

    course = relationship("Course", back_populates="assessments")
    marks = relationship("Mark", back_populates="assessment", cascade="all, delete-orphan")


# ── Mark ───────────────────────────────────────────────

class Mark(Base):
    __tablename__ = "marks"

    id = Column(Integer, primary_key=True, index=True)
    assessment_id = Column(Integer, ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    marks_obtained = Column(Float, nullable=False)

    __table_args__ = (UniqueConstraint("assessment_id", "student_id"),)

    assessment = relationship("Assessment", back_populates="marks")
    student = relationship("Student", back_populates="marks")


# ── Grade Computation Helpers ──────────────────────────

# Sessional marks (out of 40) = computed from best internal + quizzes + assignments
# Grade points mapping (VCE standard 10-point scale)
GRADE_MAP = [
    (90, "A+", 10),
    (80, "A",  9),
    (70, "B",  8),
    (60, "C",  7),
    (50, "D",  6),
    (40, "E",  5),
    (0,  "F",  0),
]


def compute_sessional(marks_by_type: dict) -> tuple[float, float]:
    """
    Compute sessional marks (out of 40) from raw assessment marks.
    
    VCE formula (approximate):
    - Best of 2 internals → scaled to 20 marks
    - Sum of 3 quizzes → scaled to 10 marks
    - Sum of 3 assignments → scaled to 10 marks
    - Total sessional = 40
    
    Returns: (sessional_obtained, sessional_max=40)
    """
    internals = marks_by_type.get(AssessmentType.INTERNAL, [])
    quizzes = marks_by_type.get(AssessmentType.QUIZ, [])
    assignments = marks_by_type.get(AssessmentType.ASSIGNMENT, [])

    # Best internal out of 30 → scaled to 20
    if internals:
        best_internal = max(internals)
        internal_score = (best_internal / 30) * 20
    else:
        internal_score = 0

    # Sum of quizzes out of 15 → scaled to 10
    quiz_total = sum(quizzes)
    quiz_score = (quiz_total / 15) * 10 if quizzes else 0

    # Sum of assignments out of 15 → scaled to 10
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
