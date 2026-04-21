"""Teacher routes — offerings, attendance, assessments, marks, and audits."""

import csv
import io
import logging
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.dependencies import require_role
from app.models import (
    ASSESSMENT_DEFAULT_MAX,
    ASSESSMENT_LIMITS,
    Assessment,
    Attendance,
    AttendanceAudit,
    AttendanceStatus,
    CourseOffering,
    Enrollment,
    Mark,
    MarkAudit,
    Student,
    Teacher,
    TeacherCourse,
    User,
)
from app.schemas import AttendanceMark, AssessmentCreate, MarksUpload

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/teacher", tags=["Teacher"])
teacher_required = require_role("TEACHER")


def get_teacher(current_user: User, db: Session) -> Teacher:
    teacher = db.query(Teacher).filter(Teacher.user_id == current_user.id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher profile not found")
    return teacher


def _offering_label(offering: CourseOffering) -> str:
    label = (
        f"{offering.course.code} — {offering.course.name} | "
        f"AY {offering.academic_year} | Sem {offering.semester}"
    )
    if offering.section:
        label += f" | Section {offering.section.name}"
    return label


def _verify_offering_access(teacher: Teacher, offering_id: int, db: Session) -> TeacherCourse:
    assignment = (
        db.query(TeacherCourse)
        .filter(TeacherCourse.teacher_id == teacher.id, TeacherCourse.offering_id == offering_id)
        .options(
            joinedload(TeacherCourse.course_offering).joinedload(CourseOffering.course),
            joinedload(TeacherCourse.course_offering).joinedload(CourseOffering.section),
        )
        .first()
    )
    if not assignment:
        raise HTTPException(status_code=403, detail="You are not assigned to this course offering")
    return assignment


def _student_name(student: Student) -> str:
    return f"{student.first_name} {student.last_name}"


def _get_offering_enrollments(offering_id: int, db: Session, section_id: Optional[int] = None) -> List[Enrollment]:
    query = (
        db.query(Enrollment)
        .filter(Enrollment.offering_id == offering_id)
        .options(
            joinedload(Enrollment.student).joinedload(Student.section),
            joinedload(Enrollment.attendances),
        )
    )
    if section_id is not None:
        query = query.join(Student).filter(Student.section_id == section_id)
    enrollments = query.all()
    return sorted(enrollments, key=lambda enrollment: enrollment.student.roll_number or "")


def _get_assessment(assessment_id: int, db: Session) -> Assessment:
    assessment = (
        db.query(Assessment)
        .filter(Assessment.id == assessment_id)
        .options(
            joinedload(Assessment.course_offering).joinedload(CourseOffering.course),
            joinedload(Assessment.course_offering).joinedload(CourseOffering.section),
            joinedload(Assessment.marks),
        )
        .first()
    )
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return assessment


def _get_enrollment_for_student(student_id: int, offering_id: int, db: Session) -> Enrollment:
    enrollment = (
        db.query(Enrollment)
        .filter(Enrollment.student_id == student_id, Enrollment.offering_id == offering_id)
        .first()
    )
    if not enrollment:
        raise HTTPException(status_code=400, detail=f"Student {student_id} is not enrolled in this offering")
    return enrollment


def _get_enrollment_by_roll(
    roll_number: str,
    offering_id: int,
    db: Session,
    section_id: Optional[int] = None,
) -> Enrollment:
    enrollment = (
        db.query(Enrollment)
        .join(Student)
        .filter(Enrollment.offering_id == offering_id, Student.roll_number == roll_number)
        .options(joinedload(Enrollment.student).joinedload(Student.section))
        .first()
    )
    if not enrollment:
        raise HTTPException(status_code=400, detail=f"Roll number {roll_number} is not enrolled in this offering")
    if section_id is not None and enrollment.student.section_id != section_id:
        raise HTTPException(status_code=400, detail=f"Roll number {roll_number} is not in the selected section")
    return enrollment


def _upsert_attendance(
    enrollment: Enrollment,
    teacher_id: int,
    att_date: date,
    period: int,
    sub_period: int,
    status: AttendanceStatus,
    db: Session,
) -> None:
    existing = (
        db.query(Attendance)
        .filter(
            Attendance.enrollment_id == enrollment.id,
            Attendance.date == att_date,
            Attendance.period == period,
            Attendance.sub_period == sub_period,
        )
        .first()
    )
    if existing:
        old_status = existing.status
        if old_status == status:
            return
        existing.status = status
        action = "UPDATE"
    else:
        old_status = None
        db.add(
            Attendance(
                enrollment_id=enrollment.id,
                date=att_date,
                period=period,
                sub_period=sub_period,
                status=status,
            )
        )
        action = "CREATE"

    db.add(
        AttendanceAudit(
            teacher_id=teacher_id,
            enrollment_id=enrollment.id,
            action=action,
            date=att_date,
            period=period,
            sub_period=sub_period,
            old_status=old_status,
            new_status=status,
        )
    )


def _upsert_mark(
    assessment_id: int,
    student_id: int,
    teacher_id: int,
    marks_obtained: float,
    db: Session,
) -> None:
    existing = (
        db.query(Mark)
        .filter(Mark.assessment_id == assessment_id, Mark.student_id == student_id)
        .first()
    )
    if existing:
        old_marks = existing.marks_obtained
        if old_marks == marks_obtained:
            return
        existing.marks_obtained = marks_obtained
    else:
        old_marks = None
        db.add(Mark(assessment_id=assessment_id, student_id=student_id, marks_obtained=marks_obtained))

    db.add(
        MarkAudit(
            teacher_id=teacher_id,
            assessment_id=assessment_id,
            student_id=student_id,
            old_marks=old_marks,
            new_marks=marks_obtained,
        )
    )


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
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="CSV must be UTF-8 encoded") from exc

    reader = csv.DictReader(io.StringIO(text))
    fieldnames = set(reader.fieldnames or [])
    missing = required_columns - fieldnames
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing CSV columns: {', '.join(sorted(missing))}")

    rows = []
    for line_number, row in enumerate(reader, start=2):
        rows.append((line_number, {key: (value or "").strip() for key, value in row.items()}))
    if not rows:
        raise HTTPException(status_code=400, detail="CSV has no data rows")
    return rows


