"""Core SMS tests for auth, offering workflows, audits, reports, and RBAC."""

import os

import pytest

os.environ["DATABASE_URL"] = "sqlite:///./test_sms.db"

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models import AttendanceAudit, CourseOffering, MarkAudit, PasswordResetAudit, Role, Student, User
from app.security import hash_password


SQLALCHEMY_TEST_URL = "sqlite:///./test_sms.db"
engine = create_engine(SQLALCHEMY_TEST_URL, connect_args={"check_same_thread": False})


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


@pytest.fixture(autouse=True, scope="module")
def setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestSession()
    for name in ["ADMIN", "TEACHER", "STUDENT"]:
        db.add(Role(name=name))
    db.flush()

    admin_role = db.query(Role).filter(Role.name == "ADMIN").first()
    db.add(
        User(
            username="testadmin",
            password_hash=hash_password("Admin1234"),
            role_id=admin_role.id,
            must_change_password=False,
        )
    )
    db.commit()
    db.close()

    yield

    Base.metadata.drop_all(bind=engine)
    if os.path.exists("./test_sms.db"):
        os.remove("./test_sms.db")


def admin_token():
    res = client.post("/auth/login", json={"username": "testadmin", "password": "Admin1234"})
    assert res.status_code == 200
    return res.json()["access_token"]


def auth_header(token=None):
    return {"Authorization": f"Bearer {token or admin_token()}"}


