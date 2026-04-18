"""Student routes — profile, per-period attendance, VCE marks report with SGPA."""

from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from app.database import get_db
from app.models import (
    User, Student, Enrollment, Attendance, AttendanceStatus,
    Mark, Assessment, AssessmentType, Course,
    compute_sessional, compute_grade,
)
from app.schemas import SubjectMarksDetail, MarksReport
from app.dependencies import require_role

router = APIRouter(prefix="/student", tags=["Student"])
student_required = require_role("STUDENT")


def get_student(current_user: User, db: Session) -> Student:
    student = (
        db.query(Student)
        .filter(Student.user_id == current_user.id)
        .options(joinedload(Student.section))
        .first()
    )
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
        "roll_number": s.roll_number,
        "branch_code": s.branch_code,
        "section": s.section.name if s.section else None,
        "first_name": s.first_name,
        "last_name": s.last_name,
        "gender": s.gender.value if s.gender else None,
        "dob": str(s.dob),
        "father_name": s.father_name,
        "email": s.email,
        "phone": s.phone,
        "address": s.address,
        "photo_url": s.photo_url,
        "enrollment_date": str(s.enrollment_date) if s.enrollment_date else None,
        "current_year": s.current_year,
        "current_semester": s.current_semester,
        "blood_group": s.blood_group,
        "cet_qualified": s.cet_qualified,
        "rank": s.rank,
        "religion": s.religion,
        "nationality": s.nationality,
        "admission_category": s.admission_category.value if s.admission_category else None,
        "category": s.category.value if s.category else None,
        "area": s.area.value if s.area else None,
        "mentor_name": s.mentor_name,
        "mentor_id": s.mentor_id,
        "identification_mark1": s.identification_mark1,
        "identification_mark2": s.identification_mark2,
    }


# ── Attendance (summary) ────────────────────────────

@router.get("/attendance")
def my_attendance(db: Session = Depends(get_db), current_user: User = Depends(student_required)):
    """Get attendance summary for all enrolled courses."""
    student = get_student(current_user, db)
    enrollments = (
        db.query(Enrollment)
        .filter(Enrollment.student_id == student.id)
        .options(joinedload(Enrollment.course), joinedload(Enrollment.attendances))
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
            "total_periods": total,
            "present": present,
            "absent": total - present,
            "percentage": round((present / total * 100), 1) if total > 0 else 0
        })
    return result


# ── Attendance (detailed, per-course) ────────────────

@router.get("/attendance/{course_id}")
def my_attendance_detail(course_id: int, db: Session = Depends(get_db), current_user: User = Depends(student_required)):
    """Get day-by-day, period-by-period attendance for a single course."""
    student = get_student(current_user, db)

    enrollment = (
        db.query(Enrollment)
        .filter(Enrollment.student_id == student.id, Enrollment.course_id == course_id)
        .options(joinedload(Enrollment.course), joinedload(Enrollment.attendances))
        .first()
    )
    if not enrollment:
        raise HTTPException(status_code=404, detail="Not enrolled in this course")

    # Group attendance records by date
    by_date = defaultdict(dict)
    for r in enrollment.attendances:
        by_date[str(r.date)][f"period_{r.period}"] = r.status.value

    records = enrollment.attendances
    total = len(records)
    present = sum(1 for r in records if r.status == AttendanceStatus.PRESENT)

    return {
        "course_code": enrollment.course.code,
        "course_name": enrollment.course.name,
        "total_periods": total,
        "present": present,
        "absent": total - present,
        "percentage": round((present / total * 100), 1) if total > 0 else 0,
        "daily_detail": [
            {"date": d, **periods}
            for d, periods in sorted(by_date.items())
        ]
    }


# ── Marks (VCE-style report with SGPA) ──────────────