def _parse_status(value: str, line_number: int) -> AttendanceStatus:
    normalized = value.strip().upper()
    aliases = {"P": "PRESENT", "A": "ABSENT"}
    normalized = aliases.get(normalized, normalized)
    try:
        return AttendanceStatus(normalized)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid attendance status on line {line_number}") from exc


@router.get("/courses")
@router.get("/offerings")
def my_courses(db: Session = Depends(get_db), current_user: User = Depends(teacher_required)):
    teacher = get_teacher(current_user, db)
    assignments = (
        db.query(TeacherCourse)
        .filter(TeacherCourse.teacher_id == teacher.id)
        .options(
            joinedload(TeacherCourse.course_offering).joinedload(CourseOffering.course),
            joinedload(TeacherCourse.course_offering).joinedload(CourseOffering.section),
            joinedload(TeacherCourse.course_offering).joinedload(CourseOffering.enrollments),
        )
        .all()
    )
    result = []
    for assignment in assignments:
        offering = assignment.course_offering
        result.append(
            {
                "id": offering.id,
                "course_id": offering.course.id,
                "code": offering.course.code,
                "name": offering.course.name,
                "credits": offering.course.credits,
                "department": offering.course.department,
                "academic_year": offering.academic_year,
                "semester": offering.semester,
                "section_id": offering.section_id,
                "section_name": offering.section.name if offering.section else None,
                "student_count": len(offering.enrollments),
                "label": _offering_label(offering),
            }
        )
    return sorted(result, key=lambda row: (row["academic_year"], row["semester"], row["code"]), reverse=True)


