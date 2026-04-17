"""SQLAlchemy ORM models — all tables defined in one file for simplicity."""

from sqlalchemy import (
    Column, Integer, String, Boolean, Date, Float,
    ForeignKey, Enum, UniqueConstraint
)
from sqlalchemy.orm import relationship
from app.database import Base
import enum


# ── Enums ──────────────────────────────────────────────

class AttendanceStatus(str, enum.Enum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"


class AssessmentType(str, enum.Enum):
    QUIZ = "QUIZ"
    MIDTERM = "MIDTERM"
    FINAL = "FINAL"
    ASSIGNMENT = "ASSIGNMENT"


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


# ── Student ────────────────────────────────────────────

class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    roll_number = Column(String(20), unique=True, nullable=True, index=True)  # e.g. 1602-24-733-016
    branch_code = Column(String(10), nullable=True)  # e.g. 733 for CSE
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    dob = Column(Date, nullable=False)
    email = Column(String(200))
    phone = Column(String(20))
    address = Column(String(500))
    enrollment_date = Column(Date)

    user = relationship("User", back_populates="student")
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
    status = Column(Enum(AttendanceStatus), nullable=False)

    __table_args__ = (UniqueConstraint("enrollment_id", "date"),)

    enrollment = relationship("Enrollment", back_populates="attendances")


# ── Assessment ─────────────────────────────────────────

class Assessment(Base):
    __tablename__ = "assessments"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(200), nullable=False)
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
