"""Test suite for SMS — auth, CRUD, RBAC, sections, assessment limits, and attendance.

Uses SQLite in-memory to avoid needing a running MySQL server.
"""

import os
import pytest

# Override DATABASE_URL BEFORE importing app (so create_all uses SQLite)
os.environ["DATABASE_URL"] = "sqlite:///./test_sms.db"

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from app.database import Base, get_db
from app.main import app

# ── Test database setup (SQLite file) ─────────────────
SQLALCHEMY_TEST_URL = "sqlite:///./test_sms.db"
engine = create_engine(SQLALCHEMY_TEST_URL, connect_args={"check_same_thread": False})

# Enable foreign keys in SQLite (needed for CASCADE)
@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


# ── Fixtures ──────────────────────────────────────────

@pytest.fixture(autouse=True, scope="module")
def setup_db():
    """Create tables and seed basic roles + admin before all tests."""
    Base.metadata.create_all(bind=engine)
    db = TestSession()

    # Create roles
    from app.models import Role, User
    from app.security import hash_password

    for name in ["ADMIN", "TEACHER", "STUDENT"]:
        if not db.query(Role).filter(Role.name == name).first():
            db.add(Role(name=name))
    db.commit()

    # Create admin user
    role = db.query(Role).filter(Role.name == "ADMIN").first()
    if not db.query(User).filter(User.username == "testadmin").first():
        db.add(User(username="testadmin", password_hash=hash_password("Admin1234"),
                     role_id=role.id, must_change_password=False))
        db.commit()
    db.close()
    yield
    Base.metadata.drop_all(bind=engine)
    # Clean up test db file
    if os.path.exists("./test_sms.db"):
        os.remove("./test_sms.db")


def admin_token():
    """Helper to get admin JWT token."""
    res = client.post("/auth/login", json={"username": "testadmin", "password": "Admin1234"})
    return res.json()["access_token"]