@router.get("/courses/{offering_id}/sections")
def course_sections(offering_id: int, db: Session = Depends(get_db), current_user: User = Depends(teacher_required)):
    teacher = get_teacher(current_user, db)
    assignment = _verify_offering_access(teacher, offering_id, db)
    offering = assignment.course_offering

    by_section = {}
    if offering.section:
        by_section[offering.section.id] = {
            "section_id": offering.section.id,
            "section_name": offering.section.name,
            "branch_code": offering.section.branch_code,
            "year": offering.section.year,
            "student_count": 0,
        }

    for enrollment in _get_offering_enrollments(offering_id, db):
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
    return sorted(by_section.values(), key=lambda row: (row["branch_code"] or "", row["section_name"] or ""))


@router.get("/courses/{offering_id}/students")
def course_students(
    offering_id: int,
    section_id: int = Query(None, description="Filter by section"),
    db: Session = Depends(get_db),
    current_user: User = Depends(teacher_required),
):
    teacher = get_teacher(current_user, db)
    _verify_offering_access(teacher, offering_id, db)

    enrollments = _get_offering_enrollments(offering_id, db, section_id)
    return [
        {
            "student_id": enrollment.student.id,
            "roll_number": enrollment.student.roll_number,
            "first_name": enrollment.student.first_name,
            "last_name": enrollment.student.last_name,
            "section": enrollment.student.section.name if enrollment.student.section else None,
            "email": enrollment.student.email,
            "enrollment_id": enrollment.id,
        }
        for enrollment in enrollments
    ]


@router.post("/attendance")
def mark_attendance(data: AttendanceMark, db: Session = Depends(get_db), current_user: User = Depends(teacher_required)):
    teacher = get_teacher(current_user, db)
    _verify_offering_access(teacher, data.offering_id, db)

    for record in data.records:
        enrollment = _get_enrollment_for_student(record.student_id, data.offering_id, db)
        _upsert_attendance(
            enrollment=enrollment,
            teacher_id=teacher.id,
            att_date=data.date,
            period=data.period,
            sub_period=data.sub_period,
            status=record.status,
            db=db,
        )

    db.commit()
    logger.info(
        "Teacher %s marked attendance for offering %d, period %d.%d on %s",
        current_user.username,
        data.offering_id,
        data.period,
        data.sub_period,
        data.date,
    )
    return {"message": f"Attendance marked for period {data.period}.{data.sub_period}"}


@router.get("/attendance/{offering_id}")
def view_attendance(
    offering_id: int,
    section_id: int = Query(None, description="Filter by section"),
    db: Session = Depends(get_db),
    current_user: User = Depends(teacher_required),
):
    teacher = get_teacher(current_user, db)
    assignment = _verify_offering_access(teacher, offering_id, db)
    offering = assignment.course_offering

    enrollments = _get_offering_enrollments(offering_id, db, section_id)
    result = []
    for enrollment in enrollments:
        records = enrollment.attendances
        total = len(records)
        present = sum(1 for record in records if record.status == AttendanceStatus.PRESENT)
        result.append(
            {
                "student_id": enrollment.student.id,
                "roll_number": enrollment.student.roll_number,
                "student_name": _student_name(enrollment.student),
                "section": enrollment.student.section.name if enrollment.student.section else None,
                "total_periods": total,
                "present": present,
                "absent": total - present,
                "percentage": round((present / total * 100), 1) if total > 0 else 0,
                "offering_label": _offering_label(offering),
            }
        )
    return result


@router.get("/attendance/{offering_id}/grid")
def attendance_grid(
    offering_id: int,
    att_date: date,
    period: int = Query(..., ge=1, le=7),
    sub_period: int = Query(1, ge=1, le=4),
    section_id: int = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(teacher_required),
):
    teacher = get_teacher(current_user, db)
    _verify_offering_access(teacher, offering_id, db)

    rows = []
    for enrollment in _get_offering_enrollments(offering_id, db, section_id):
        slot = next(
            (
                attendance
                for attendance in enrollment.attendances
                if attendance.date == att_date and attendance.period == period and attendance.sub_period == sub_period
            ),
            None,
        )
        rows.append(
            {
                "student_id": enrollment.student.id,
                "roll_number": enrollment.student.roll_number,
                "student_name": _student_name(enrollment.student),
                "section": enrollment.student.section.name if enrollment.student.section else None,
                "date": str(att_date),
                "period": period,
                "sub_period": sub_period,
                "status": slot.status.value if slot else None,
            }
        )
    return rows


