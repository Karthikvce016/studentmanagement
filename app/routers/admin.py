"""Admin routes — catalog, offerings, assignments, reports, and user management."""

import logging
from collections import defaultdict
from datetime import date
from typing import Union

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.dependencies import require_role
from app.models import (
    ASSESSMENT_DEFAULT_MAX,
    ASSESSMENT_LIMITS,
    Assessment,
    AssessmentType,
    Attendance,
    AttendanceStatus,
    Category,
    Course,
    CourseOffering,
    Enrollment,
    Mark,
    PasswordResetAudit,
    Role,
    Section,
    Student,
    Teacher,
    TeacherCourse,
    User,
    compute_sessional,
    parse_roll_number,
)
from app.schemas import (
    CourseCreate,
    CourseOfferingCreate,
    CourseOfferingOut,
    CourseOfferingUpdate,
    CourseOut,
    CourseUpdate,
    DashboardStats,
    SectionOut,
    StudentCreate,
    StudentOut,
    StudentUpdate,
    TeacherCreate,
    TeacherOut,
    TeacherUpdate,
)
from app.security import hash_password

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["Admin"])
admin_required = require_role("ADMIN")

COLLEGE_CODE = "1602"
SECTION_SIZE = 65


def _default_password_from_dob(dob: date) -> str:
    return dob.strftime("%d%m%Y")


def _generate_roll_number(db: Session, branch_code: str, joining_year: int) -> str:
    yy = str(joining_year)[-2:]
    existing = (
        db.query(Student)
        .filter(
            Student.branch_code == branch_code,
            Student.roll_number.like(f"{COLLEGE_CODE}-{yy}-{branch_code}-%"),
        )
        .count()
    )
    serial = str(existing + 1).zfill(3)
    return f"{COLLEGE_CODE}-{yy}-{branch_code}-{serial}"


def _get_or_create_section(db: Session, branch_code: str, joining_year: int, serial: int) -> Section:
    section_index = (serial - 1) // SECTION_SIZE
    section_name = chr(ord("A") + section_index)
    section = (
        db.query(Section)
        .filter(
            Section.name == section_name,
            Section.branch_code == branch_code,
            Section.year == joining_year,
        )
        .first()
    )
    if not section:
        section = Section(name=section_name, branch_code=branch_code, year=joining_year)
        db.add(section)
        db.flush()
    return section


def _generate_unique_username(db: Session, first_name: str, last_name: str) -> str:
    base = f"{first_name.lower()}.{last_name.lower()}"
    username = base
    counter = 1
    while db.query(User).filter(User.username == username).first():
        username = f"{base}{counter}"
        counter += 1
    return username


def _create_teacher_with_profile(db: Session, first_name: str, last_name: str, dob: date, **profile_fields) -> str:
    username = _generate_unique_username(db, first_name, last_name)
    role = db.query(Role).filter(Role.name == "TEACHER").first()
    if not role:
        raise HTTPException(status_code=500, detail="TEACHER role not found")

    user = User(
        username=username,
        password_hash=hash_password(_default_password_from_dob(dob)),
        role_id=role.id,
        must_change_password=True,
    )
    db.add(user)
    db.flush()

    teacher = Teacher(user_id=user.id, first_name=first_name, last_name=last_name, dob=dob, **profile_fields)
    db.add(teacher)
    return username


def _create_student_with_profile(db: Session, first_name: str, last_name: str, dob: date, branch_code: str, **profile_fields) -> str:
    joining_year = date.today().year
    roll_number = _generate_roll_number(db, branch_code, joining_year)
    roll_info = parse_roll_number(roll_number)
    section = _get_or_create_section(db, branch_code, joining_year, roll_info["serial"])

    role = db.query(Role).filter(Role.name == "STUDENT").first()
    if not role:
        raise HTTPException(status_code=500, detail="STUDENT role not found")

    user = User(
        username=roll_number,
        password_hash=hash_password(_default_password_from_dob(dob)),
        role_id=role.id,
        must_change_password=True,
    )
    db.add(user)
    db.flush()

    student = Student(
        user_id=user.id,
        roll_number=roll_number,
        branch_code=branch_code,
        section_id=section.id,
        first_name=first_name,
        last_name=last_name,
        dob=dob,
        enrollment_date=date.today(),
        **profile_fields,
    )
    db.add(student)
    return roll_number


