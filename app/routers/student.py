"""Student routes — profile, attendance, marks report, and SGPA."""

from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.dependencies import require_role
from app.models import (
    Assessment,
    AssessmentType,
    AttendanceStatus,
    CourseOffering,
    Enrollment,
    Mark,
    Student,
    User,
    compute_grade,
    compute_sessional,
)
from app.schemas import MarksReport, SubjectMarksDetail

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


def _offering_label(offering: CourseOffering) -> str:
    label = (
        f"{offering.course.code} — {offering.course.name} | "
        f"AY {offering.academic_year} | Sem {offering.semester}"
    )
    if offering.section:
        label += f" | Section {offering.section.name}"
    return label


@router.get("/profile")
def my_profile(db: Session = Depends(get_db), current_user: User = Depends(student_required)):
    student = get_student(current_user, db)
    return {
        "id": student.id,
        "username": current_user.username,
        "roll_number": student.roll_number,
        "branch_code": student.branch_code,
        "section": student.section.name if student.section else None,
        "first_name": student.first_name,
        "last_name": student.last_name,
        "gender": student.gender.value if student.gender else None,
        "dob": str(student.dob),
        "father_name": student.father_name,
        "email": student.email,
        "phone": student.phone,
        "address": student.address,
        "photo_url": student.photo_url,
        "enrollment_date": str(student.enrollment_date) if student.enrollment_date else None,
        "current_year": student.current_year,
        "current_semester": student.current_semester,
        "blood_group": student.blood_group,
        "cet_qualified": student.cet_qualified,
        "rank": student.rank,
        "religion": student.religion,
        "nationality": student.nationality,
        "admission_category": student.admission_category.value if student.admission_category else None,
        "category": student.category.value if student.category else None,
        "area": student.area.value if student.area else None,
        "mentor_name": student.mentor_name,
        "mentor_id": student.mentor_id,
        "identification_mark1": student.identification_mark1,
        "identification_mark2": student.identification_mark2,
    }


@router.get("/attendance")
def my_attendance(db: Session = Depends(get_db), current_user: User = Depends(student_required)):
    student = get_student(current_user, db)
    enrollments = (
        db.query(Enrollment)
        .filter(Enrollment.student_id == student.id)
        .options(
            joinedload(Enrollment.course_offering).joinedload(CourseOffering.course),
            joinedload(Enrollment.course_offering).joinedload(CourseOffering.section),
            joinedload(Enrollment.attendances),
        )
        .all()
    )

    result = []
    for enrollment in enrollments:
        offering = enrollment.course_offering
        total = len(enrollment.attendances)
        present = sum(1 for record in enrollment.attendances if record.status == AttendanceStatus.PRESENT)
        result.append(
            {
                "offering_id": offering.id,
                "offering_label": _offering_label(offering),
                "course_id": offering.course.id,
                "course_code": offering.course.code,
                "course_name": offering.course.name,
                "academic_year": offering.academic_year,
                "semester": offering.semester,
                "section_name": offering.section.name if offering.section else None,
                "total_periods": total,
                "present": present,
                "absent": total - present,
                "percentage": round((present / total * 100), 1) if total > 0 else 0,
            }
        )
    return result


@router.get("/attendance/{offering_id}")
def my_attendance_detail(offering_id: int, db: Session = Depends(get_db), current_user: User = Depends(student_required)):
    student = get_student(current_user, db)
    enrollment = (
        db.query(Enrollment)
        .filter(Enrollment.student_id == student.id, Enrollment.offering_id == offering_id)
        .options(
            joinedload(Enrollment.course_offering).joinedload(CourseOffering.course),
            joinedload(Enrollment.course_offering).joinedload(CourseOffering.section),
            joinedload(Enrollment.attendances),
        )
        .first()
    )
    if not enrollment:
        raise HTTPException(status_code=404, detail="Not enrolled in this course offering")

    by_date = defaultdict(dict)
    for record in enrollment.attendances:
        key = f"period_{record.period}" if record.sub_period == 1 else f"period_{record.period}_{record.sub_period}"
        by_date[str(record.date)][key] = record.status.value

    total = len(enrollment.attendances)
    present = sum(1 for record in enrollment.attendances if record.status == AttendanceStatus.PRESENT)
    offering = enrollment.course_offering
    return {
        "offering_label": _offering_label(offering),
        "course_code": offering.course.code,
        "course_name": offering.course.name,
        "total_periods": total,
        "present": present,
        "absent": total - present,
        "percentage": round((present / total * 100), 1) if total > 0 else 0,
        "daily_detail": [{"date": day, **periods} for day, periods in sorted(by_date.items())],
    }