@router.get("/attendance/{offering_id}/template")
def attendance_csv_template(
    offering_id: int,
    att_date: date,
    period: int = Query(..., ge=1, le=7),
    sub_period: int = Query(1, ge=1, le=4),
    section_id: int = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(teacher_required),
):
    rows = attendance_grid(offering_id, att_date, period, sub_period, section_id, db, current_user)
    fieldnames = ["roll_number", "student_name", "section", "date", "period", "sub_period", "status"]
    return _csv_response(
        f"attendance_offering_{offering_id}_{att_date}_p{period}_{sub_period}.csv",
        fieldnames,
        rows,
    )


@router.post("/attendance/{offering_id}/upload-csv")
def upload_attendance_csv(
    offering_id: int,
    att_date: date,
    period: int = Query(..., ge=1, le=7),
    sub_period: int = Query(1, ge=1, le=4),
    section_id: int = Query(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(teacher_required),
):
    teacher = get_teacher(current_user, db)
    _verify_offering_access(teacher, offering_id, db)

    rows = _read_csv_upload(file, {"roll_number", "status"})
    seen_rolls = set()
    for line_number, row in rows:
        roll_number = row["roll_number"]
        if not roll_number:
            raise HTTPException(status_code=400, detail=f"Missing roll_number on line {line_number}")
        if roll_number in seen_rolls:
            raise HTTPException(status_code=400, detail=f"Duplicate roll_number {roll_number} in CSV")
        seen_rolls.add(roll_number)

        enrollment = _get_enrollment_by_roll(roll_number, offering_id, db, section_id)
        status = _parse_status(row["status"], line_number)
        _upsert_attendance(enrollment, teacher.id, att_date, period, sub_period, status, db)

    db.commit()
    return {"message": "Attendance CSV uploaded", "updated": len(rows)}


@router.get("/attendance/{offering_id}/date/{att_date}")
def view_attendance_by_date(
    offering_id: int,
    att_date: date,
    section_id: int = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(teacher_required),
):
    teacher = get_teacher(current_user, db)
    _verify_offering_access(teacher, offering_id, db)

    enrollments = _get_offering_enrollments(offering_id, db, section_id)
    result = []
    for enrollment in enrollments:
        day_records = [record for record in enrollment.attendances if record.date == att_date]
        periods = {_attendance_slot_key(record): record.status.value for record in day_records}
        result.append(
            {
                "student_id": enrollment.student.id,
                "roll_number": enrollment.student.roll_number,
                "student_name": _student_name(enrollment.student),
                "section": enrollment.student.section.name if enrollment.student.section else None,
                "periods": periods,
            }
        )
    return result


@router.get("/assessments/{offering_id}")
def list_assessments(offering_id: int, db: Session = Depends(get_db), current_user: User = Depends(teacher_required)):
    teacher = get_teacher(current_user, db)
    _verify_offering_access(teacher, offering_id, db)

    assessments = db.query(Assessment).filter(Assessment.offering_id == offering_id).all()
    return [
        {
            "id": assessment.id,
            "name": assessment.name,
            "type": assessment.type.value,
            "max_marks": assessment.max_marks,
            "date": str(assessment.date) if assessment.date else None,
        }
        for assessment in assessments
    ]


@router.post("/assessments")
def create_assessment(data: AssessmentCreate, db: Session = Depends(get_db), current_user: User = Depends(teacher_required)):
    teacher = get_teacher(current_user, db)
    _verify_offering_access(teacher, data.offering_id, db)

    expected_max = ASSESSMENT_DEFAULT_MAX[data.type]
    if data.max_marks is not None and data.max_marks != expected_max:
        raise HTTPException(
            status_code=400,
            detail=f"{data.type.value} assessments must use max_marks={expected_max}",
        )

    existing_count = (
        db.query(Assessment)
        .filter(Assessment.offering_id == data.offering_id, Assessment.type == data.type)
        .count()
    )
    limit = ASSESSMENT_LIMITS.get(data.type, 99)
    if existing_count >= limit:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {limit} {data.type.value.lower()}s allowed per offering. Already have {existing_count}.",
        )

    duplicate = (
        db.query(Assessment)
        .filter(
            Assessment.offering_id == data.offering_id,
            Assessment.type == data.type,
            Assessment.name == data.name,
        )
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=400, detail="Assessment name already exists for this type and offering")

    assessment = Assessment(
        offering_id=data.offering_id,
        name=data.name,
        type=data.type,
        max_marks=expected_max,
        date=data.date,
    )
    db.add(assessment)
    db.commit()
    logger.info("Teacher %s created assessment '%s' for offering %d", current_user.username, data.name, data.offering_id)
    return {"message": "Assessment created", "id": assessment.id}