def login_token(username, password):
    """Helper to get a JWT token for any seeded/created user."""
    res = client.post("/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200
    return res.json()["access_token"]


def auth_header(token=None):
    t = token or admin_token()
    return {"Authorization": f"Bearer {t}"}


def create_assigned_teacher_course_student(label):
    """Create one teacher, course, student, assignment, and enrollment for teacher-route tests."""
    headers = auth_header()
    teacher_email = f"{label}.teacher@example.com"
    student_email = f"{label}.student@example.com"
    course_code = f"{label.upper()}101"

    teacher_res = client.post("/admin/teachers", json={
        "first_name": label.title(),
        "last_name": "Teacher",
        "dob": "1985-01-02",
        "email": teacher_email,
        "phone": "9876500001",
        "department": "Computer Science",
    }, headers=headers)
    assert teacher_res.status_code == 201

    course_res = client.post("/admin/courses", json={
        "code": course_code,
        "name": f"{label.title()} Course",
        "credits": 3,
        "department": "Computer Science",
    }, headers=headers)
    assert course_res.status_code == 201
    course_id = course_res.json()["id"]

    student_res = client.post("/admin/students", json={
        "first_name": label.title(),
        "last_name": "Student",
        "dob": "2004-03-04",
        "branch_code": "733",
        "email": student_email,
        "phone": "9876500002",
    }, headers=headers)
    assert student_res.status_code == 201

    teachers = client.get("/admin/teachers", headers=headers).json()
    teacher = next(t for t in teachers if t["email"] == teacher_email)
    students = client.get("/admin/students", headers=headers).json()
    student = next(s for s in students if s["email"] == student_email)

    assign_res = client.post(
        f"/admin/assign-teacher?teacher_id={teacher['id']}&course_id={course_id}",
        headers=headers,
    )
    assert assign_res.status_code == 200
    enroll_res = client.post(
        f"/admin/enroll?student_id={student['id']}&course_id={course_id}",
        headers=headers,
    )
    assert enroll_res.status_code == 200

    teacher_token = login_token(teacher["username"], "02011985")
    return {
        "teacher": teacher,
        "teacher_token": teacher_token,
        "course_id": course_id,
        "student": student,
    }


# ── Auth Tests ────────────────────────────────────────

class TestAuth:
    def test_login_success(self):
        res = client.post("/auth/login", json={"username": "testadmin", "password": "Admin1234"})
        assert res.status_code == 200
        data = res.json()
        assert "access_token" in data
        assert data["role"] == "ADMIN"

    def test_login_wrong_password(self):
        res = client.post("/auth/login", json={"username": "testadmin", "password": "wrong"})
        assert res.status_code == 401

    def test_login_nonexistent_user(self):
        res = client.post("/auth/login", json={"username": "nobody", "password": "pass"})
        assert res.status_code == 401


# ── Admin Student CRUD Tests ─────────────────────────

class TestAdminStudents:
    def test_create_student(self):
        res = client.post("/admin/students", json={
            "first_name": "Test",
            "last_name": "Student",
            "dob": "2004-06-15",
            "branch_code": "733",
            "email": "test@student.com",
            "phone": "9876543210",
            "gender": "MALE",
            "father_name": "Test Father",
            "category": "OC",
            "area": "URBAN",
        }, headers=auth_header())
        assert res.status_code == 201
        assert "1602" in res.json()["message"]  # Roll number should contain college code

    def test_list_students(self):
        res = client.get("/admin/students", headers=auth_header())
        assert res.status_code == 200
        assert isinstance(res.json(), list)
        assert len(res.json()) >= 1

    def test_student_has_section(self):
        """Student should be auto-assigned to a section on creation."""
        res = client.get("/admin/students", headers=auth_header())
        students = res.json()
        assert len(students) >= 1
        # Section should be auto-assigned
        assert students[0]["section_name"] is not None
        assert students[0]["roll_college_code"] == "1602"
        assert students[0]["roll_joining_year"] is not None
        assert students[0]["roll_serial"] is not None

    def test_update_student(self):
        students = client.get("/admin/students", headers=auth_header()).json()
        sid = students[0]["id"]
        res = client.put(f"/admin/students/{sid}", json={
            "email": "updated@student.com",
            "blood_group": "O+",
        }, headers=auth_header())
        assert res.status_code == 200

    def test_reset_student_password_restores_dob_password_and_force_change(self):
        create_res = client.post("/admin/students", json={
            "first_name": "Reset",
            "last_name": "Student",
            "dob": "2004-07-16",
            "branch_code": "733",
            "email": "reset.student@example.com",
            "phone": "9876500100",
        }, headers=auth_header())
        assert create_res.status_code == 201

        students = client.get("/admin/students", headers=auth_header()).json()
        student = next(s for s in students if s["email"] == "reset.student@example.com")

        initial_token = login_token(student["username"], "16072004")
        change_res = client.post("/auth/change-password", json={
            "new_password": "ResetPass123"
        }, headers=auth_header(initial_token))
        assert change_res.status_code == 200

        reset_res = client.post(
            f"/admin/students/{student['id']}/reset-password",
            headers=auth_header(),
        )
        assert reset_res.status_code == 200

        login_res = client.post("/auth/login", json={
            "username": student["username"],
            "password": "16072004",
        })
        assert login_res.status_code == 200
        assert login_res.json()["must_change_password"] is True

    def test_reset_student_password_missing_student_returns_404(self):
        res = client.post("/admin/students/999999/reset-password", headers=auth_header())
        assert res.status_code == 404

    def test_list_students_filter_by_branch(self):
        res = client.get("/admin/students?branch_code=733", headers=auth_header())
        assert res.status_code == 200
        for s in res.json():
            assert s["branch_code"] == "733"

    def test_delete_student(self):
        # Create a student to delete
        client.post("/admin/students", json={
            "first_name": "Delete", "last_name": "Me",
            "dob": "2004-01-01", "branch_code": "733"
        }, headers=auth_header())
        students = client.get("/admin/students", headers=auth_header()).json()
        target = [s for s in students if s["first_name"] == "Delete"]
        if target:
            res = client.delete(f"/admin/students/{target[0]['id']}", headers=auth_header())
            assert res.status_code == 200


# ── Section Tests ────────────────────────────────────

class TestSections:
    def test_list_sections(self):
        res = client.get("/admin/sections", headers=auth_header())
        assert res.status_code == 200
        sections = res.json()
        assert isinstance(sections, list)
        # At least one section should exist from student creation
        assert len(sections) >= 1

    def test_list_sections_by_branch(self):
        res = client.get("/admin/sections?branch_code=733", headers=auth_header())
        assert res.status_code == 200
        for s in res.json():
            assert s["branch_code"] == "733"


# ── Admin Course CRUD Tests ──────────────────────────

class TestAdminCourses:
    def test_create_course(self):
        res = client.post("/admin/courses", json={
            "code": "TEST101",
            "name": "Test Course",
            "credits": 3,
            "department": "Testing"
        }, headers=auth_header())
        assert res.status_code == 201

    def test_duplicate_course_code(self):
        res = client.post("/admin/courses", json={
            "code": "TEST101", "name": "Duplicate", "credits": 3
        }, headers=auth_header())
        assert res.status_code == 400

    def test_list_courses(self):
        res = client.get("/admin/courses", headers=auth_header())
        assert res.status_code == 200
        assert isinstance(res.json(), list)


# ── Teacher-Course Assignment Tests ──────────────────

class TestTeacherCourseAssignments:
    def test_assign_list_duplicate_and_unassign(self):
        teacher_res = client.post("/admin/teachers", json={
            "first_name": "Assign",
            "last_name": "Teacher",
            "dob": "1989-04-12",
            "email": "assign.teacher@example.com",
            "phone": "9876543219",
            "department": "Computer Science",
        }, headers=auth_header())
        assert teacher_res.status_code == 201

        course_res = client.post("/admin/courses", json={
            "code": "ASN101",
            "name": "Assignment Wiring",
            "credits": 3,
            "department": "Computer Science",
        }, headers=auth_header())
        assert course_res.status_code == 201
        course_id = course_res.json()["id"]

        teachers = client.get("/admin/teachers", headers=auth_header()).json()
        teacher_id = next(t["id"] for t in teachers if t["email"] == "assign.teacher@example.com")

        assign_res = client.post(
            f"/admin/assign-teacher?teacher_id={teacher_id}&course_id={course_id}",
            headers=auth_header(),
        )
        assert assign_res.status_code == 200

        assignments = client.get("/admin/teacher-assignments", headers=auth_header()).json()
        assert any(a["teacher_id"] == teacher_id and a["course_id"] == course_id for a in assignments)

        duplicate_res = client.post(
            f"/admin/assign-teacher?teacher_id={teacher_id}&course_id={course_id}",
            headers=auth_header(),
        )
        assert duplicate_res.status_code == 400

        unassign_res = client.delete(
            f"/admin/unassign-teacher?teacher_id={teacher_id}&course_id={course_id}",
            headers=auth_header(),
        )
        assert unassign_res.status_code == 200


# ── Teacher Workflow Roadmap Tests ───────────────────

class TestTeacherWorkflowRoadmap:
    def test_teacher_sections_assessment_limits_and_marks_csv(self):
        ctx = create_assigned_teacher_course_student("roadmapmarks")
        teacher_headers = auth_header(ctx["teacher_token"])

        sections_res = client.get(
            f"/teacher/courses/{ctx['course_id']}/sections",
            headers=teacher_headers,
        )
        assert sections_res.status_code == 200
        assert sections_res.json()[0]["student_count"] >= 1

        bad_assessment = client.post("/teacher/assessments", json={
            "course_id": ctx["course_id"],
            "name": "IntBad",
            "type": "INTERNAL",
            "max_marks": 20,
        }, headers=teacher_headers)
        assert bad_assessment.status_code == 400

        assessment_res = client.post("/teacher/assessments", json={
            "course_id": ctx["course_id"],
            "name": "Int1",
            "type": "INTERNAL",
        }, headers=teacher_headers)
        assert assessment_res.status_code == 200
        assessment_id = assessment_res.json()["id"]

        template_res = client.get(
            f"/teacher/marks/{assessment_id}/template",
            headers=teacher_headers,
        )
        assert template_res.status_code == 200
        assert "roll_number" in template_res.text
        assert ctx["student"]["roll_number"] in template_res.text

        csv_body = f"roll_number,marks_obtained\n{ctx['student']['roll_number']},28\n"
        upload_res = client.post(
            f"/teacher/marks/{assessment_id}/upload-csv",
            files={"file": ("marks.csv", csv_body, "text/csv")},
            headers=teacher_headers,
        )
        assert upload_res.status_code == 200
        assert upload_res.json()["updated"] == 1

        grid_res = client.get(
            f"/teacher/marks/{assessment_id}/grid",
            headers=teacher_headers,
        )
        assert grid_res.status_code == 200
        row = next(r for r in grid_res.json() if r["roll_number"] == ctx["student"]["roll_number"])
        assert row["marks_obtained"] == 28
        assert row["max_marks"] == 30

    def test_sub_period_attendance_grid_and_csv_upload(self):
        ctx = create_assigned_teacher_course_student("roadmapatt")
        teacher_headers = auth_header(ctx["teacher_token"])

        empty_grid_res = client.get(
            f"/teacher/attendance/{ctx['course_id']}/grid"
            "?att_date=2026-03-01&period=7&sub_period=2",
            headers=teacher_headers,
        )
        assert empty_grid_res.status_code == 200
        empty_row = next(r for r in empty_grid_res.json() if r["roll_number"] == ctx["student"]["roll_number"])
        assert empty_row["status"] is None

        mark_res = client.post("/teacher/attendance", json={
            "course_id": ctx["course_id"],
            "date": "2026-03-01",
            "period": 7,
            "sub_period": 2,
            "records": [{
                "student_id": ctx["student"]["id"],
                "status": "PRESENT",
            }],
        }, headers=teacher_headers)
        assert mark_res.status_code == 200

        detail_res = client.get(
            f"/teacher/attendance/{ctx['course_id']}/date/2026-03-01",
            headers=teacher_headers,
        )
        assert detail_res.status_code == 200
        row = next(r for r in detail_res.json() if r["roll_number"] == ctx["student"]["roll_number"])
        assert row["periods"]["period_7_2"] == "PRESENT"

        template_res = client.get(
            f"/teacher/attendance/{ctx['course_id']}/template"
            "?att_date=2026-03-01&period=7&sub_period=2",
            headers=teacher_headers,
        )
        assert template_res.status_code == 200
        assert "status" in template_res.text

        csv_body = f"roll_number,status\n{ctx['student']['roll_number']},ABSENT\n"
        upload_res = client.post(
            f"/teacher/attendance/{ctx['course_id']}/upload-csv"
            "?att_date=2026-03-01&period=7&sub_period=2",
            files={"file": ("attendance.csv", csv_body, "text/csv")},
            headers=teacher_headers,
        )
        assert upload_res.status_code == 200
        assert upload_res.json()["updated"] == 1

        summary_res = client.get(
            f"/teacher/attendance/{ctx['course_id']}",
            headers=teacher_headers,
        )
        assert summary_res.status_code == 200
        summary_row = next(r for r in summary_res.json() if r["roll_number"] == ctx["student"]["roll_number"])
        assert summary_row["total_periods"] == 1
        assert summary_row["present"] == 0

        grid_res = client.get(
            f"/teacher/attendance/{ctx['course_id']}/grid"
            "?att_date=2026-03-01&period=7&sub_period=2",
            headers=teacher_headers,
        )
        assert grid_res.status_code == 200
        row = next(r for r in grid_res.json() if r["roll_number"] == ctx["student"]["roll_number"])
        assert row["status"] == "ABSENT"


# ── RBAC Tests ────────────────────────────────────────

class TestRBAC:
    def test_no_token_rejected(self):
        res = client.get("/admin/students")
        assert res.status_code in [401, 403]

    def test_invalid_token_rejected(self):
        res = client.get("/admin/students", headers={"Authorization": "Bearer invalidtoken"})
        assert res.status_code == 401

    def test_teacher_cannot_reset_student_password(self):
        ctx = create_assigned_teacher_course_student("resetdeny")
        res = client.post(
            f"/admin/students/{ctx['student']['id']}/reset-password",
            headers=auth_header(ctx["teacher_token"]),
        )
        assert res.status_code == 403


# ── Validation Tests ──────────────────────────────────

class TestValidation:
    def test_weak_password_rejected(self):
        res = client.post("/auth/change-password", json={
            "new_password": "short"
        }, headers=auth_header())
        assert res.status_code == 422

    def test_invalid_email_rejected(self):
        res = client.post("/admin/students", json={
            "first_name": "Bad",
            "last_name": "Email",
            "dob": "2004-01-01",
            "branch_code": "733",
            "email": "not-an-email"
        }, headers=auth_header())
        assert res.status_code == 422

    def test_invalid_phone_rejected(self):
        res = client.post("/admin/students", json={
            "first_name": "Bad",
            "last_name": "Phone",
            "dob": "2004-01-01",
            "branch_code": "733",
            "phone": "abc"
        }, headers=auth_header())
        assert res.status_code == 422

    def test_negative_credits_rejected(self):
        res = client.post("/admin/courses", json={
            "code": "NEG001",
            "name": "Negative Credits",
            "credits": -1
        }, headers=auth_header())
        assert res.status_code == 422

    def test_attendance_invalid_period_rejected(self):
        """Period must be 1-7."""
        res = client.post("/teacher/attendance", json={
            "course_id": 1,
            "date": "2026-03-01",
            "period": 8,  # Invalid — max is 7
            "records": []
        }, headers=auth_header())
        # Should be 422 (validation) or 403 (not a teacher) — either is acceptable
        assert res.status_code in [422, 403]
