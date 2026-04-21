"""Seed script for a demo SMS database with course offerings and audit-ready flows."""

import random
import sys
from datetime import date, timedelta

from app.database import Base, SessionLocal, engine
from app.models import (
    ASSESSMENT_DEFAULT_MAX,
    AdmissionCategory,
    Area,
    Assessment,
    AssessmentType,
    Attendance,
    AttendanceStatus,
    Category,
    Course,
    CourseOffering,
    Enrollment,
    Gender,
    Mark,
    Role,
    Section,
    Student,
    Teacher,
    TeacherCourse,
    User,
)
from app.security import hash_password


def _default_password(dob: date) -> str:
    return dob.strftime("%d%m%Y")


def seed():
    db = SessionLocal()
    try:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

        role_admin = Role(name="ADMIN")
        role_teacher = Role(name="TEACHER")
        role_student = Role(name="STUDENT")
        db.add_all([role_admin, role_teacher, role_student])
        db.flush()

        admin_user = User(
            username="admin",
            password_hash=hash_password("admin123"),
            role_id=role_admin.id,
            must_change_password=False,
        )
        db.add(admin_user)
        db.flush()

        sec_cse_a = Section(name="A", branch_code="733", year=2024)
        sec_cse_b = Section(name="B", branch_code="733", year=2024)
        sec_ece_a = Section(name="A", branch_code="734", year=2024)
        db.add_all([sec_cse_a, sec_cse_b, sec_ece_a])
        db.flush()

        teachers_data = [
            {"first_name": "Rajesh", "last_name": "Kumar", "dob": date(1985, 3, 15), "email": "rajesh@vce.ac.in", "department": "Computer Science"},
            {"first_name": "Priya", "last_name": "Sharma", "dob": date(1988, 7, 22), "email": "priya@vce.ac.in", "department": "Computer Science"},
            {"first_name": "Amit", "last_name": "Patel", "dob": date(1982, 11, 8), "email": "amit@vce.ac.in", "department": "Computer Science"},
            {"first_name": "Sunita", "last_name": "Rao", "dob": date(1986, 4, 10), "email": "sunita@vce.ac.in", "department": "Computer Science"},
        ]
        teachers = []
        for row in teachers_data:
            user = User(
                username=f"{row['first_name'].lower()}.{row['last_name'].lower()}",
                password_hash=hash_password(_default_password(row["dob"])),
                role_id=role_teacher.id,
                must_change_password=True,
            )
            db.add(user)
            db.flush()
            teacher = Teacher(user_id=user.id, **row)
            db.add(teacher)
            db.flush()
            teachers.append(teacher)

        college_code = "1602"
        joining_year = "24"
        students_data = [
            {"first_name": "Karthik", "last_name": "Reddy", "dob": date(2007, 3, 16), "gender": Gender.MALE, "father_name": "Janga Reddy", "email": "karthik@vce.ac.in", "phone": "9876543210", "address": "Hyderabad", "branch_code": "733", "cet_qualified": "EAPCET-2024", "rank": 2969, "admission_category": AdmissionCategory.CONVENER, "category": Category.EWS, "area": Area.RURAL, "blood_group": "O+", "religion": "Hindu", "nationality": "Indian", "identification_mark1": "A MOLE ON LEFT ARM", "identification_mark2": "A MOLE ON RIGHT HAND MIDDLE FINGER", "current_year": 2, "current_semester": 3},
            {"first_name": "Diya", "last_name": "Gupta", "dob": date(2006, 5, 20), "gender": Gender.FEMALE, "father_name": "Ramesh Gupta", "email": "diya@vce.ac.in", "phone": "9876543211", "address": "Secunderabad", "branch_code": "733", "cet_qualified": "EAPCET-2024", "rank": 5432, "admission_category": AdmissionCategory.CONVENER, "category": Category.OC, "area": Area.URBAN, "blood_group": "A+", "religion": "Hindu", "nationality": "Indian", "current_year": 2, "current_semester": 3},
            {"first_name": "Aarav", "last_name": "Singh", "dob": date(2006, 1, 10), "gender": Gender.MALE, "father_name": "Vikram Singh", "email": "aarav@vce.ac.in", "phone": "9876543212", "address": "Warangal", "branch_code": "733", "cet_qualified": "EAPCET-2024", "rank": 3100, "admission_category": AdmissionCategory.CONVENER, "category": Category.BC_A, "area": Area.RURAL, "blood_group": "B+", "religion": "Hindu", "nationality": "Indian", "current_year": 2, "current_semester": 3},
            {"first_name": "Ananya", "last_name": "Sharma", "dob": date(2006, 12, 25), "gender": Gender.FEMALE, "father_name": "Suresh Sharma", "email": "ananya@vce.ac.in", "phone": "9876543213", "address": "Vijayawada", "branch_code": "733", "cet_qualified": "EAPCET-2024", "rank": 4200, "admission_category": AdmissionCategory.MANAGEMENT, "category": Category.OC, "area": Area.URBAN, "blood_group": "AB+", "religion": "Hindu", "nationality": "Indian", "current_year": 2, "current_semester": 3},
            {"first_name": "Rohan", "last_name": "Mehta", "dob": date(2006, 9, 5), "gender": Gender.MALE, "father_name": "Ajay Mehta", "email": "rohan@vce.ac.in", "phone": "9876543214", "address": "Karimnagar", "branch_code": "734", "cet_qualified": "EAPCET-2024", "rank": 7800, "admission_category": AdmissionCategory.CONVENER, "category": Category.BC_B, "area": Area.RURAL, "blood_group": "O-", "religion": "Hindu", "nationality": "Indian", "current_year": 2, "current_semester": 3},
            {"first_name": "Vikram", "last_name": "Joshi", "dob": date(2006, 6, 14), "gender": Gender.MALE, "father_name": "Prakash Joshi", "email": "vikram@vce.ac.in", "phone": "9876543215", "address": "Nizamabad", "branch_code": "734", "cet_qualified": "EAPCET-2024", "rank": 8100, "admission_category": AdmissionCategory.CONVENER, "category": Category.SC, "area": Area.URBAN, "blood_group": "A-", "religion": "Hindu", "nationality": "Indian", "current_year": 2, "current_semester": 3},
        ]

        students = []
        branch_serials = {}
        section_map = {"733": [sec_cse_a, sec_cse_b], "734": [sec_ece_a]}
        for row in students_data:
            branch_code = row["branch_code"]
            branch_serials[branch_code] = branch_serials.get(branch_code, 0) + 1
            serial = branch_serials[branch_code]
            roll_number = f"{college_code}-{joining_year}-{branch_code}-{str(serial).zfill(3)}"
            section_index = (serial - 1) // 65
            section = section_map[branch_code][min(section_index, len(section_map[branch_code]) - 1)]

            user = User(
                username=roll_number,
                password_hash=hash_password(_default_password(row["dob"])),
                role_id=role_student.id,
                must_change_password=True,
            )
            db.add(user)
            db.flush()

            student = Student(
                user_id=user.id,
                roll_number=roll_number,
                section_id=section.id,
                enrollment_date=date(2024, 9, 9),
                **row,
            )
            db.add(student)
            db.flush()
            students.append(student)

        courses_data = [
            {"code": "DS", "name": "Data Structures", "credits": 4, "department": "Computer Science"},
            {"code": "OOPJ", "name": "Object Oriented Programming in Java", "credits": 3, "department": "Computer Science"},
            {"code": "CA", "name": "Computer Architecture", "credits": 3, "department": "Computer Science"},
            {"code": "TTPS", "name": "Theory of Computation & PS", "credits": 4, "department": "Computer Science"},
            {"code": "CT", "name": "Communication Theory", "credits": 1, "department": "Computer Science"},
        ]
        courses = []
        for row in courses_data:
            course = Course(**row)
            db.add(course)
            db.flush()
            courses.append(course)

        offerings = {}
        sections = [sec_cse_a, sec_ece_a]
        for section in sections:
            for course in courses:
                offering = CourseOffering(
                    course_id=course.id,
                    academic_year=2024,
                    semester=3,
                    section_id=section.id,
                    capacity=65,
                    start_date=date(2025, 12, 15),
                    end_date=date(2026, 4, 30),
                    is_active=True,
                )
                db.add(offering)
                db.flush()
                offerings[(course.code, section.id)] = offering

        teacher_map = {
            "DS": teachers[0],
            "OOPJ": teachers[0],
            "CA": teachers[1],
            "TTPS": teachers[2],
            "CT": teachers[3],
        }
        for (course_code, _section_id), offering in offerings.items():
            db.add(TeacherCourse(teacher_id=teacher_map[course_code].id, offering_id=offering.id))

        enrollments = []
        for student in students:
            for course in courses:
                offering = offerings[(course.code, student.section_id)]
                enrollment = Enrollment(student_id=student.id, offering_id=offering.id, enrolled_date=date(2024, 9, 9))
                db.add(enrollment)
                db.flush()
                enrollments.append(enrollment)

        random.seed(42)
        base_date = date(2026, 1, 19)
        school_days = []
        current = base_date
        while len(school_days) < 20:
            if current.weekday() < 6:
                school_days.append(current)
            current += timedelta(days=1)

        for enrollment in enrollments:
            for day in school_days:
                period = random.randint(1, 7)
                status = AttendanceStatus.PRESENT if random.random() > 0.2 else AttendanceStatus.ABSENT
                db.add(Attendance(enrollment_id=enrollment.id, date=day, period=period, sub_period=1, status=status))

        for offering in offerings.values():
            enrolled_students = [enrollment.student for enrollment in enrollments if enrollment.offering_id == offering.id]
            for assessment_type, limit in {"INTERNAL": 2, "ASSIGNMENT": 3, "QUIZ": 3}.items():
                enum_type = AssessmentType(assessment_type)
                for index in range(1, limit + 1):
                    max_marks = ASSESSMENT_DEFAULT_MAX[enum_type]
                    if enum_type == AssessmentType.INTERNAL:
                        assessment_date = date(2026, 2 + index, 15)
                        name = f"Int{index}"
                        low, high = 14, 30
                    elif enum_type == AssessmentType.ASSIGNMENT:
                        assessment_date = date(2026, 2, index * 5)
                        name = f"Asst{index}"
                        low, high = 3, 5
                    else:
                        assessment_date = date(2026, 3, index * 5)
                        name = f"Quiz{index}"
                        low, high = 3, 5
                    assessment = Assessment(
                        offering_id=offering.id,
                        name=name,
                        type=enum_type,
                        max_marks=max_marks,
                        date=assessment_date,
                    )
                    db.add(assessment)
                    db.flush()
                    for student in enrolled_students:
                        db.add(
                            Mark(
                                assessment_id=assessment.id,
                                student_id=student.id,
                                marks_obtained=round(random.uniform(low, high), 0),
                            )
                        )

        db.commit()

        print("Seed data created successfully.")
        print()
        print("LOGIN CREDENTIALS")
        print("Admin:    admin / admin123")
        print("Teachers:")
        print("  rajesh.kumar / 15031985")
        print("  priya.sharma / 22071988")
        print("  amit.patel   / 08111982")
        print("  sunita.rao   / 10041986")
        print("Students:")
        print("  1602-24-733-001 / 16032007  (Karthik Reddy, CSE-A)")
        print("  1602-24-733-002 / 20052006  (Diya Gupta, CSE-A)")
        print("  1602-24-733-003 / 10012006  (Aarav Singh, CSE-A)")
        print("  1602-24-733-004 / 25122006  (Ananya Sharma, CSE-A)")
        print("  1602-24-734-001 / 05092006  (Rohan Mehta, ECE-A)")
        print("  1602-24-734-002 / 14062006  (Vikram Joshi, ECE-A)")
        print()
        print("Sections: CSE-A, CSE-B, ECE-A")
        print("Course offerings: AY 2024 / Semester 3 per section")
        print("Assessment structure per offering: 2 Internals, 3 Quizzes, 3 Assignments")
    except Exception as exc:
        db.rollback()
        print(f"Seed failed: {exc}", file=sys.stderr)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