@router.post("/marks")
def upload_marks(data: MarksUpload, db: Session = Depends(get_db), current_user: User = Depends(teacher_required)):
    teacher = get_teacher(current_user, db)
    assessment = _get_assessment(data.assessment_id, db)
    _verify_offering_access(teacher, assessment.offering_id, db)

    seen_students = set()
    for entry in data.marks:
        if entry.student_id in seen_students:
            raise HTTPException(status_code=400, detail=f"Duplicate student {entry.student_id} in marks payload")
        seen_students.add(entry.student_id)
        _get_enrollment_for_student(entry.student_id, assessment.offering_id, db)
        if entry.marks_obtained > assessment.max_marks:
            raise HTTPException(
                status_code=400,
                detail=f"Marks {entry.marks_obtained} exceed max {assessment.max_marks} for student {entry.student_id}",
            )
        _upsert_mark(data.assessment_id, entry.student_id, teacher.id, entry.marks_obtained, db)

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
    teacher = get_teacher(current_user, db)
    assessment = _get_assessment(assessment_id, db)
    _verify_offering_access(teacher, assessment.offering_id, db)

    marks_lookup = {mark.student_id: mark.marks_obtained for mark in assessment.marks}
    rows = []
    for enrollment in _get_offering_enrollments(assessment.offering_id, db, section_id):
        rows.append(
            {
                "student_id": enrollment.student.id,
                "roll_number": enrollment.student.roll_number,
                "student_name": _student_name(enrollment.student),
                "section": enrollment.student.section.name if enrollment.student.section else None,
                "marks_obtained": marks_lookup.get(enrollment.student.id),
                "max_marks": assessment.max_marks,
            }
        )
    return rows


@router.get("/marks/{assessment_id}/template")
def marks_csv_template(
    assessment_id: int,
    section_id: int = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(teacher_required),
):
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
    teacher = get_teacher(current_user, db)
    assessment = _get_assessment(assessment_id, db)
    _verify_offering_access(teacher, assessment.offering_id, db)

    rows = _read_csv_upload(file, {"roll_number", "marks_obtained"})
    seen_rolls = set()
    for line_number, row in rows:
        roll_number = row["roll_number"]
        if not roll_number:
            raise HTTPException(status_code=400, detail=f"Missing roll_number on line {line_number}")
        if roll_number in seen_rolls:
            raise HTTPException(status_code=400, detail=f"Duplicate roll_number {roll_number} in CSV")
        seen_rolls.add(roll_number)

        enrollment = _get_enrollment_by_roll(roll_number, assessment.offering_id, db, section_id)
        try:
            marks_obtained = float(row["marks_obtained"])
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid marks_obtained on line {line_number}") from exc
        if marks_obtained < 0:
            raise HTTPException(status_code=400, detail=f"Marks cannot be negative on line {line_number}")
        if marks_obtained > assessment.max_marks:
            raise HTTPException(
                status_code=400,
                detail=f"Marks {marks_obtained} exceed max {assessment.max_marks} on line {line_number}",
            )
        _upsert_mark(assessment_id, enrollment.student_id, teacher.id, marks_obtained, db)

    db.commit()
    return {"message": "Marks CSV uploaded", "updated": len(rows)}