def _build_student_out(student: Student) -> StudentOut:
    roll_info = {}
    if student.roll_number:
        try:
            roll_info = parse_roll_number(student.roll_number)
        except ValueError:
            roll_info = {}
    return StudentOut(
        id=student.id,
        user_id=student.user_id,
        username=student.user.username,
        roll_number=student.roll_number,
        branch_code=student.branch_code,
        roll_college_code=roll_info.get("college_code"),
        roll_joining_year=roll_info.get("joining_year"),
        roll_serial=roll_info.get("serial"),
        section_name=student.section.name if student.section else None,
        first_name=student.first_name,
        last_name=student.last_name,
        gender=student.gender.value if student.gender else None,
        dob=student.dob,
        email=student.email,
        phone=student.phone,
        address=student.address,
        father_name=student.father_name,
        enrollment_date=student.enrollment_date,
        current_year=student.current_year,
        current_semester=student.current_semester,
        blood_group=student.blood_group,
        cet_qualified=student.cet_qualified,
        rank=student.rank,
        religion=student.religion,
        nationality=student.nationality,
        admission_category=student.admission_category.value if student.admission_category else None,
        category=student.category.value if student.category else None,
        area=student.area.value if student.area else None,
        mentor_name=student.mentor_name,
        mentor_id=student.mentor_id,
        identification_mark1=student.identification_mark1,
        identification_mark2=student.identification_mark2,
        photo_url=student.photo_url,
    )


def _offering_query(db: Session):
    return db.query(CourseOffering).options(joinedload(CourseOffering.course), joinedload(CourseOffering.section))


def _build_offering_out(offering: CourseOffering) -> CourseOfferingOut:
    section_name = offering.section.name if offering.section else None
    branch_code = offering.section.branch_code if offering.section else None
    label = f"{offering.course.code} — {offering.course.name} | AY {offering.academic_year} | Sem {offering.semester}"
    if section_name:
        label += f" | Section {section_name}"
    return CourseOfferingOut(
        id=offering.id,
        course_id=offering.course_id,
        course_code=offering.course.code,
        course_name=offering.course.name,
        credits=offering.course.credits,
        department=offering.course.department,
        academic_year=offering.academic_year,
        semester=offering.semester,
        section_id=offering.section_id,
        section_name=section_name,
        branch_code=branch_code,
        capacity=offering.capacity,
        start_date=offering.start_date,
        end_date=offering.end_date,
        is_active=offering.is_active,
        label=label,
    )


def _get_offering(db: Session, offering_id: int) -> CourseOffering:
    offering = _offering_query(db).filter(CourseOffering.id == offering_id).first()
    if not offering:
        raise HTTPException(status_code=404, detail="Course offering not found")
    return offering


def _offering_duplicate_exists(db: Session, data: Union[CourseOfferingCreate, CourseOfferingUpdate], course_id: int) -> bool:
    query = db.query(CourseOffering).filter(
        CourseOffering.course_id == course_id,
        CourseOffering.academic_year == data.academic_year,
        CourseOffering.semester == data.semester,
    )
    if data.section_id is None:
        query = query.filter(CourseOffering.section_id.is_(None))
    else:
        query = query.filter(CourseOffering.section_id == data.section_id)
    return query.first() is not None


def _collect_sessional_for_enrollment(enrollment: Enrollment) -> tuple[float, float]:
    marks_by_type: dict[AssessmentType, list[float]] = defaultdict(list)
    marks_lookup = {
        mark.assessment_id: mark.marks_obtained
        for mark in enrollment.student.marks
        if mark.assessment.offering_id == enrollment.offering_id
    }
    for assessment in enrollment.course_offering.assessments:
        if assessment.id in marks_lookup:
            marks_by_type[assessment.type].append(marks_lookup[assessment.id])
    return compute_sessional(marks_by_type)


