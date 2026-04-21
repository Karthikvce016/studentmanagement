"""Teacher routes — courses, per-period attendance, assessments (with limits), marks."""

import csv
import io
import logging
from datetime import date
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session, joinedload
from app.database import get_db
from app.models import (
    User, Teacher, TeacherCourse, Enrollment,
    Attendance, AttendanceStatus, Assessment, Mark, Student,
    ASSESSMENT_DEFAULT_MAX, ASSESSMENT_LIMITS
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


def _student_name(student: Student) -> str:
    return f"{student.first_name} {student.last_name}"


def _get_course_enrollments(course_id: int, db: Session, section_id: int | None = None) -> list[Enrollment]:
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
    return sorted(enrollments, key=lambda e: e.student.roll_number or "")


def _get_assessment(assessment_id: int, db: Session) -> Assessment:
    assessment = db.query(Assessment).filter(Assessment.id == assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return assessment


def _get_enrollment_for_student(student_id: int, course_id: int, db: Session) -> Enrollment:
    enrollment = db.query(Enrollment).filter(
        Enrollment.student_id == student_id,
        Enrollment.course_id == course_id,
    ).first()
    if not enrollment:
        raise HTTPException(status_code=400, detail=f"Student {student_id} is not enrolled in this course")
    return enrollment


def _get_enrollment_by_roll(
    roll_number: str,
    course_id: int,
    db: Session,
    section_id: int | None = None,
) -> Enrollment:
    enrollment = (
        db.query(Enrollment)
        .join(Student)
        .filter(Enrollment.course_id == course_id, Student.roll_number == roll_number)
        .options(joinedload(Enrollment.student).joinedload(Student.section))
        .first()
    )
    if not enrollment:
        raise HTTPException(status_code=400, detail=f"Roll number {roll_number} is not enrolled in this course")
    if section_id is not None and enrollment.student.section_id != section_id:
        raise HTTPException(status_code=400, detail=f"Roll number {roll_number} is not in the selected section")
    return enrollment


def _upsert_attendance(
    enrollment_id: int,
    att_date: date,
    period: int,
    sub_period: int,
    status: AttendanceStatus,
    db: Session,
) -> None:
    existing = db.query(Attendance).filter(
        Attendance.enrollment_id == enrollment_id,
        Attendance.date == att_date,
        Attendance.period == period,
        Attendance.sub_period == sub_period,
    ).first()
    if existing:
        existing.status = status
    else:
        db.add(Attendance(
            enrollment_id=enrollment_id,
            date=att_date,
            period=period,
            sub_period=sub_period,
            status=status,
        ))


def _upsert_mark(assessment_id: int, student_id: int, marks_obtained: float, db: Session) -> None:
    existing = db.query(Mark).filter(
        Mark.assessment_id == assessment_id,
        Mark.student_id == student_id,
    ).first()
    if existing:
        existing.marks_obtained = marks_obtained
    else:
        db.add(Mark(
            assessment_id=assessment_id,
            student_id=student_id,
            marks_obtained=marks_obtained,
        ))


def _attendance_slot_key(record: Attendance) -> str:
    if record.sub_period == 1:
        return f"period_{record.period}"
    return f"period_{record.period}_{record.sub_period}"


def _csv_response(filename: str, fieldnames: list[str], rows: list[dict]) -> Response:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return Response(
        output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _read_csv_upload(file: UploadFile, required_columns: set[str]) -> list[tuple[int, dict]]:
    raw = file.file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="CSV file is empty")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="CSV must be UTF-8 encoded")

    reader = csv.DictReader(io.StringIO(text))
    fieldnames = set(reader.fieldnames or [])
    missing = required_columns - fieldnames
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing CSV columns: {', '.join(sorted(missing))}")

    rows = []
    for line_number, row in enumerate(reader, start=2):
        rows.append((line_number, {k: (v or "").strip() for k, v in row.items()}))
    if not rows:
        raise HTTPException(status_code=400, detail="CSV has no data rows")
    return rows


def _parse_status(value: str, line_number: int) -> AttendanceStatus:
    normalized = value.strip().upper()
    aliases = {"P": "PRESENT", "A": "ABSENT"}
    normalized = aliases.get(normalized, normalized)
    try:
        return AttendanceStatus(normalized)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid attendance status on line {line_number}")


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


@router.get("/courses/{course_id}/sections")
def course_sections(course_id: int, db: Session = Depends(get_db), current_user: User = Depends(teacher_required)):
    """List sections represented in an assigned course."""
    teacher = get_teacher(current_user, db)
    _verify_course_access(teacher, course_id, db)

    enrollments = _get_course_enrollments(course_id, db)
    by_section = {}
    for enrollment in enrollments:
        section = enrollment.student.section
        key = section.id if section else 0
        if key not in by_section:
            by_section[key] = {
                "section_id": section.id if section else None,
                "section_name": section.name if section else None,
                "branch_code": section.branch_code if section else enrollment.student.branch_code,
                "year": section.year if section else None,
                "student_count": 0,
            }
        by_section[key]["student_count"] += 1
    return sorted(by_section.values(), key=lambda s: (s["branch_code"] or "", s["section_name"] or ""))


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

    enrollments = _get_course_enrollments(course_id, db, section_id)

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
    """Mark attendance for a specific period/sub-period on a given date."""
    teacher = get_teacher(current_user, db)
    _verify_course_access(teacher, data.course_id, db)

    for record in data.records:
        enrollment = _get_enrollment_for_student(record.student_id, data.course_id, db)
        _upsert_attendance(
            enrollment.id,
            data.date,
            data.period,
            data.sub_period,
            record.status,
            db,
        )

    db.commit()
    logger.info(
        "Teacher %s marked attendance for course %d, period %d.%d on %s",
        current_user.username, data.course_id, data.period, data.sub_period, data.date
    )
    return {"message": f"Attendance marked for period {data.period}.{data.sub_period}"}


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

    enrollments = _get_course_enrollments(course_id, db, section_id)

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


@router.get("/attendance/{course_id}/grid")
def attendance_grid(
    course_id: int,
    att_date: date,
    period: int = Query(..., ge=1, le=7),
    sub_period: int = Query(1, ge=1, le=4),
    section_id: int = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(teacher_required),
):
    """Rows for an attendance spreadsheet/grid for a specific slot."""
    teacher = get_teacher(current_user, db)
    _verify_course_access(teacher, course_id, db)

    rows = []
    for enrollment in _get_course_enrollments(course_id, db, section_id):
        slot = next(
            (
                a for a in enrollment.attendances
                if a.date == att_date and a.period == period and a.sub_period == sub_period
            ),
            None,
        )
        rows.append({
            "student_id": enrollment.student.id,
            "roll_number": enrollment.student.roll_number,
            "student_name": _student_name(enrollment.student),
            "section": enrollment.student.section.name if enrollment.student.section else None,
            "date": str(att_date),
            "period": period,
            "sub_period": sub_period,
            "status": slot.status.value if slot else None,
        })
    return rows


@router.get("/attendance/{course_id}/template")
def attendance_csv_template(
    course_id: int,
    att_date: date,
    period: int = Query(..., ge=1, le=7),
    sub_period: int = Query(1, ge=1, le=4),
    section_id: int = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(teacher_required),
):
    """Download a strict CSV template for attendance bulk entry."""
    rows = attendance_grid(course_id, att_date, period, sub_period, section_id, db, current_user)
    fieldnames = ["roll_number", "student_name", "section", "date", "period", "sub_period", "status"]
    return _csv_response(
        f"attendance_course_{course_id}_{att_date}_p{period}_{sub_period}.csv",
        fieldnames,
        rows,
    )


@router.post("/attendance/{course_id}/upload-csv")
def upload_attendance_csv(
    course_id: int,
    att_date: date,
    period: int = Query(..., ge=1, le=7),
    sub_period: int = Query(1, ge=1, le=4),
    section_id: int = Query(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(teacher_required),
):
    """Upload attendance from CSV keyed by roll_number."""
    teacher = get_teacher(current_user, db)
    _verify_course_access(teacher, course_id, db)

    rows = _read_csv_upload(file, {"roll_number", "status"})
    seen_rolls = set()
    for line_number, row in rows:
        roll_number = row["roll_number"]
        if not roll_number:
            raise HTTPException(status_code=400, detail=f"Missing roll_number on line {line_number}")
        if roll_number in seen_rolls:
            raise HTTPException(status_code=400, detail=f"Duplicate roll_number {roll_number} in CSV")
        seen_rolls.add(roll_number)

        enrollment = _get_enrollment_by_roll(roll_number, course_id, db, section_id)
        status = _parse_status(row["status"], line_number)
        _upsert_attendance(enrollment.id, att_date, period, sub_period, status, db)

    db.commit()
    return {"message": "Attendance CSV uploaded", "updated": len(rows)}


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

    enrollments = _get_course_enrollments(course_id, db, section_id)

    result = []
    for e in enrollments:
        day_records = [r for r in e.attendances if r.date == att_date]
        periods = {_attendance_slot_key(r): r.status.value for r in day_records}
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

    expected_max = ASSESSMENT_DEFAULT_MAX[data.type]
    if data.max_marks is not None and data.max_marks != expected_max:
        raise HTTPException(
            status_code=400,
            detail=f"{data.type.value} assessments must use max_marks={expected_max}",
        )

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

    if db.query(Assessment).filter(
        Assessment.course_id == data.course_id,
        Assessment.type == data.type,
        Assessment.name == data.name,
    ).first():
        raise HTTPException(status_code=400, detail="Assessment name already exists for this type and course")

    assessment = Assessment(
        course_id=data.course_id, name=data.name,
        type=data.type, max_marks=expected_max, date=data.date
    )
    db.add(assessment)
    db.commit()
    logger.info("Teacher %s created assessment '%s' for course %d", current_user.username, data.name, data.course_id)
    return {"message": "Assessment created", "id": assessment.id}


# ── Marks ─────────────────────────────────────────────

@router.post("/marks")
def upload_marks(data: MarksUpload, db: Session = Depends(get_db), current_user: User = Depends(teacher_required)):
    teacher = get_teacher(current_user, db)
    assessment = _get_assessment(data.assessment_id, db)

    _verify_course_access(teacher, assessment.course_id, db)

    seen_students = set()
    for entry in data.marks:
        if entry.student_id in seen_students:
            raise HTTPException(status_code=400, detail=f"Duplicate student {entry.student_id} in marks payload")
        seen_students.add(entry.student_id)
        _get_enrollment_for_student(entry.student_id, assessment.course_id, db)
        # Validate marks don't exceed max
        if entry.marks_obtained > assessment.max_marks:
            raise HTTPException(
                status_code=400,
                detail=f"Marks {entry.marks_obtained} exceed max {assessment.max_marks} for student {entry.student_id}"
            )
        _upsert_mark(data.assessment_id, entry.student_id, entry.marks_obtained, db)
    db.commit()
    logger.info("Teacher %s uploaded marks for assessment %d", current_user.username, data.assessment_id)
    return {"message": "Marks uploaded successfully"}


@router.get("/marks/{assessment_id}/grid")
def marks_grid(
    assessment_id: int,
    section_id: int = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(teacher_required),
):
    """Rows for a marks spreadsheet/grid, including students without marks yet."""
    teacher = get_teacher(current_user, db)
    assessment = _get_assessment(assessment_id, db)
    _verify_course_access(teacher, assessment.course_id, db)

    existing_marks = {
        mark.student_id: mark.marks_obtained
        for mark in db.query(Mark).filter(Mark.assessment_id == assessment_id).all()
    }
    rows = []
    for enrollment in _get_course_enrollments(assessment.course_id, db, section_id):
        rows.append({
            "student_id": enrollment.student.id,
            "roll_number": enrollment.student.roll_number,
            "student_name": _student_name(enrollment.student),
            "section": enrollment.student.section.name if enrollment.student.section else None,
            "assessment_id": assessment_id,
            "assessment_name": assessment.name,
            "assessment_type": assessment.type.value,
            "marks_obtained": existing_marks.get(enrollment.student.id),
            "max_marks": assessment.max_marks,
        })
    return rows


@router.get("/marks/{assessment_id}/template")
def marks_csv_template(
    assessment_id: int,
    section_id: int = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(teacher_required),
):
    """Download a strict CSV template for marks bulk entry."""
    rows = marks_grid(assessment_id, section_id, db, current_user)
    fieldnames = ["roll_number", "student_name", "section", "marks_obtained", "max_marks"]
    return _csv_response(f"marks_assessment_{assessment_id}.csv", fieldnames, rows)


@router.post("/marks/{assessment_id}/upload-csv")
def upload_marks_csv(
    assessment_id: int,
    section_id: int = Query(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(teacher_required),
):
    """Upload marks from CSV keyed by roll_number."""
    teacher = get_teacher(current_user, db)
    assessment = _get_assessment(assessment_id, db)
    _verify_course_access(teacher, assessment.course_id, db)

    rows = _read_csv_upload(file, {"roll_number", "marks_obtained"})
    seen_rolls = set()
    for line_number, row in rows:
        roll_number = row["roll_number"]
        if not roll_number:
            raise HTTPException(status_code=400, detail=f"Missing roll_number on line {line_number}")
        if roll_number in seen_rolls:
            raise HTTPException(status_code=400, detail=f"Duplicate roll_number {roll_number} in CSV")
        seen_rolls.add(roll_number)

        try:
            marks_obtained = float(row["marks_obtained"])
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid marks_obtained on line {line_number}")
        if marks_obtained < 0 or marks_obtained > assessment.max_marks:
            raise HTTPException(
                status_code=400,
                detail=f"marks_obtained on line {line_number} must be between 0 and {assessment.max_marks}",
            )
        enrollment = _get_enrollment_by_roll(roll_number, assessment.course_id, db, section_id)
        _upsert_mark(assessment_id, enrollment.student.id, marks_obtained, db)

    db.commit()
    return {"message": "Marks CSV uploaded", "updated": len(rows)}


@router.get("/marks/{assessment_id}")
def view_marks(
    assessment_id: int,
    section_id: int = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(teacher_required),
):
    teacher = get_teacher(current_user, db)
    assessment = _get_assessment(assessment_id, db)

    _verify_course_access(teacher, assessment.course_id, db)

    marks = (
        db.query(Mark)
        .filter(Mark.assessment_id == assessment_id)
        .options(joinedload(Mark.student).joinedload(Student.section))
        .all()
    )
    if section_id is not None:
        marks = [m for m in marks if m.student.section_id == section_id]
    return [{
        "student_id": m.student.id,
        "roll_number": m.student.roll_number,
        "student_name": f"{m.student.first_name} {m.student.last_name}",
        "section": m.student.section.name if m.student.section else None,
        "marks_obtained": m.marks_obtained,
        "max_marks": assessment.max_marks
    } for m in marks]