@router.get("/marks")
def my_marks(db: Session = Depends(get_db), current_user: User = Depends(student_required)):
    """Return marks in the exact VCE ERP format:
    Per subject: Int1, Int2, Asst1-3, Quiz1-3, Sessional, Grade, Credits, GradePoints.
    Plus overall SGPA.
    """
    student = get_student(current_user, db)

    # Get all enrollments with course info
    enrollments = (
        db.query(Enrollment)
        .filter(Enrollment.student_id == student.id)
        .options(joinedload(Enrollment.course).joinedload(Course.assessments))
        .all()
    )

    # Get all marks for this student
    all_marks = (
        db.query(Mark)
        .filter(Mark.student_id == student.id)
        .options(joinedload(Mark.assessment))
        .all()
    )

    # Build a lookup: assessment_id → marks_obtained
    marks_lookup = {m.assessment_id: m.marks_obtained for m in all_marks}

    subjects = []
    total_credits = 0
    total_grade_points = 0
    total_sessional_max = 0
    total_sessional_secured = 0

    for enrollment in enrollments:
        course = enrollment.course

        # Group assessments by type, sorted by name to get Int1/Int2, Quiz1/2/3, Asst1/2/3
        assessments_by_type = defaultdict(list)
        for a in course.assessments:
            assessments_by_type[a.type].append(a)

        # Sort each group by name to ensure consistent ordering
        for atype in assessments_by_type:
            assessments_by_type[atype].sort(key=lambda x: x.name)

        internals = assessments_by_type.get(AssessmentType.INTERNAL, [])
        quizzes = assessments_by_type.get(AssessmentType.QUIZ, [])
        assignments = assessments_by_type.get(AssessmentType.ASSIGNMENT, [])

        # Helper to get marks for an assessment slot
        def get_marks(assessment_list, index):
            if index < len(assessment_list):
                a = assessment_list[index]
                return marks_lookup.get(a.id)
            return None

        def get_max(assessment_list, index, default):
            if index < len(assessment_list):
                return assessment_list[index].max_marks
            return default

        # Collect raw marks for sessional computation
        marks_by_type = {}
        for atype, alist in assessments_by_type.items():
            marks_by_type[atype] = [
                marks_lookup.get(a.id, 0) for a in alist if a.id in marks_lookup
            ]

        sessional_secured, sessional_max = compute_sessional(marks_by_type)
        sessional_pct = (sessional_secured / sessional_max * 100) if sessional_max > 0 else 0
        grade, grade_pts = compute_grade(sessional_pct)

        subject = SubjectMarksDetail(
            subject_code=course.code,
            subject_name=course.name,
            int1_max=get_max(internals, 0, 30),
            int1_secured=get_marks(internals, 0),
            int2_max=get_max(internals, 1, 30),
            int2_secured=get_marks(internals, 1),
            asst1_max=get_max(assignments, 0, 5),
            asst1_secured=get_marks(assignments, 0),
            asst2_max=get_max(assignments, 1, 5),
            asst2_secured=get_marks(assignments, 1),
            asst3_max=get_max(assignments, 2, 5),
            asst3_secured=get_marks(assignments, 2),
            quiz1_max=get_max(quizzes, 0, 5),
            quiz1_secured=get_marks(quizzes, 0),
            quiz2_max=get_max(quizzes, 1, 5),
            quiz2_secured=get_marks(quizzes, 1),
            quiz3_max=get_max(quizzes, 2, 5),
            quiz3_secured=get_marks(quizzes, 2),
            sessional_max=sessional_max,
            sessional_secured=sessional_secured,
            grade=grade,
            sub_credits=course.credits,
            grade_points=grade_pts,
        )
        subjects.append(subject)

        total_credits += course.credits
        total_grade_points += grade_pts * course.credits
        total_sessional_max += sessional_max
        total_sessional_secured += sessional_secured

    sgpa = round(total_grade_points / total_credits, 2) if total_credits > 0 else 0
    sessional_pct = round(
        (total_sessional_secured / total_sessional_max * 100), 2
    ) if total_sessional_max > 0 else 0

    return MarksReport(
        student_name=f"{student.first_name} {student.last_name}",
        roll_number=student.roll_number or "",
        branch=student.branch_code or "",
        year=student.current_year,
        semester=student.current_semester,
        subjects=subjects,
        total_sessional_max=total_sessional_max,
        total_sessional_secured=total_sessional_secured,
        sessional_percentage=sessional_pct,
        sgpa=sgpa,
        total_credits=total_credits,
        total_grade_points=total_grade_points,
    )


# ── Marks (simple flat list — legacy) ────────────────

@router.get("/marks/flat")
def my_marks_flat(db: Session = Depends(get_db), current_user: User = Depends(student_required)):
    """Simple flat list of all marks (for backward compatibility)."""
    student = get_student(current_user, db)
    marks = (
        db.query(Mark)
        .filter(Mark.student_id == student.id)
        .options(
            joinedload(Mark.assessment).joinedload(Assessment.course)
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