@router.get("/marks")
def my_marks(db: Session = Depends(get_db), current_user: User = Depends(student_required)):
    student = get_student(current_user, db)
    enrollments = (
        db.query(Enrollment)
        .filter(Enrollment.student_id == student.id)
        .options(
            joinedload(Enrollment.course_offering).joinedload(CourseOffering.course),
            joinedload(Enrollment.course_offering).joinedload(CourseOffering.section),
            joinedload(Enrollment.course_offering).joinedload(CourseOffering.assessments),
        )
        .all()
    )
    all_marks = (
        db.query(Mark)
        .filter(Mark.student_id == student.id)
        .options(joinedload(Mark.assessment).joinedload(Assessment.course_offering).joinedload(CourseOffering.course))
        .all()
    )
    marks_lookup = {mark.assessment_id: mark.marks_obtained for mark in all_marks}

    subjects = []
    total_credits = 0
    total_grade_points = 0
    total_sessional_max = 0
    total_sessional_secured = 0

    for enrollment in enrollments:
        offering = enrollment.course_offering
        course = offering.course

        assessments_by_type = defaultdict(list)
        for assessment in offering.assessments:
            assessments_by_type[assessment.type].append(assessment)
        for assessment_type in assessments_by_type:
            assessments_by_type[assessment_type].sort(key=lambda item: item.name)

        internals = assessments_by_type.get(AssessmentType.INTERNAL, [])
        quizzes = assessments_by_type.get(AssessmentType.QUIZ, [])
        assignments = assessments_by_type.get(AssessmentType.ASSIGNMENT, [])

        def get_marks(assessment_list, index):
            if index < len(assessment_list):
                assessment = assessment_list[index]
                return marks_lookup.get(assessment.id)
            return None

        def get_max(assessment_list, index, default):
            if index < len(assessment_list):
                return assessment_list[index].max_marks
            return default

        marks_by_type = {}
        for assessment_type, assessment_list in assessments_by_type.items():
            marks_by_type[assessment_type] = [
                marks_lookup.get(assessment.id, 0) for assessment in assessment_list if assessment.id in marks_lookup
            ]

        sessional_secured, sessional_max = compute_sessional(marks_by_type)
        sessional_pct = (sessional_secured / sessional_max * 100) if sessional_max > 0 else 0
        grade, grade_points = compute_grade(sessional_pct)

        subjects.append(
            SubjectMarksDetail(
                subject_code=course.code,
                subject_name=course.name,
                offering_label=_offering_label(offering),
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
                grade_points=grade_points,
            )
        )

        total_credits += course.credits
        total_grade_points += grade_points * course.credits
        total_sessional_max += sessional_max
        total_sessional_secured += sessional_secured

    sgpa = round(total_grade_points / total_credits, 2) if total_credits > 0 else 0
    sessional_pct = round((total_sessional_secured / total_sessional_max * 100), 2) if total_sessional_max > 0 else 0

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


@router.get("/marks/flat")
def my_marks_flat(db: Session = Depends(get_db), current_user: User = Depends(student_required)):
    student = get_student(current_user, db)
    marks = (
        db.query(Mark)
        .filter(Mark.student_id == student.id)
        .options(
            joinedload(Mark.assessment).joinedload(Assessment.course_offering).joinedload(CourseOffering.course),
            joinedload(Mark.assessment).joinedload(Assessment.course_offering).joinedload(CourseOffering.section),
        )
        .all()
    )

    result = []
    for mark in marks:
        offering = mark.assessment.course_offering
        result.append(
            {
                "course_code": offering.course.code,
                "course_name": offering.course.name,
                "offering_label": _offering_label(offering),
                "assessment_name": mark.assessment.name,
                "assessment_type": mark.assessment.type.value,
                "marks_obtained": mark.marks_obtained,
                "max_marks": mark.assessment.max_marks,
                "percentage": round((mark.marks_obtained / mark.assessment.max_marks * 100), 1)
                if mark.assessment.max_marks > 0
                else 0,
            }
        )
    return result
