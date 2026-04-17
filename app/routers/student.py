"""Student routes — profile, attendance, marks."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from app.database import get_db
from app.models import User, Student, Enrollment, Attendance, AttendanceStatus, Mark, Assessment
from app.dependencies import require_role

router = APIRouter(prefix="/student", tags=["Student"])
student_required = require_role("STUDENT")


def get_student(current_user: User, db: Session) -> Student:
    student = db.query(Student).filter(Student.user_id == current_user.id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found")
    return student


# ── Profile ───────────────────────────────────────────

@router.get("/profile")
def my_profile(db: Session = Depends(get_db), current_user: User = Depends(student_required)):
    s = get_student(current_user, db)
    return {
        "id": s.id,
        "username": current_user.username,
        "first_name": s.first_name,
        "last_name": s.last_name,
        "dob": str(s.dob),
        "email": s.email,
        "phone": s.phone,
        "address": s.address,
        "enrollment_date": str(s.enrollment_date) if s.enrollment_date else None
    }


# ── Attendance ────────────────────────────────────────

@router.get("/attendance")
def my_attendance(db: Session = Depends(get_db), current_user: User = Depends(student_required)):
    student = get_student(current_user, db)
    enrollments = (
        db.query(Enrollment)
        .filter(Enrollment.student_id == student.id)
        .options(joinedload(Enrollment.course), joinedload(Enrollment.attendances))  # Fix #6
        .all()
    )

    result = []
    for e in enrollments:
        records = e.attendances
        total = len(records)
        present = sum(1 for r in records if r.status == AttendanceStatus.PRESENT)
        result.append({
            "course_id": e.course.id,
            "course_code": e.course.code,
            "course_name": e.course.name,
            "total_classes": total,
            "present": present,
            "absent": total - present,
            "percentage": round((present / total * 100), 1) if total > 0 else 0
        })
    return result


# ── Marks ─────────────────────────────────────────────

@router.get("/marks")
def my_marks(db: Session = Depends(get_db), current_user: User = Depends(student_required)):
    student = get_student(current_user, db)
    marks = (
        db.query(Mark)
        .filter(Mark.student_id == student.id)
        .options(
            joinedload(Mark.assessment).joinedload(Assessment.course)  # Fix #6 — nested eager load
        )
        .all()
    )

    result = []
    for m in marks:
        result.append({
            "course_code": m.assessment.course.code,
            "course_name": m.assessment.course.name,
            "assessment_name": m.assessment.name,
            "assessment_type": m.assessment.type.value,
            "marks_obtained": m.marks_obtained,
            "max_marks": m.assessment.max_marks,
            "percentage": round((m.marks_obtained / m.assessment.max_marks * 100), 1) if m.assessment.max_marks > 0 else 0
        })
    return result