def login_token(username, password):
    res = client.post("/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200
    return res.json()["access_token"]


def create_teacher(label):
    email = f"{label}.teacher@example.com"
    res = client.post(
        "/admin/teachers",
        json={
            "first_name": label.title(),
            "last_name": "Teacher",
            "dob": "1985-01-02",
            "email": email,
            "phone": "9876500001",
            "department": "Computer Science",
        },
        headers=auth_header(),
    )
    assert res.status_code == 201
    teachers = client.get("/admin/teachers", headers=auth_header()).json()
    return next(teacher for teacher in teachers if teacher["email"] == email)


def create_student(label):
    email = f"{label}.student@example.com"
    res = client.post(
        "/admin/students",
        json={
            "first_name": label.title(),
            "last_name": "Student",
            "dob": "2004-03-04",
            "branch_code": "733",
            "email": email,
            "phone": "9876500002",
        },
        headers=auth_header(),
    )
    assert res.status_code == 201
    students = client.get("/admin/students", headers=auth_header()).json()
    return next(student for student in students if student["email"] == email)


def create_course(label):
    code = f"{label[:6].upper()}1"
    res = client.post(
        "/admin/courses",
        json={
            "code": code,
            "name": f"{label.title()} Course",
            "credits": 3,
            "department": "Computer Science",
        },
        headers=auth_header(),
    )
    assert res.status_code == 201
    return {"id": res.json()["id"], "code": code}


def create_offering(course_id, section_id, academic_year=2026, semester=3):
    res = client.post(
        "/admin/course-offerings",
        json={
            "course_id": course_id,
            "academic_year": academic_year,
            "semester": semester,
            "section_id": section_id,
            "capacity": 65,
        },
        headers=auth_header(),
    )
    assert res.status_code == 201
    return res.json()["id"]


def build_assigned_context(label):
    teacher = create_teacher(label)
    student = create_student(label)
    course = create_course(label)

    db = TestSession()
    try:
        student_row = db.query(Student).filter(Student.id == student["id"]).first()
        section_id = student_row.section_id
    finally:
        db.close()

    offering_id = create_offering(course["id"], section_id)
    assign_res = client.post(
        f"/admin/assign-teacher?teacher_id={teacher['id']}&offering_id={offering_id}",
        headers=auth_header(),
    )
    assert assign_res.status_code == 200
    enroll_res = client.post(
        f"/admin/enroll?student_id={student['id']}&offering_id={offering_id}",
        headers=auth_header(),
    )
    assert enroll_res.status_code == 200

    teacher_token = login_token(teacher["username"], "02011985")
    student_token = login_token(student["username"], "04032004")
    return {
        "teacher": teacher,
        "teacher_token": teacher_token,
        "student": student,
        "student_token": student_token,
        "course": course,
        "offering_id": offering_id,
        "section_id": section_id,
    }


class TestAuth:
    def test_login_success(self):
        res = client.post("/auth/login", json={"username": "testadmin", "password": "Admin1234"})
        assert res.status_code == 200
        assert res.json()["role"] == "ADMIN"

    def test_login_wrong_password(self):
        res = client.post("/auth/login", json={"username": "testadmin", "password": "wrong"})
        assert res.status_code == 401

    def test_login_nonexistent_user(self):
        res = client.post("/auth/login", json={"username": "nobody", "password": "pass"})
        assert res.status_code == 401


class TestAdminStudents:
    def test_create_student(self):
        res = client.post(
            "/admin/students",
            json={
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
            },
            headers=auth_header(),
        )
        assert res.status_code == 201
        assert "DDMMYYYY" in res.json()["message"]

    def test_list_students(self):
        res = client.get("/admin/students", headers=auth_header())
        assert res.status_code == 200
        assert len(res.json()) >= 1

    def test_student_has_section_and_roll_metadata(self):
        students = client.get("/admin/students", headers=auth_header()).json()
        assert students[0]["section_name"] is not None
        assert students[0]["roll_college_code"] == "1602"
        assert students[0]["roll_joining_year"] is not None
        assert students[0]["roll_serial"] is not None

    def test_update_student(self):
        students = client.get("/admin/students", headers=auth_header()).json()
        student_id = students[0]["id"]
        res = client.put(
            f"/admin/students/{student_id}",
            json={"email": "updated@student.com", "blood_group": "O+"},
            headers=auth_header(),
        )
        assert res.status_code == 200

    def test_reset_student_password_and_audit(self):
        student = create_student("resetflow")
        initial_token = login_token(student["username"], "04032004")
        change_res = client.post(
            "/auth/change-password",
            json={"new_password": "ResetPass123"},
            headers=auth_header(initial_token),
        )
        assert change_res.status_code == 200

        reset_res = client.post(
            f"/admin/students/{student['id']}/reset-password",
            headers=auth_header(),
        )
        assert reset_res.status_code == 200

        login_res = client.post("/auth/login", json={"username": student["username"], "password": "04032004"})
        assert login_res.status_code == 200
        assert login_res.json()["must_change_password"] is True

        db = TestSession()
        try:
            audit = db.query(PasswordResetAudit).filter(PasswordResetAudit.student_id == student["id"]).all()
            assert len(audit) == 1
            assert audit[0].reset_value_rule == "DOB_DDMMYYYY"
        finally:
            db.close()

    def test_reset_student_password_missing_student_returns_404(self):
        res = client.post("/admin/students/999999/reset-password", headers=auth_header())
        assert res.status_code == 404


class TestSections:
    def test_list_sections(self):
        res = client.get("/admin/sections", headers=auth_header())
        assert res.status_code == 200
        assert len(res.json()) >= 1

    def test_list_sections_by_branch(self):
        res = client.get("/admin/sections?branch_code=733", headers=auth_header())
        assert res.status_code == 200
        assert all(section["branch_code"] == "733" for section in res.json())


class TestCoursesAndOfferings:
    def test_create_course_and_duplicate_code(self):
        res = client.post(
            "/admin/courses",
            json={"code": "TEST101", "name": "Test Course", "credits": 3, "department": "Testing"},
            headers=auth_header(),
        )
        assert res.status_code == 201

        duplicate_res = client.post(
            "/admin/courses",
            json={"code": "TEST101", "name": "Duplicate", "credits": 3},
            headers=auth_header(),
        )
        assert duplicate_res.status_code == 400

    def test_create_and_list_course_offering(self):
        student = create_student("offeringseed")
        course = create_course("offeringseed")

        db = TestSession()
        try:
            section_id = db.query(Student).filter(Student.id == student["id"]).first().section_id
        finally:
            db.close()

        offering_id = create_offering(course["id"], section_id, academic_year=2027, semester=4)
        res = client.get("/admin/course-offerings", headers=auth_header())
        assert res.status_code == 200
        assert any(offering["id"] == offering_id and offering["section_id"] == section_id for offering in res.json())

    def test_dashboard_stats_include_offerings(self):
        res = client.get("/admin/stats", headers=auth_header())
        assert res.status_code == 200
        assert "total_course_offerings" in res.json()


class TestAssignmentsAndEnrollments:
    def test_assign_list_duplicate_and_unassign(self):
        ctx = build_assigned_context("assignflow")

        assignments = client.get("/admin/teacher-assignments", headers=auth_header()).json()
        assert any(item["teacher_id"] == ctx["teacher"]["id"] and item["offering_id"] == ctx["offering_id"] for item in assignments)

        duplicate_res = client.post(
            f"/admin/assign-teacher?teacher_id={ctx['teacher']['id']}&offering_id={ctx['offering_id']}",
            headers=auth_header(),
        )
        assert duplicate_res.status_code == 400

        enrollments = client.get("/admin/enrollments", headers=auth_header()).json()
        assert any(item["student_id"] == ctx["student"]["id"] and item["offering_id"] == ctx["offering_id"] for item in enrollments)

        unassign_res = client.delete(
            f"/admin/unassign-teacher?teacher_id={ctx['teacher']['id']}&offering_id={ctx['offering_id']}",
            headers=auth_header(),
        )
        assert unassign_res.status_code == 200


class TestTeacherWorkflow:
    def test_teacher_sections_assessment_limits_marks_csv_and_mark_audit(self):
        ctx = build_assigned_context("teachmarks")
        teacher_headers = auth_header(ctx["teacher_token"])

        sections_res = client.get(f"/teacher/courses/{ctx['offering_id']}/sections", headers=teacher_headers)
        assert sections_res.status_code == 200
        assert sections_res.json()[0]["student_count"] >= 1

        students_res = client.get(
            f"/teacher/courses/{ctx['offering_id']}/students?section_id={ctx['section_id']}",
            headers=teacher_headers,
        )
        assert students_res.status_code == 200
        assert students_res.json()[0]["student_id"] == ctx["student"]["id"]

        bad_assessment = client.post(
            "/teacher/assessments",
            json={
                "offering_id": ctx["offering_id"],
                "name": "IntBad",
                "type": "INTERNAL",
                "max_marks": 20,
            },
            headers=teacher_headers,
        )
        assert bad_assessment.status_code == 400

        assessment_res = client.post(
            "/teacher/assessments",
            json={"offering_id": ctx["offering_id"], "name": "Int1", "type": "INTERNAL"},
            headers=teacher_headers,
        )
        assert assessment_res.status_code == 200
        assessment_id = assessment_res.json()["id"]

        template_res = client.get(f"/teacher/marks/{assessment_id}/template", headers=teacher_headers)
        assert template_res.status_code == 200
        assert "roll_number" in template_res.text

        csv_body = f"roll_number,marks_obtained\n{ctx['student']['roll_number']},28\n"
        upload_res = client.post(
            f"/teacher/marks/{assessment_id}/upload-csv",
            files={"file": ("marks.csv", csv_body, "text/csv")},
            headers=teacher_headers,
        )
        assert upload_res.status_code == 200
        assert upload_res.json()["updated"] == 1

        grid_res = client.get(f"/teacher/marks/{assessment_id}/grid?section_id={ctx['section_id']}", headers=teacher_headers)
        assert grid_res.status_code == 200
        row = next(item for item in grid_res.json() if item["student_id"] == ctx["student"]["id"])
        assert row["marks_obtained"] == 28
        assert row["max_marks"] == 30

        db = TestSession()
        try:
            audits = db.query(MarkAudit).filter(MarkAudit.assessment_id == assessment_id).all()
            assert len(audits) == 1
            assert audits[0].new_marks == 28
        finally:
            db.close()

    def test_sub_period_attendance_grid_csv_and_audit(self):
        ctx = build_assigned_context("teachatt")
        teacher_headers = auth_header(ctx["teacher_token"])

        empty_grid = client.get(
            f"/teacher/attendance/{ctx['offering_id']}/grid?att_date=2026-03-01&period=7&sub_period=2&section_id={ctx['section_id']}",
            headers=teacher_headers,
        )
        assert empty_grid.status_code == 200
        row = next(item for item in empty_grid.json() if item["student_id"] == ctx["student"]["id"])
        assert row["status"] is None

        mark_res = client.post(
            "/teacher/attendance",
            json={
                "offering_id": ctx["offering_id"],
                "date": "2026-03-01",
                "period": 7,
                "sub_period": 2,
                "records": [{"student_id": ctx["student"]["id"], "status": "PRESENT"}],
            },
            headers=teacher_headers,
        )
        assert mark_res.status_code == 200

        detail_res = client.get(
            f"/teacher/attendance/{ctx['offering_id']}/date/2026-03-01?section_id={ctx['section_id']}",
            headers=teacher_headers,
        )
        assert detail_res.status_code == 200
        row = next(item for item in detail_res.json() if item["student_id"] == ctx["student"]["id"])
        assert row["periods"]["period_7_2"] == "PRESENT"

        csv_body = f"roll_number,status\n{ctx['student']['roll_number']},ABSENT\n"
        upload_res = client.post(
            f"/teacher/attendance/{ctx['offering_id']}/upload-csv?att_date=2026-03-01&period=7&sub_period=2&section_id={ctx['section_id']}",
            files={"file": ("attendance.csv", csv_body, "text/csv")},
            headers=teacher_headers,
        )
        assert upload_res.status_code == 200
        assert upload_res.json()["updated"] == 1

        summary_res = client.get(
            f"/teacher/attendance/{ctx['offering_id']}?section_id={ctx['section_id']}",
            headers=teacher_headers,
        )
        assert summary_res.status_code == 200
        row = next(item for item in summary_res.json() if item["student_id"] == ctx["student"]["id"])
        assert row["total_periods"] == 1
        assert row["present"] == 0

        db = TestSession()
        try:
            enrollment_id = (
                db.query(Student)
                .filter(Student.id == ctx["student"]["id"])
                .first()
                .enrollments[0]
                .id
            )
            audits = db.query(AttendanceAudit).filter(AttendanceAudit.enrollment_id == enrollment_id).all()
            assert len(audits) >= 2
        finally:
            db.close()


class TestStudentViews:
    def test_student_attendance_and_marks_use_offerings(self):
        ctx = build_assigned_context("studentview")
        teacher_headers = auth_header(ctx["teacher_token"])

        assessment_res = client.post(
            "/teacher/assessments",
            json={"offering_id": ctx["offering_id"], "name": "Quiz1", "type": "QUIZ"},
            headers=teacher_headers,
        )
        assert assessment_res.status_code == 200
        assessment_id = assessment_res.json()["id"]

        marks_res = client.post(
            "/teacher/marks",
            json={"assessment_id": assessment_id, "marks": [{"student_id": ctx["student"]["id"], "marks_obtained": 5}]},
            headers=teacher_headers,
        )
        assert marks_res.status_code == 200

        attendance_res = client.post(
            "/teacher/attendance",
            json={
                "offering_id": ctx["offering_id"],
                "date": "2026-03-02",
                "period": 2,
                "sub_period": 1,
                "records": [{"student_id": ctx["student"]["id"], "status": "PRESENT"}],
            },
            headers=teacher_headers,
        )
        assert attendance_res.status_code == 200

        student_headers = auth_header(ctx["student_token"])
        attendance_summary = client.get("/student/attendance", headers=student_headers)
        assert attendance_summary.status_code == 200
        assert any(item["offering_id"] == ctx["offering_id"] for item in attendance_summary.json())

        detail = client.get(f"/student/attendance/{ctx['offering_id']}", headers=student_headers)
        assert detail.status_code == 200
        assert detail.json()["course_code"] == ctx["course"]["code"]

        marks_report = client.get("/student/marks", headers=student_headers)
        assert marks_report.status_code == 200
        assert any(subject["offering_label"] for subject in marks_report.json()["subjects"])


class TestReports:
    def test_admin_reports_return_rows(self):
        ctx = build_assigned_context("reportflow")
        teacher_headers = auth_header(ctx["teacher_token"])

        client.post(
            "/teacher/attendance",
            json={
                "offering_id": ctx["offering_id"],
                "date": "2026-04-01",
                "period": 1,
                "sub_period": 1,
                "records": [{"student_id": ctx["student"]["id"], "status": "ABSENT"}],
            },
            headers=teacher_headers,
        )
        assessment_res = client.post(
            "/teacher/assessments",
            json={"offering_id": ctx["offering_id"], "name": "Asst1", "type": "ASSIGNMENT"},
            headers=teacher_headers,
        )
        assessment_id = assessment_res.json()["id"]
        client.post(
            "/teacher/marks",
            json={"assessment_id": assessment_id, "marks": [{"student_id": ctx["student"]["id"], "marks_obtained": 4}]},
            headers=teacher_headers,
        )

        for endpoint in [
            "/admin/reports/attendance-risk",
            "/admin/reports/course-toppers",
            "/admin/reports/section-performance",
            "/admin/reports/pass-fail-summary",
            "/admin/reports/attendance-trend",
        ]:
            res = client.get(endpoint, headers=auth_header())
            assert res.status_code == 200
            assert isinstance(res.json(), list)


class TestRBAC:
    def test_no_token_rejected(self):
        res = client.get("/admin/students")
        assert res.status_code in [401, 403]

    def test_invalid_token_rejected(self):
        res = client.get("/admin/students", headers={"Authorization": "Bearer invalidtoken"})
        assert res.status_code == 401

    def test_teacher_cannot_reset_student_password(self):
        ctx = build_assigned_context("rbacreset")
        res = client.post(
            f"/admin/students/{ctx['student']['id']}/reset-password",
            headers=auth_header(ctx["teacher_token"]),
        )
        assert res.status_code == 403


class TestValidation:
    def test_weak_password_rejected(self):
        res = client.post("/auth/change-password", json={"new_password": "short"}, headers=auth_header())
        assert res.status_code == 422

    def test_invalid_email_rejected(self):
        res = client.post(
            "/admin/students",
            json={"first_name": "Bad", "last_name": "Email", "dob": "2004-01-01", "branch_code": "733", "email": "not-an-email"},
            headers=auth_header(),
        )
        assert res.status_code == 422

    def test_invalid_phone_rejected(self):
        res = client.post(
            "/admin/students",
            json={"first_name": "Bad", "last_name": "Phone", "dob": "2004-01-01", "branch_code": "733", "phone": "abc"},
            headers=auth_header(),
        )
        assert res.status_code == 422

    def test_negative_credits_rejected(self):
        res = client.post(
            "/admin/courses",
            json={"code": "NEG001", "name": "Negative Credits", "credits": -1},
            headers=auth_header(),
        )
        assert res.status_code == 422

    def test_attendance_invalid_period_rejected(self):
        res = client.post(
            "/teacher/attendance",
            json={"offering_id": 1, "date": "2026-03-01", "period": 8, "records": []},
            headers=auth_header(),
        )
        assert res.status_code in [422, 403]
