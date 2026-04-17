"""Admin routes — CRUD for students, teachers, courses + dashboard stats."""

import logging
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from app.database import get_db
from app.models import User, Role, Student, Teacher, Course, TeacherCourse, Enrollment
from app.schemas import (
    StudentCreate, StudentUpdate, StudentOut,
    TeacherCreate, TeacherUpdate, TeacherOut,
    CourseCreate, CourseUpdate, CourseOut,
    DashboardStats
)
from app.security import hash_password
from app.dependencies import require_role

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["Admin"])

# All routes require ADMIN role
admin_required = require_role("ADMIN")


# ── Helpers ────────────────────────────────────────────

COLLEGE_CODE = "1602"  # Your college code

def _generate_roll_number(db: Session, branch_code: str, joining_year: int) -> str:
    """Generate roll number: 1602-YY-BBB-NNN (auto-incremented serial)."""
    yy = str(joining_year)[-2:]  # Last 2 digits of year

    # Count existing students with same year + branch to get next serial
    existing = (
        db.query(Student)
        .filter(
            Student.branch_code == branch_code,
            Student.roll_number.like(f"{COLLEGE_CODE}-{yy}-{branch_code}-%")
        )
        .count()
    )
    serial = str(existing + 1).zfill(3)  # Zero-pad to 3 digits
    return f"{COLLEGE_CODE}-{yy}-{branch_code}-{serial}"


def _generate_unique_username(db: Session, first_name: str, last_name: str) -> str:
    """Generate a unique username from first.last (used for teachers)."""
    base = f"{first_name.lower()}.{last_name.lower()}"
    username = base
    counter = 1
    while db.query(User).filter(User.username == username).first():
        username = f"{base}{counter}"
        counter += 1
    return username


def _create_teacher_with_profile(db: Session, first_name: str, last_name: str,
                                  dob: date, **profile_fields) -> str:
    """Create a User + Teacher profile. Returns the generated username."""
    username = _generate_unique_username(db, first_name, last_name)
    default_password = dob.strftime("%d%m%Y")

    role = db.query(Role).filter(Role.name == "TEACHER").first()
    if not role:
        raise HTTPException(status_code=500, detail="TEACHER role not found")

    user = User(username=username, password_hash=hash_password(default_password),
                role_id=role.id, must_change_password=True)
    db.add(user)
    db.flush()

    teacher = Teacher(user_id=user.id, first_name=first_name, last_name=last_name,
                      dob=dob, **profile_fields)
    db.add(teacher)
    return username


def _create_student_with_profile(db: Session, first_name: str, last_name: str,
                                  dob: date, branch_code: str, **profile_fields) -> str:
    """Create a User + Student profile with roll number as username."""
    joining_year = date.today().year
    roll_number = _generate_roll_number(db, branch_code, joining_year)
    default_password = dob.strftime("%d%m%Y")

    role = db.query(Role).filter(Role.name == "STUDENT").first()
    if not role:
        raise HTTPException(status_code=500, detail="STUDENT role not found")

    user = User(username=roll_number, password_hash=hash_password(default_password),
                role_id=role.id, must_change_password=True)
    db.add(user)
    db.flush()

    student = Student(user_id=user.id, roll_number=roll_number, branch_code=branch_code,
                      first_name=first_name, last_name=last_name, dob=dob,
                      enrollment_date=date.today(), **profile_fields)
    db.add(student)
    return roll_number


# ── Dashboard ─────────────────────────────────────────

@router.get("/stats", response_model=DashboardStats)
def get_stats(db: Session = Depends(get_db), current_user: User = Depends(admin_required)):
    return DashboardStats(
        total_students=db.query(Student).count(),
        total_teachers=db.query(Teacher).count(),
        total_courses=db.query(Course).count()
    )


# ── Students ──────────────────────────────────────────

