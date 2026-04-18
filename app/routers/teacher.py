"""Teacher routes — courses, per-period attendance, assessments (with limits), marks."""

import logging
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from app.database import get_db
from app.models import (
    User, Teacher, TeacherCourse, Course, Enrollment,
    Attendance, AttendanceStatus, Assessment, AssessmentType, Mark, Student,
    ASSESSMENT_LIMITS
)
from app.schemas import AttendanceMark, AssessmentCreate, MarksUpload
from app.dependencies import require_role

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/teacher", tags=["Teacher"])
teacher_required = require_role("TEACHER")


def get_teacher(current_user: User, db: Session) -> Teacher:
    """Helper to get the teacher profile for the current user."""
    teacher = db.query(Teacher).filter(Teacher.user_id == current_user.id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher profile not found")
    return teacher


def _verify_course_access(teacher: Teacher, course_id: int, db: Session) -> TeacherCourse:
    """Verify teacher is assigned to this course, raise 403 if not."""
    tc = db.query(TeacherCourse).filter(
        TeacherCourse.teacher_id == teacher.id,
        TeacherCourse.course_id == course_id,
    ).first()
    if not tc:
        raise HTTPException(status_code=403, detail="You are not assigned to this course")
    return tc


# ── Courses ───────────────────────────────────────────

@router.get("/courses")
def my_courses(db: Session = Depends(get_db), current_user: User = Depends(teacher_required)):
    teacher = get_teacher(current_user, db)
    tc_list = (
        db.query(TeacherCourse)
        .filter(TeacherCourse.teacher_id == teacher.id)
        .options(joinedload(TeacherCourse.course))
        .all()
    )
    return [{
        "id": tc.course.id,
        "code": tc.course.code,
        "name": tc.course.name,
        "credits": tc.course.credits,
        "department": tc.course.department
    } for tc in tc_list]


@router.get("/courses/{course_id}/students")
def course_students(
    course_id: int,
    section_id: int = Query(None, description="Filter by section"),
    db: Session = Depends(get_db),
    current_user: User = Depends(teacher_required),
):
    """List students enrolled in a course, optionally filtered by section."""
    teacher = get_teacher(current_user, db)
    _verify_course_access(teacher, course_id, db)

    query = (
        db.query(Enrollment)
        .filter(Enrollment.course_id == course_id)
        .options(joinedload(Enrollment.student).joinedload(Student.section))
    )

    enrollments = query.all()

    # Filter by section in Python (simpler than a cross-table join)
    if section_id is not None:
        enrollments = [e for e in enrollments if e.student.section_id == section_id]

    return [{
        "student_id": e.student.id,
        "roll_number": e.student.roll_number,
        "first_name": e.student.first_name,
        "last_name": e.student.last_name,
        "section": e.student.section.name if e.student.section else None,
        "email": e.student.email,
        "enrollment_id": e.id
    } for e in enrollments]


# ── Attendance (per-period) ──────────────────────────

@router.post("/attendance")
def mark_attendance(data: AttendanceMark, db: Session = Depends(get_db), current_user: User = Depends(teacher_required)):
    """Mark attendance for a specific period (1–6) on a given date."""
    teacher = get_teacher(current_user, db)
    _verify_course_access(teacher, data.course_id, db)

    for record in data.records:
        enrollment = db.query(Enrollment).filter(
            Enrollment.student_id == record.student_id,
            Enrollment.course_id == data.course_id
        ).first()
        if not enrollment:
            continue

        # Update if exists for this enrollment+date+period, else create
        existing = db.query(Attendance).filter(
            Attendance.enrollment_id == enrollment.id,
            Attendance.date == data.date,
            Attendance.period == data.period
        ).first()
        if existing:
            existing.status = record.status
        else:
            db.add(Attendance(
                enrollment_id=enrollment.id,
                date=data.date,
                period=data.period,
                status=record.status
            ))

    db.commit()
    logger.info(
        "Teacher %s marked attendance for course %d, period %d on %s",
        current_user.username, data.course_id, data.period, data.date
    )
    return {"message": f"Attendance marked for period {data.period}"}


@router.get("/attendance/{course_id}")
def view_attendance(
    course_id: int,
    section_id: int = Query(None, description="Filter by section"),
    db: Session = Depends(get_db),
    current_user: User = Depends(teacher_required),
):
    """View attendance summary for all students in a course."""
    teacher = get_teacher(current_user, db)
    _verify_course_access(teacher, course_id, db)

    enrollments = (
        db.query(Enrollment)
        .filter(Enrollment.course_id == course_id)
        .options(
            joinedload(Enrollment.student).joinedload(Student.section),
            joinedload(Enrollment.attendances),
        )
        .all()
    )

    if section_id is not None:
        enrollments = [e for e in enrollments if e.student.section_id == section_id]

    result = []
    for e in enrollments:
        records = e.attendances
        total = len(records)
        present = sum(1 for r in records if r.status == AttendanceStatus.PRESENT)
        result.append({
            "student_id": e.student.id,
            "roll_number": e.student.roll_number,
            "student_name": f"{e.student.first_name} {e.student.last_name}",
            "section": e.student.section.name if e.student.section else None,
            "total_periods": total,
            "present": present,
            "absent": total - present,
            "percentage": round((present / total * 100), 1) if total > 0 else 0
        })
    return result


@router.get("/attendance/{course_id}/date/{att_date}")
def view_attendance_by_date(
    course_id: int,
    att_date: date,
    section_id: int = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(teacher_required),
):
    """View all period-wise attendance for a course on a specific date."""
    teacher = get_teacher(current_user, db)
    _verify_course_access(teacher, course_id, db)

    enrollments = (
        db.query(Enrollment)
        .filter(Enrollment.course_id == course_id)
        .options(
            joinedload(Enrollment.student).joinedload(Student.section),
            joinedload(Enrollment.attendances),
        )
        .all()
    )

    if section_id is not None:
        enrollments = [e for e in enrollments if e.student.section_id == section_id]

    result = []
    for e in enrollments:
        day_records = [r for r in e.attendances if r.date == att_date]
        periods = {r.period: r.status.value for r in day_records}
        result.append({
            "student_id": e.student.id,
            "roll_number": e.student.roll_number,
            "student_name": f"{e.student.first_name} {e.student.last_name}",
            "section": e.student.section.name if e.student.section else None,
            "periods": periods  # e.g. {1: "PRESENT", 2: "ABSENT", ...}
        })
    return result


# ── Assessments (with limits) ────────────────────────

@router.get("/assessments/{course_id}")
def list_assessments(course_id: int, db: Session = Depends(get_db), current_user: User = Depends(teacher_required)):
    teacher = get_teacher(current_user, db)
    _verify_course_access(teacher, course_id, db)

    assessments = db.query(Assessment).filter(Assessment.course_id == course_id).all()
    return [{
        "id": a.id,
        "name": a.name,
        "type": a.type.value,
        "max_marks": a.max_marks,
        "date": str(a.date) if a.date else None
    } for a in assessments]


@router.post("/assessments")
def create_assessment(data: AssessmentCreate, db: Session = Depends(get_db), current_user: User = Depends(teacher_required)):
    teacher = get_teacher(current_user, db)
    _verify_course_access(teacher, data.course_id, db)

    # Enforce assessment limits per course
    existing_count = db.query(Assessment).filter(
        Assessment.course_id == data.course_id,
        Assessment.type == data.type
    ).count()

    limit = ASSESSMENT_LIMITS.get(data.type, 99)
    if existing_count >= limit:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {limit} {data.type.value.lower()}s allowed per course. "
                   f"Already have {existing_count}."
        )

    assessment = Assessment(
        course_id=data.course_id, name=data.name,
        type=data.type, max_marks=data.max_marks, date=data.date
    )
    db.add(assessment)
    db.commit()
    logger.info("Teacher %s created assessment '%s' for course %d", current_user.username, data.name, data.course_id)
    return {"message": "Assessment created", "id": assessment.id}


