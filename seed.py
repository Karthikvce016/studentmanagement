"""Seed script — creates sample data matching VCE college structure.

Run:  python seed.py
Note: This DROPS all existing data before re-seeding.
"""

import sys
from datetime import date, timedelta
import random
from sqlalchemy import text
from app.database import SessionLocal, engine, Base
from app.models import (
    Role, User, Student, Teacher, Course, TeacherCourse,
    Enrollment, Assessment, AssessmentType, Attendance, AttendanceStatus,
    Mark, Section, Gender, AdmissionCategory, Category, Area,
    ASSESSMENT_LIMITS
)
from app.security import hash_password

# Create all tables
Base.metadata.create_all(bind=engine)


def seed():
    db = SessionLocal()

    try:
        # Clear existing data in reverse dependency order
        for model in [Mark, Attendance, Assessment, Enrollment, TeacherCourse,
                      Course, Student, Teacher, User, Role, Section]:
            db.query(model).delete()
        db.commit()

        # ── Roles ──
        role_admin = Role(name="ADMIN")
        role_teacher = Role(name="TEACHER")
        role_student = Role(name="STUDENT")
        db.add_all([role_admin, role_teacher, role_student])
        db.flush()

        # ── Admin User ──
        admin_user = User(username="admin", password_hash=hash_password("admin123"),
                          role_id=role_admin.id, must_change_password=False)
        db.add(admin_user)
        db.flush()

        # ── Sections ──
        sec_cse_a = Section(name="A", branch_code="733", year=2024)
        sec_cse_b = Section(name="B", branch_code="733", year=2024)
        sec_ece_a = Section(name="A", branch_code="734", year=2024)
        db.add_all([sec_cse_a, sec_cse_b, sec_ece_a])
        db.flush()

        # ── Teachers ──
        teachers_data = [
            {"first_name": "Rajesh", "last_name": "Kumar", "dob": date(1985, 3, 15),
             "email": "rajesh@vce.ac.in", "department": "Computer Science"},
            {"first_name": "Priya", "last_name": "Sharma", "dob": date(1988, 7, 22),
             "email": "priya@vce.ac.in", "department": "Computer Science"},
            {"first_name": "Amit", "last_name": "Patel", "dob": date(1982, 11, 8),
             "email": "amit@vce.ac.in", "department": "Computer Science"},
            {"first_name": "Sunita", "last_name": "Rao", "dob": date(1986, 4, 10),
             "email": "sunita@vce.ac.in", "department": "Computer Science"},
        ]
        teachers = []
        for td in teachers_data:
            user = User(
                username=f"{td['first_name'].lower()}.{td['last_name'].lower()}",
                password_hash=hash_password(td['dob'].strftime("%d%m%Y")),
                role_id=role_teacher.id, must_change_password=True
            )
            db.add(user)
            db.flush()
            t = Teacher(user_id=user.id, **td)
            db.add(t)
            db.flush()
            teachers.append(t)

        # ── Students (VCE-style) ──
        COLLEGE_CODE = "1602"
        joining_year = "24"
        categories = [Category.OC, Category.BC_A, Category.BC_B, Category.EWS, Category.SC]
        areas = [Area.RURAL, Area.URBAN]
        blood_groups = ["O+", "A+", "B+", "AB+", "O-", "A-"]

        students_data = [
            {"first_name": "Karthik", "last_name": "Reddy", "dob": date(2007, 3, 16),
             "gender": Gender.MALE, "father_name": "Janga Reddy",
             "email": "karthik@vce.ac.in", "phone": "9876543210", "address": "Hyderabad",
             "branch_code": "733", "cet_qualified": "EAPCET-2024", "rank": 2969,
             "admission_category": AdmissionCategory.CONVENER, "category": Category.EWS,
             "area": Area.RURAL, "blood_group": "O+", "religion": "Hindu", "nationality": "Indian",
             "identification_mark1": "A MOLE ON LEFT ARM", "identification_mark2": "A MOLE ON RIGHT HAND MIDDLE FINGER",
             "current_year": 2, "current_semester": 3},

            {"first_name": "Diya", "last_name": "Gupta", "dob": date(2006, 5, 20),
             "gender": Gender.FEMALE, "father_name": "Ramesh Gupta",
             "email": "diya@vce.ac.in", "phone": "9876543211", "address": "Secunderabad",
             "branch_code": "733", "cet_qualified": "EAPCET-2024", "rank": 5432,
             "admission_category": AdmissionCategory.CONVENER, "category": Category.OC,
             "area": Area.URBAN, "blood_group": "A+", "religion": "Hindu",
             "current_year": 2, "current_semester": 3},

            {"first_name": "Aarav", "last_name": "Singh", "dob": date(2006, 1, 10),
             "gender": Gender.MALE, "father_name": "Vikram Singh",
             "email": "aarav@vce.ac.in", "phone": "9876543212", "address": "Warangal",
             "branch_code": "733", "cet_qualified": "EAPCET-2024", "rank": 3100,
             "admission_category": AdmissionCategory.CONVENER, "category": Category.BC_A,
             "area": Area.RURAL, "blood_group": "B+",
             "current_year": 2, "current_semester": 3},

            {"first_name": "Ananya", "last_name": "Sharma", "dob": date(2006, 12, 25),
             "gender": Gender.FEMALE, "father_name": "Suresh Sharma",
             "email": "ananya@vce.ac.in", "phone": "9876543213", "address": "Vijayawada",
             "branch_code": "733", "cet_qualified": "EAPCET-2024", "rank": 4200,
             "admission_category": AdmissionCategory.MANAGEMENT, "category": Category.OC,
             "area": Area.URBAN, "blood_group": "AB+",
             "current_year": 2, "current_semester": 3},

            {"first_name": "Rohan", "last_name": "Mehta", "dob": date(2006, 9, 5),
             "gender": Gender.MALE, "father_name": "Ajay Mehta",
             "email": "rohan@vce.ac.in", "phone": "9876543214", "address": "Karimnagar",
             "branch_code": "734", "cet_qualified": "EAPCET-2024", "rank": 7800,
             "admission_category": AdmissionCategory.CONVENER, "category": Category.BC_B,
             "area": Area.RURAL, "blood_group": "O-",
             "current_year": 2, "current_semester": 3},

            {"first_name": "Vikram", "last_name": "Joshi", "dob": date(2006, 6, 14),
             "gender": Gender.MALE, "father_name": "Prakash Joshi",
             "email": "vikram@vce.ac.in", "phone": "9876543215", "address": "Nizamabad",
             "branch_code": "734", "cet_qualified": "EAPCET-2024", "rank": 8100,
             "admission_category": AdmissionCategory.CONVENER, "category": Category.SC,
             "area": Area.URBAN, "blood_group": "A-",
             "current_year": 2, "current_semester": 3},
        ]

        students = []
        branch_serials = {}
        section_map = {"733": [sec_cse_a, sec_cse_b], "734": [sec_ece_a]}

        for sd in students_data:
            bc = sd["branch_code"]
            branch_serials[bc] = branch_serials.get(bc, 0) + 1
            serial = branch_serials[bc]
            roll = f"{COLLEGE_CODE}-{joining_year}-{bc}-{str(serial).zfill(3)}"

            # Auto-assign section: first 65 → A, next 65 → B
            section_index = (serial - 1) // 65
            sections_for_branch = section_map.get(bc, [])
            section = sections_for_branch[min(section_index, len(sections_for_branch) - 1)]

            user = User(
                username=roll,
                password_hash=hash_password(sd['dob'].strftime("%d%m%Y")),
                role_id=role_student.id, must_change_password=True
            )
            db.add(user)
            db.flush()

            s = Student(
                user_id=user.id, roll_number=roll, enrollment_date=date(2024, 9, 9),
                section_id=section.id,
                **sd
            )
            db.add(s)
            db.flush()
            students.append(s)

        # ── Courses (2nd Year, 3rd Sem CSE subjects) ──
        courses_data = [
            {"code": "DS", "name": "Data Structures", "credits": 4, "department": "Computer Science"},
            {"code": "OOPJ", "name": "Object Oriented Programming in Java", "credits": 3, "department": "Computer Science"},
            {"code": "CA", "name": "Computer Architecture", "credits": 3, "department": "Computer Science"},
            {"code": "TTPS", "name": "Theory of Computation & PS", "credits": 4, "department": "Computer Science"},
            {"code": "CT", "name": "Communication Theory", "credits": 1, "department": "Computer Science"},
        ]
        courses = []
        for cd in courses_data:
            c = Course(**cd)
            db.add(c)
            db.flush()
            courses.append(c)

        # ── Assign Teachers to Courses ──
        # Rajesh → DS, OOPJ | Priya → CA | Amit → TTPS | Sunita → CT
        assignments = [(0, 0), (0, 1), (1, 2), (2, 3), (3, 4)]
        for ti, ci in assignments:
            db.add(TeacherCourse(teacher_id=teachers[ti].id, course_id=courses[ci].id))

        # ── Enroll Students ──
        enrollments = []
        for s in students:
            for c in courses:
                e = Enrollment(student_id=s.id, course_id=c.id, enrolled_date=date(2024, 9, 9))
                db.add(e)
                db.flush()
                enrollments.append(e)

        # ── Per-Period Attendance (6 periods/day, ~20 days) ──
        random.seed(42)
        base_date = date(2026, 1, 19)  # Class start date
        school_days = []
        current = base_date
        while len(school_days) < 20:
            if current.weekday() < 6:  # Mon-Sat
                school_days.append(current)
            current += timedelta(days=1)

        for e in enrollments:
            for day in school_days:
                # Each course gets 1 period per day (random period 1-6)
                period = random.randint(1, 6)
                # ~80% attendance, some consistent absences
                is_present = random.random() > 0.2
                status = AttendanceStatus.PRESENT if is_present else AttendanceStatus.ABSENT
                db.add(Attendance(
                    enrollment_id=e.id, date=day,
                    period=period, status=status
                ))

        # ── Standardized Assessments (matching VCE structure) ──
        # Per course: 2 Internals (max 30), 3 Quizzes (max 5), 3 Assignments (max 5)
        for c in courses:
            # Internals
            for i in range(1, 3):
                a = Assessment(course_id=c.id, name=f"Int{i}", type=AssessmentType.INTERNAL,
                               max_marks=30, date=date(2026, 2 + i, 15))
                db.add(a)
                db.flush()
                for s in students:
                    marks = round(random.uniform(14, 30), 0)
                    db.add(Mark(assessment_id=a.id, student_id=s.id, marks_obtained=marks))

            # Assignments
            for i in range(1, 4):
                a = Assessment(course_id=c.id, name=f"Asst{i}", type=AssessmentType.ASSIGNMENT,
                               max_marks=5, date=date(2026, 2, i * 5))
                db.add(a)
                db.flush()
                for s in students:
                    marks = round(random.uniform(3, 5), 0)
                    db.add(Mark(assessment_id=a.id, student_id=s.id, marks_obtained=marks))

            # Quizzes
            for i in range(1, 4):
                a = Assessment(course_id=c.id, name=f"Quiz{i}", type=AssessmentType.QUIZ,
                               max_marks=5, date=date(2026, 3, i * 5))
                db.add(a)
                db.flush()
                for s in students:
                    marks = round(random.uniform(3, 5), 0)
                    db.add(Mark(assessment_id=a.id, student_id=s.id, marks_obtained=marks))

        db.commit()
        print("✅ Seed data created successfully!")
        print()
        print("=" * 60)
        print("LOGIN CREDENTIALS")
        print("=" * 60)
        print()
        print("  Admin:    admin / admin123")
        print()
        print("  Teachers:")
        print("    rajesh.kumar   / 15031985  (DOB: 15-Mar-1985)")
        print("    priya.sharma   / 22071988  (DOB: 22-Jul-1988)")
        print("    amit.patel     / 08111982  (DOB: 08-Nov-1982)")
        print("    sunita.rao     / 10041986  (DOB: 10-Apr-1986)")
        print()
        print("  Students:")
        print("    1602-24-733-001 / 16032007  (Karthik Reddy, CSE-A)")
        print("    1602-24-733-002 / 20052006  (Diya Gupta, CSE-A)")
        print("    1602-24-733-003 / 10012006  (Aarav Singh, CSE-A)")
        print("    1602-24-733-004 / 25122006  (Ananya Sharma, CSE-A)")
        print("    1602-24-734-001 / 05092006  (Rohan Mehta, ECE-A)")
        print("    1602-24-734-002 / 14062006  (Vikram Joshi, ECE-A)")
        print()
        print("  Sections: CSE-A, CSE-B, ECE-A")
        print("  Courses:  DS, OOPJ, CA, TTPS, CT")
        print("  Assessments per course: 2 Internals, 3 Quizzes, 3 Assignments")
        print("=" * 60)

    except Exception as e:
        db.rollback()
        print(f"❌ Seed failed: {e}", file=sys.stderr)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