@router.get("/students")
def list_students(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    students = (
        db.query(Student)
        .options(joinedload(Student.user))
        .offset(skip).limit(limit)
        .all()
    )
    return [
        StudentOut(
            id=s.id, user_id=s.user_id, username=s.user.username,
            roll_number=s.roll_number, branch_code=s.branch_code,
            first_name=s.first_name, last_name=s.last_name, dob=s.dob,
            email=s.email, phone=s.phone, address=s.address,
            enrollment_date=s.enrollment_date
        ) for s in students
    ]


@router.post("/students", status_code=status.HTTP_201_CREATED)
def create_student(data: StudentCreate, db: Session = Depends(get_db), current_user: User = Depends(admin_required)):
    roll_number = _create_student_with_profile(
        db, data.first_name, data.last_name, data.dob, data.branch_code,
        email=data.email, phone=data.phone, address=data.address,
    )
    db.commit()
    logger.info("Admin %s created student %s", current_user.username, roll_number)
    return {"message": f"Student created. Roll Number / Username: {roll_number}, Default password: DOB (DDMMYYYY)"}


@router.put("/students/{student_id}")
def update_student(student_id: int, data: StudentUpdate, db: Session = Depends(get_db), current_user: User = Depends(admin_required)):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(student, field, value)
    db.commit()
    logger.info("Admin %s updated student %d", current_user.username, student_id)
    return {"message": "Student updated"}


@router.delete("/students/{student_id}")
def delete_student(student_id: int, db: Session = Depends(get_db), current_user: User = Depends(admin_required)):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    user = student.user
    db.delete(student)  # Delete profile first
    db.flush()
    db.delete(user)     # Then delete user
    db.commit()
    logger.info("Admin %s deleted student %d", current_user.username, student_id)
    return {"message": "Student deleted"}


# ── Teachers ──────────────────────────────────────────

@router.get("/teachers")
def list_teachers(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    teachers = (
        db.query(Teacher)
        .options(joinedload(Teacher.user))
        .offset(skip).limit(limit)
        .all()
    )
    return [
        TeacherOut(
            id=t.id, user_id=t.user_id, username=t.user.username,
            first_name=t.first_name, last_name=t.last_name, dob=t.dob,
            email=t.email, phone=t.phone, department=t.department
        ) for t in teachers
    ]


@router.post("/teachers", status_code=status.HTTP_201_CREATED)
def create_teacher(data: TeacherCreate, db: Session = Depends(get_db), current_user: User = Depends(admin_required)):
    username = _create_teacher_with_profile(
        db, data.first_name, data.last_name, data.dob,
        email=data.email, phone=data.phone, department=data.department,
    )
    db.commit()
    logger.info("Admin %s created teacher %s", current_user.username, username)
    return {"message": f"Teacher created. Username: {username}, Default password: DOB (DDMMYYYY)"}


@router.put("/teachers/{teacher_id}")
def update_teacher(teacher_id: int, data: TeacherUpdate, db: Session = Depends(get_db), current_user: User = Depends(admin_required)):
    teacher = db.query(Teacher).filter(Teacher.id == teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(teacher, field, value)
    db.commit()
    logger.info("Admin %s updated teacher %d", current_user.username, teacher_id)
    return {"message": "Teacher updated"}


@router.delete("/teachers/{teacher_id}")
def delete_teacher(teacher_id: int, db: Session = Depends(get_db), current_user: User = Depends(admin_required)):
    teacher = db.query(Teacher).filter(Teacher.id == teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")
    user = teacher.user
    db.delete(teacher)  # Delete profile first
    db.flush()
    db.delete(user)     # Then delete user
    db.commit()
    logger.info("Admin %s deleted teacher %d", current_user.username, teacher_id)
    return {"message": "Teacher deleted"}


# ── Courses ───────────────────────────────────────────

@router.get("/courses")
def list_courses(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    courses = db.query(Course).offset(skip).limit(limit).all()
    return [CourseOut(id=c.id, code=c.code, name=c.name, credits=c.credits, department=c.department) for c in courses]


@router.post("/courses", status_code=status.HTTP_201_CREATED)
def create_course(data: CourseCreate, db: Session = Depends(get_db), current_user: User = Depends(admin_required)):
    if db.query(Course).filter(Course.code == data.code).first():
        raise HTTPException(status_code=400, detail="Course code already exists")
    course = Course(**data.model_dump())
    db.add(course)
    db.commit()
    logger.info("Admin %s created course %s", current_user.username, data.code)
    return {"message": "Course created", "id": course.id}


@router.put("/courses/{course_id}")
def update_course(course_id: int, data: CourseUpdate, db: Session = Depends(get_db), current_user: User = Depends(admin_required)):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(course, field, value)
    db.commit()
    return {"message": "Course updated"}


@router.delete("/courses/{course_id}")
def delete_course(course_id: int, db: Session = Depends(get_db), current_user: User = Depends(admin_required)):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    db.delete(course)
    db.commit()
    logger.info("Admin %s deleted course %d", current_user.username, course_id)
    return {"message": "Course deleted"}


# ── Teacher-Course Assignment ─────────────────────────

@router.post("/assign-teacher")
def assign_teacher(teacher_id: int, course_id: int, db: Session = Depends(get_db), current_user: User = Depends(admin_required)):
    if not db.query(Teacher).filter(Teacher.id == teacher_id).first():
        raise HTTPException(status_code=404, detail="Teacher not found")
    if not db.query(Course).filter(Course.id == course_id).first():
        raise HTTPException(status_code=404, detail="Course not found")
    if db.query(TeacherCourse).filter(TeacherCourse.teacher_id == teacher_id, TeacherCourse.course_id == course_id).first():
        raise HTTPException(status_code=400, detail="Already assigned")
    tc = TeacherCourse(teacher_id=teacher_id, course_id=course_id)
    db.add(tc)
    db.commit()
    return {"message": "Teacher assigned to course"}


@router.delete("/unassign-teacher")
def unassign_teacher(teacher_id: int, course_id: int, db: Session = Depends(get_db), current_user: User = Depends(admin_required)):
    tc = db.query(TeacherCourse).filter(TeacherCourse.teacher_id == teacher_id, TeacherCourse.course_id == course_id).first()
    if not tc:
        raise HTTPException(status_code=404, detail="Assignment not found")
    db.delete(tc)
    db.commit()
    return {"message": "Teacher unassigned from course"}


# ── Enrollment ────────────────────────────────────────

@router.post("/enroll")
def enroll_student(student_id: int, course_id: int, db: Session = Depends(get_db), current_user: User = Depends(admin_required)):
    if not db.query(Student).filter(Student.id == student_id).first():
        raise HTTPException(status_code=404, detail="Student not found")
    if not db.query(Course).filter(Course.id == course_id).first():
        raise HTTPException(status_code=404, detail="Course not found")
    if db.query(Enrollment).filter(Enrollment.student_id == student_id, Enrollment.course_id == course_id).first():
        raise HTTPException(status_code=400, detail="Already enrolled")
    enrollment = Enrollment(student_id=student_id, course_id=course_id, enrolled_date=date.today())
    db.add(enrollment)
    db.commit()
    return {"message": "Student enrolled in course"}


@router.delete("/unenroll")
def unenroll_student(student_id: int, course_id: int, db: Session = Depends(get_db), current_user: User = Depends(admin_required)):
    enrollment = db.query(Enrollment).filter(Enrollment.student_id == student_id, Enrollment.course_id == course_id).first()
    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    db.delete(enrollment)
    db.commit()
    return {"message": "Student unenrolled from course"}


@router.get("/enrollments")
def list_enrollments(db: Session = Depends(get_db), current_user: User = Depends(admin_required)):
    enrollments = (
        db.query(Enrollment)
        .options(joinedload(Enrollment.student), joinedload(Enrollment.course))
        .all()
    )
    return [{
        "id": e.id,
        "student_id": e.student_id,
        "student_name": f"{e.student.first_name} {e.student.last_name}",
        "course_id": e.course_id,
        "course_name": e.course.name,
        "course_code": e.course.code,
        "enrolled_date": str(e.enrolled_date) if e.enrolled_date else None
    } for e in enrollments]


@router.get("/teacher-assignments")
def list_teacher_assignments(db: Session = Depends(get_db), current_user: User = Depends(admin_required)):
    assignments = (
        db.query(TeacherCourse)
        .options(joinedload(TeacherCourse.teacher), joinedload(TeacherCourse.course))
        .all()
    )
    return [{
        "id": a.id,
        "teacher_id": a.teacher_id,
        "teacher_name": f"{a.teacher.first_name} {a.teacher.last_name}",
        "course_id": a.course_id,
        "course_name": a.course.name,
        "course_code": a.course.code
    } for a in assignments]