# ── Marks ─────────────────────────────────────────────

@router.post("/marks")
def upload_marks(data: MarksUpload, db: Session = Depends(get_db), current_user: User = Depends(teacher_required)):
    teacher = get_teacher(current_user, db)
    assessment = db.query(Assessment).filter(Assessment.id == data.assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    _verify_course_access(teacher, assessment.course_id, db)

    for entry in data.marks:
        # Validate marks don't exceed max
        if entry.marks_obtained > assessment.max_marks:
            raise HTTPException(
                status_code=400,
                detail=f"Marks {entry.marks_obtained} exceed max {assessment.max_marks} for student {entry.student_id}"
            )
        existing = db.query(Mark).filter(Mark.assessment_id == data.assessment_id, Mark.student_id == entry.student_id).first()
        if existing:
            existing.marks_obtained = entry.marks_obtained
        else:
            db.add(Mark(assessment_id=data.assessment_id, student_id=entry.student_id, marks_obtained=entry.marks_obtained))
    db.commit()
    logger.info("Teacher %s uploaded marks for assessment %d", current_user.username, data.assessment_id)
    return {"message": "Marks uploaded successfully"}


@router.get("/marks/{assessment_id}")
def view_marks(assessment_id: int, db: Session = Depends(get_db), current_user: User = Depends(teacher_required)):
    teacher = get_teacher(current_user, db)
    assessment = db.query(Assessment).filter(Assessment.id == assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    _verify_course_access(teacher, assessment.course_id, db)

    marks = (
        db.query(Mark)
        .filter(Mark.assessment_id == assessment_id)
        .options(joinedload(Mark.student).joinedload(Student.section))
        .all()
    )
    return [{
        "student_id": m.student.id,
        "roll_number": m.student.roll_number,
        "student_name": f"{m.student.first_name} {m.student.last_name}",
        "section": m.student.section.name if m.student.section else None,
        "marks_obtained": m.marks_obtained,
        "max_marks": assessment.max_marks
    } for m in marks]
