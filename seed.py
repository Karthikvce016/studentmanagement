"""Seed script — creates sample data for testing.

Run:  python seed.py
Note: This DROPS all existing data before re-seeding (#18 — improved robustness).
"""

import sys
from datetime import date, timedelta
import random
from sqlalchemy import text
from app.database import SessionLocal, engine, Base
from app.models import (
    Role, User, Student, Teacher, Course, TeacherCourse,
    Enrollment, Assessment, AssessmentType, Attendance, AttendanceStatus, Mark
)
from app.security import hash_password

# Create all tables
Base.metadata.create_all(bind=engine)


def seed():
    db = SessionLocal()

    try:
        # Clear existing data in reverse dependency order (#18)
        for model in [Mark, Attendance, Assessment, Enrollment, TeacherCourse,
                      Course, Student, Teacher, User, Role]:
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

        # ── Teachers ──
        teachers_data = [
            {"first_name": "Rajesh", "last_name": "Kumar", "dob": date(1985, 3, 15),
             "email": "rajesh@school.com", "department": "Computer Science"},
            {"first_name": "Priya", "last_name": "Sharma", "dob": date(1988, 7, 22),
             "email": "priya@school.com", "department": "Mathematics"},
            {"first_name": "Amit", "last_name": "Patel", "dob": date(1982, 11, 8),
             "email": "amit@school.com", "department": "Physics"},
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

        # ── Students ──
        COLLEGE_CODE = "1602"
        joining_year = "24"  # 2024

        students_data = [
            {"first_name": "Aarav", "last_name": "Singh", "dob": date(2004, 1, 10),
             "email": "aarav@student.com", "phone": "9876543210", "address": "123 Main St",
             "branch_code": "733"},
            {"first_name": "Diya", "last_name": "Gupta", "dob": date(2004, 5, 20),
             "email": "diya@student.com", "phone": "9876543211", "address": "456 Oak Ave",
             "branch_code": "733"},
            {"first_name": "Rohan", "last_name": "Mehta", "dob": date(2003, 9, 5),
             "email": "rohan@student.com", "phone": "9876543212", "address": "789 Pine Rd",
             "branch_code": "734"},
            {"first_name": "Ananya", "last_name": "Reddy", "dob": date(2004, 12, 25),
             "email": "ananya@student.com", "phone": "9876543213", "address": "321 Elm St",
             "branch_code": "733"},
            {"first_name": "Vikram", "last_name": "Joshi", "dob": date(2003, 6, 14),
             "email": "vikram@student.com", "phone": "9876543214", "address": "654 Maple Dr",
             "branch_code": "734"},
        ]
        students = []
        # Track serial numbers per branch
        branch_serials = {}
        for sd in students_data:
            bc = sd["branch_code"]
            branch_serials[bc] = branch_serials.get(bc, 0) + 1
            roll = f"{COLLEGE_CODE}-{joining_year}-{bc}-{str(branch_serials[bc]).zfill(3)}"
            user = User(
                username=roll,
                password_hash=hash_password(sd['dob'].strftime("%d%m%Y")),
                role_id=role_student.id, must_change_password=True
            )
            db.add(user)
            db.flush()
            s = Student(user_id=user.id, roll_number=roll, enrollment_date=date.today(), **sd)
            db.add(s)
            db.flush()
            students.append(s)

        # ── Courses ──
        courses_data = [
            {"code": "CS101", "name": "Introduction to Programming", "credits": 4, "department": "Computer Science"},
            {"code": "MA201", "name": "Linear Algebra", "credits": 3, "department": "Mathematics"},
            {"code": "PH101", "name": "Physics I", "credits": 4, "department": "Physics"},
            {"code": "CS202", "name": "Data Structures", "credits": 4, "department": "Computer Science"},
        ]
        courses = []
        for cd in courses_data:
            c = Course(**cd)
            db.add(c)
            db.flush()
            courses.append(c)

        # ── Assign Teachers to Courses ──
        assignments = [(0, 0), (0, 3), (1, 1), (2, 2)]  # (teacher_idx, course_idx)
        for ti, ci in assignments:
            db.add(TeacherCourse(teacher_id=teachers[ti].id, course_id=courses[ci].id))

        # ── Enroll Students ──
        enrollments = []
        for s in students:
            for c in courses[:3]:  # Enroll all students in first 3 courses
                e = Enrollment(student_id=s.id, course_id=c.id, enrolled_date=date.today())
                db.add(e)
                db.flush()
                enrollments.append(e)

        # ── Sample Attendance ──
        base_date = date(2026, 3, 1)
        for e in enrollments:
            for day_offset in range(10):
                d = base_date + timedelta(days=day_offset)
                status = AttendanceStatus.PRESENT if day_offset % 3 != 0 else AttendanceStatus.ABSENT
                db.add(Attendance(enrollment_id=e.id, date=d, status=status))

        # ── Sample Assessments & Marks ──
        assessments_data = [
            {"course_idx": 0, "name": "Quiz 1", "type": AssessmentType.QUIZ, "max_marks": 20},
            {"course_idx": 0, "name": "Midterm", "type": AssessmentType.MIDTERM, "max_marks": 50},
            {"course_idx": 1, "name": "Quiz 1", "type": AssessmentType.QUIZ, "max_marks": 25},
            {"course_idx": 2, "name": "Midterm", "type": AssessmentType.MIDTERM, "max_marks": 50},
        ]
        random.seed(42)
        for ad in assessments_data:
            assessment = Assessment(
                course_id=courses[ad["course_idx"]].id,
                name=ad["name"], type=ad["type"], max_marks=ad["max_marks"], date=date.today()
            )
            db.add(assessment)
            db.flush()
            for s in students:
                m = Mark(assessment_id=assessment.id, student_id=s.id,
                         marks_obtained=round(random.uniform(ad["max_marks"] * 0.4, ad["max_marks"]), 1))
                db.add(m)

        db.commit()
        print("✅ Seed data created successfully!")
        print()
        print("Login credentials:")
        print("  Admin:   admin / admin123")
        print("  Teacher: rajesh.kumar / 15031985  (DOB: 15-Mar-1985)")
        print("  Teacher: priya.sharma / 22071988  (DOB: 22-Jul-1988)")
        print("  Student: 1602-24-733-001 / 10012004  (Aarav Singh, CSE)")
        print("  Student: 1602-24-733-002 / 20052004  (Diya Gupta, CSE)")
        print("  Student: 1602-24-734-001 / 05092003  (Rohan Mehta, ECE)")

    except Exception as e:
        db.rollback()
        print(f"❌ Seed failed: {e}", file=sys.stderr)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