def _collect_offering_sections(offering: CourseOffering) -> list[dict]:
    by_section = {}
    if offering.section:
        by_section[offering.section.id] = {
            "section_id": offering.section.id,
            "section_name": offering.section.name,
            "branch_code": offering.section.branch_code,
            "year": offering.section.year,
            "student_count": 0,
        }
    for enrollment in offering.enrollments:
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
    return sorted(by_section.values(), key=lambda item: (item["branch_code"] or "", item["section_name"] or ""))


@router.get("/stats", response_model=DashboardStats)
def get_stats(db: Session = Depends(get_db), current_user: User = Depends(admin_required)):
    return DashboardStats(
        total_students=db.query(Student).count(),
        total_teachers=db.query(Teacher).count(),
        total_courses=db.query(Course).count(),
        total_sections=db.query(Section).count(),
        total_course_offerings=db.query(CourseOffering).count(),
    )


@router.get("/sections")
def list_sections(
    branch_code: str = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    query = db.query(Section)
    if branch_code:
        query = query.filter(Section.branch_code == branch_code)
    sections = query.all()
    return [
        SectionOut(
            id=section.id,
            name=section.name,
            branch_code=section.branch_code,
            year=section.year,
            student_count=db.query(Student).filter(Student.section_id == section.id).count(),
        )
        for section in sections
    ]


@router.get("/sections/{section_id}/students")
def section_students(section_id: int, db: Session = Depends(get_db), current_user: User = Depends(admin_required)):
    section = db.query(Section).filter(Section.id == section_id).first()
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    students = (
        db.query(Student)
        .filter(Student.section_id == section_id)
        .options(joinedload(Student.user), joinedload(Student.section))
        .all()
    )
    return [_build_student_out(student) for student in students]


@router.put("/students/{student_id}/section")
def change_student_section(
    student_id: int,
    section_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    section = db.query(Section).filter(Section.id == section_id).first()
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    student.section_id = section_id
    db.commit()
    return {"message": f"Student moved to section {section.name}"}


@router.get("/students")
def list_students(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    branch_code: str = Query(None),
    section_id: int = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    query = db.query(Student).options(joinedload(Student.user), joinedload(Student.section))
    if branch_code:
        query = query.filter(Student.branch_code == branch_code)
    if section_id:
        query = query.filter(Student.section_id == section_id)
    students = query.offset(skip).limit(limit).all()
    return [_build_student_out(student) for student in students]


@router.post("/students", status_code=status.HTTP_201_CREATED)
def create_student(data: StudentCreate, db: Session = Depends(get_db), current_user: User = Depends(admin_required)):
    optional_fields = {}
    for field in [
        "gender",
        "email",
        "phone",
        "address",
        "father_name",
        "blood_group",
        "religion",
        "nationality",
        "admission_category",
        "category",
        "area",
        "cet_qualified",
        "rank",
        "mentor_name",
        "mentor_id",
        "identification_mark1",
        "identification_mark2",
        "current_year",
        "current_semester",
    ]:
        value = getattr(data, field, None)
        if value is not None:
            optional_fields[field] = value
    roll_number = _create_student_with_profile(db, data.first_name, data.last_name, data.dob, data.branch_code, **optional_fields)
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
    return {"message": "Student updated"}


@router.post("/students/{student_id}/reset-password")
def reset_student_password(student_id: int, db: Session = Depends(get_db), current_user: User = Depends(admin_required)):
    student = db.query(Student).options(joinedload(Student.user)).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    student.user.password_hash = hash_password(_default_password_from_dob(student.dob))
    student.user.must_change_password = True
    db.add(
        PasswordResetAudit(
            admin_user_id=current_user.id,
            student_id=student.id,
            reset_value_rule="DOB_DDMMYYYY",
        )
    )
    db.commit()
    return {"message": "Student password reset to DOB (DDMMYYYY). Student must change it on next login."}


@router.delete("/students/{student_id}")
def delete_student(student_id: int, db: Session = Depends(get_db), current_user: User = Depends(admin_required)):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    user = student.user
    db.delete(student)
    db.flush()
    db.delete(user)
    db.commit()
    return {"message": "Student deleted"}


@router.get("/teachers")
def list_teachers(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    teachers = db.query(Teacher).options(joinedload(Teacher.user)).offset(skip).limit(limit).all()
    return [
        TeacherOut(
            id=teacher.id,
            user_id=teacher.user_id,
            username=teacher.user.username,
            first_name=teacher.first_name,
            last_name=teacher.last_name,
            dob=teacher.dob,
            email=teacher.email,
            phone=teacher.phone,
            department=teacher.department,
        )
        for teacher in teachers
    ]


@router.post("/teachers", status_code=status.HTTP_201_CREATED)
def create_teacher(data: TeacherCreate, db: Session = Depends(get_db), current_user: User = Depends(admin_required)):
    username = _create_teacher_with_profile(
        db,
        data.first_name,
        data.last_name,
        data.dob,
        email=data.email,
        phone=data.phone,
        department=data.department,
    )
    db.commit()
    return {"message": f"Teacher created. Username: {username}, Default password: DOB (DDMMYYYY)"}


@router.put("/teachers/{teacher_id}")
def update_teacher(teacher_id: int, data: TeacherUpdate, db: Session = Depends(get_db), current_user: User = Depends(admin_required)):
    teacher = db.query(Teacher).filter(Teacher.id == teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(teacher, field, value)
    db.commit()
    return {"message": "Teacher updated"}


@router.delete("/teachers/{teacher_id}")
def delete_teacher(teacher_id: int, db: Session = Depends(get_db), current_user: User = Depends(admin_required)):
    teacher = db.query(Teacher).filter(Teacher.id == teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")
    user = teacher.user
    db.delete(teacher)
    db.flush()
    db.delete(user)
    db.commit()
    return {"message": "Teacher deleted"}


@router.get("/courses")
def list_courses(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    courses = db.query(Course).offset(skip).limit(limit).all()
    return [CourseOut(id=course.id, code=course.code, name=course.name, credits=course.credits, department=course.department) for course in courses]


@router.post("/courses", status_code=status.HTTP_201_CREATED)
def create_course(data: CourseCreate, db: Session = Depends(get_db), current_user: User = Depends(admin_required)):
    if db.query(Course).filter(Course.code == data.code).first():
        raise HTTPException(status_code=400, detail="Course code already exists")
    course = Course(**data.model_dump())
    db.add(course)
    db.commit()
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
    return {"message": "Course deleted"}


@router.get("/course-offerings")
def list_course_offerings(
    academic_year: int = Query(None),
    semester: int = Query(None),
    section_id: int = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    query = _offering_query(db)
    if academic_year:
        query = query.filter(CourseOffering.academic_year == academic_year)
    if semester:
        query = query.filter(CourseOffering.semester == semester)
    if section_id:
        query = query.filter(CourseOffering.section_id == section_id)
    offerings = query.order_by(CourseOffering.academic_year.desc(), CourseOffering.semester.desc(), CourseOffering.id.desc()).all()
    return [_build_offering_out(offering) for offering in offerings]


@router.post("/course-offerings", status_code=status.HTTP_201_CREATED)
def create_course_offering(data: CourseOfferingCreate, db: Session = Depends(get_db), current_user: User = Depends(admin_required)):
    if not db.query(Course).filter(Course.id == data.course_id).first():
        raise HTTPException(status_code=404, detail="Course not found")
    if data.section_id and not db.query(Section).filter(Section.id == data.section_id).first():
        raise HTTPException(status_code=404, detail="Section not found")
    if _offering_duplicate_exists(db, data, data.course_id):
        raise HTTPException(status_code=400, detail="Course offering already exists for that academic scope")
    offering = CourseOffering(**data.model_dump(), is_active=True)
    db.add(offering)
    db.commit()
    db.refresh(offering)
    offering = _get_offering(db, offering.id)
    return {"message": "Course offering created", "id": offering.id, "label": _build_offering_out(offering).label}


@router.put("/course-offerings/{offering_id}")
def update_course_offering(offering_id: int, data: CourseOfferingUpdate, db: Session = Depends(get_db), current_user: User = Depends(admin_required)):
    offering = db.query(CourseOffering).filter(CourseOffering.id == offering_id).first()
    if not offering:
        raise HTTPException(status_code=404, detail="Course offering not found")
    payload = data.model_dump(exclude_unset=True)
    if "section_id" in payload and payload["section_id"] is not None:
        if not db.query(Section).filter(Section.id == payload["section_id"]).first():
            raise HTTPException(status_code=404, detail="Section not found")
    for field, value in payload.items():
        setattr(offering, field, value)
    if {"academic_year", "semester", "section_id"} & set(payload.keys()):
        duplicate = _offering_query(db).filter(
            CourseOffering.course_id == offering.course_id,
            CourseOffering.academic_year == offering.academic_year,
            CourseOffering.semester == offering.semester,
            CourseOffering.id != offering.id,
        )
        if offering.section_id is None:
            duplicate = duplicate.filter(CourseOffering.section_id.is_(None))
        else:
            duplicate = duplicate.filter(CourseOffering.section_id == offering.section_id)
        if duplicate.first():
            raise HTTPException(status_code=400, detail="Another course offering already exists for that academic scope")
    db.commit()
    return {"message": "Course offering updated"}


@router.delete("/course-offerings/{offering_id}")
def delete_course_offering(offering_id: int, db: Session = Depends(get_db), current_user: User = Depends(admin_required)):
    offering = db.query(CourseOffering).filter(CourseOffering.id == offering_id).first()
    if not offering:
        raise HTTPException(status_code=404, detail="Course offering not found")
    db.delete(offering)
    db.commit()
    return {"message": "Course offering deleted"}


@router.post("/assign-teacher")
def assign_teacher(teacher_id: int, offering_id: int, db: Session = Depends(get_db), current_user: User = Depends(admin_required)):
    if not db.query(Teacher).filter(Teacher.id == teacher_id).first():
        raise HTTPException(status_code=404, detail="Teacher not found")
    _get_offering(db, offering_id)
    if db.query(TeacherCourse).filter(TeacherCourse.teacher_id == teacher_id, TeacherCourse.offering_id == offering_id).first():
        raise HTTPException(status_code=400, detail="Already assigned")
    db.add(TeacherCourse(teacher_id=teacher_id, offering_id=offering_id))
    db.commit()
    return {"message": "Teacher assigned to offering"}


@router.delete("/unassign-teacher")
def unassign_teacher(teacher_id: int, offering_id: int, db: Session = Depends(get_db), current_user: User = Depends(admin_required)):
    assignment = db.query(TeacherCourse).filter(TeacherCourse.teacher_id == teacher_id, TeacherCourse.offering_id == offering_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    db.delete(assignment)
    db.commit()
    return {"message": "Teacher unassigned from offering"}


@router.post("/enroll")
def enroll_student(student_id: int, offering_id: int, db: Session = Depends(get_db), current_user: User = Depends(admin_required)):
    student = db.query(Student).options(joinedload(Student.section)).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    offering = _get_offering(db, offering_id)
    if offering.section_id and student.section_id != offering.section_id:
        raise HTTPException(status_code=400, detail="Student is not in the selected offering section")
    if db.query(Enrollment).filter(Enrollment.student_id == student_id, Enrollment.offering_id == offering_id).first():
        raise HTTPException(status_code=400, detail="Already enrolled")
    if offering.capacity and db.query(Enrollment).filter(Enrollment.offering_id == offering_id).count() >= offering.capacity:
        raise HTTPException(status_code=400, detail="Offering capacity reached")
    db.add(Enrollment(student_id=student_id, offering_id=offering_id, enrolled_date=date.today()))
    db.commit()
    return {"message": "Student enrolled in offering"}


@router.delete("/unenroll")
def unenroll_student(student_id: int, offering_id: int, db: Session = Depends(get_db), current_user: User = Depends(admin_required)):
    enrollment = db.query(Enrollment).filter(Enrollment.student_id == student_id, Enrollment.offering_id == offering_id).first()
    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    db.delete(enrollment)
    db.commit()
    return {"message": "Student unenrolled from offering"}


@router.get("/enrollments")
def list_enrollments(db: Session = Depends(get_db), current_user: User = Depends(admin_required)):
    enrollments = (
        db.query(Enrollment)
        .options(
            joinedload(Enrollment.student).joinedload(Student.section),
            joinedload(Enrollment.course_offering).joinedload(CourseOffering.course),
            joinedload(Enrollment.course_offering).joinedload(CourseOffering.section),
        )
        .all()
    )
    result = []
    for enrollment in enrollments:
        offering_out = _build_offering_out(enrollment.course_offering)
        result.append({
            "id": enrollment.id,
            "student_id": enrollment.student_id,
            "student_name": f"{enrollment.student.first_name} {enrollment.student.last_name}",
            "roll_number": enrollment.student.roll_number,
            "offering_id": enrollment.offering_id,
            "offering_label": offering_out.label,
            "course_code": offering_out.course_code,
            "course_name": offering_out.course_name,
            "academic_year": offering_out.academic_year,
            "semester": offering_out.semester,
            "section_name": offering_out.section_name,
            "enrolled_date": str(enrollment.enrolled_date) if enrollment.enrolled_date else None,
        })
    return result


@router.get("/teacher-assignments")
def list_teacher_assignments(db: Session = Depends(get_db), current_user: User = Depends(admin_required)):
    assignments = (
        db.query(TeacherCourse)
        .options(
            joinedload(TeacherCourse.teacher),
            joinedload(TeacherCourse.course_offering).joinedload(CourseOffering.course),
            joinedload(TeacherCourse.course_offering).joinedload(CourseOffering.section),
        )
        .all()
    )
    result = []
    for assignment in assignments:
        offering_out = _build_offering_out(assignment.course_offering)
        result.append({
            "id": assignment.id,
            "teacher_id": assignment.teacher_id,
            "teacher_name": f"{assignment.teacher.first_name} {assignment.teacher.last_name}",
            "offering_id": assignment.offering_id,
            "offering_label": offering_out.label,
            "course_code": offering_out.course_code,
            "course_name": offering_out.course_name,
            "academic_year": offering_out.academic_year,
            "semester": offering_out.semester,
            "section_name": offering_out.section_name,
        })
    return result


@router.get("/reports/attendance-risk")
def report_attendance_risk(
    threshold: float = Query(75, ge=0, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    enrollments = (
        db.query(Enrollment)
        .options(
            joinedload(Enrollment.student).joinedload(Student.section),
            joinedload(Enrollment.course_offering).joinedload(CourseOffering.course),
            joinedload(Enrollment.course_offering).joinedload(CourseOffering.section),
            joinedload(Enrollment.attendances),
        )
        .all()
    )
    result = []
    for enrollment in enrollments:
        total = len(enrollment.attendances)
        present = sum(1 for record in enrollment.attendances if record.status == AttendanceStatus.PRESENT)
        percentage = round((present / total * 100), 1) if total else 0
        if percentage < threshold:
            offering = _build_offering_out(enrollment.course_offering)
            result.append({
                "student_id": enrollment.student_id,
                "roll_number": enrollment.student.roll_number,
                "student_name": f"{enrollment.student.first_name} {enrollment.student.last_name}",
                "section": enrollment.student.section.name if enrollment.student.section else None,
                "offering_label": offering.label,
                "percentage": percentage,
                "total_periods": total,
            })
    return sorted(result, key=lambda row: row["percentage"])


@router.get("/reports/course-toppers")
def report_course_toppers(db: Session = Depends(get_db), current_user: User = Depends(admin_required)):
    offerings = _offering_query(db).options(
        joinedload(CourseOffering.enrollments).joinedload(Enrollment.student).joinedload(Student.marks).joinedload(Mark.assessment),
        joinedload(CourseOffering.section),
        joinedload(CourseOffering.course),
        joinedload(CourseOffering.assessments),
    ).all()
    result = []
    for offering in offerings:
        best_row = None
        for enrollment in offering.enrollments:
            obtained, maximum = _collect_sessional_for_enrollment(enrollment)
            percentage = round((obtained / maximum * 100), 1) if maximum else 0
            row = {
                "offering_id": offering.id,
                "offering_label": _build_offering_out(offering).label,
                "student_id": enrollment.student.id,
                "roll_number": enrollment.student.roll_number,
                "student_name": f"{enrollment.student.first_name} {enrollment.student.last_name}",
                "sessional": obtained,
                "percentage": percentage,
            }
            if best_row is None or row["percentage"] > best_row["percentage"]:
                best_row = row
        if best_row:
            result.append(best_row)
    return result


@router.get("/reports/section-performance")
def report_section_performance(db: Session = Depends(get_db), current_user: User = Depends(admin_required)):
    enrollments = (
        db.query(Enrollment)
        .options(
            joinedload(Enrollment.student).joinedload(Student.section),
            joinedload(Enrollment.student).joinedload(Student.marks).joinedload(Mark.assessment),
            joinedload(Enrollment.course_offering).joinedload(CourseOffering.assessments),
            joinedload(Enrollment.attendances),
        )
        .all()
    )
    aggregates = {}
    for enrollment in enrollments:
        section = enrollment.student.section
        key = section.id if section else 0
        if key not in aggregates:
            aggregates[key] = {
                "section_id": section.id if section else None,
                "section_name": section.name if section else "Unassigned",
                "branch_code": section.branch_code if section else enrollment.student.branch_code,
                "students": set(),
                "attendance_percentages": [],
                "sessional_percentages": [],
            }
        total = len(enrollment.attendances)
        present = sum(1 for record in enrollment.attendances if record.status == AttendanceStatus.PRESENT)
        attendance_percentage = round((present / total * 100), 1) if total else 0
        obtained, maximum = _collect_sessional_for_enrollment(enrollment)
        sessional_percentage = round((obtained / maximum * 100), 1) if maximum else 0
        aggregates[key]["students"].add(enrollment.student_id)
        aggregates[key]["attendance_percentages"].append(attendance_percentage)
        aggregates[key]["sessional_percentages"].append(sessional_percentage)
    return [
        {
            "section_id": row["section_id"],
            "section_name": row["section_name"],
            "branch_code": row["branch_code"],
            "student_count": len(row["students"]),
            "avg_attendance_percentage": round(sum(row["attendance_percentages"]) / len(row["attendance_percentages"]), 1) if row["attendance_percentages"] else 0,
            "avg_sessional_percentage": round(sum(row["sessional_percentages"]) / len(row["sessional_percentages"]), 1) if row["sessional_percentages"] else 0,
        }
        for row in aggregates.values()
    ]


@router.get("/reports/pass-fail-summary")
def report_pass_fail_summary(
    pass_mark: float = Query(40, ge=0, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_required),
):
    offerings = _offering_query(db).options(
        joinedload(CourseOffering.enrollments).joinedload(Enrollment.student).joinedload(Student.marks).joinedload(Mark.assessment),
        joinedload(CourseOffering.assessments),
        joinedload(CourseOffering.course),
        joinedload(CourseOffering.section),
    ).all()
    result = []
    for offering in offerings:
        passed = 0
        failed = 0
        for enrollment in offering.enrollments:
            obtained, maximum = _collect_sessional_for_enrollment(enrollment)
            percentage = round((obtained / maximum * 100), 1) if maximum else 0
            if percentage >= pass_mark:
                passed += 1
            else:
                failed += 1
        result.append({
            "offering_id": offering.id,
            "offering_label": _build_offering_out(offering).label,
            "passed": passed,
            "failed": failed,
            "pass_rate": round((passed / (passed + failed) * 100), 1) if (passed + failed) else 0,
        })
    return result


@router.get("/reports/attendance-trend")
def report_attendance_trend(db: Session = Depends(get_db), current_user: User = Depends(admin_required)):
    records = db.query(Attendance).all()
    by_month = defaultdict(lambda: {"present": 0, "total": 0})
    for record in records:
        month_key = record.date.strftime("%Y-%m")
        by_month[month_key]["total"] += 1
        if record.status == AttendanceStatus.PRESENT:
            by_month[month_key]["present"] += 1
    return [
        {
            "month": month,
            "present": values["present"],
            "total": values["total"],
            "percentage": round((values["present"] / values["total"] * 100), 1) if values["total"] else 0,
        }
        for month, values in sorted(by_month.items())
    ]
