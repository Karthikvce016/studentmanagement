"""Basic test suite for SMS — auth, CRUD, and RBAC validation (#19).

Uses SQLite in-memory to avoid needing a running MySQL server.
"""

import os
import pytest

# Override DATABASE_URL BEFORE importing app (so create_all uses SQLite)
os.environ["DATABASE_URL"] = "sqlite:///./test_sms.db"

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base, get_db
from app.main import app

# ── Test database setup (SQLite file) ─────────────────
SQLALCHEMY_TEST_URL = "sqlite:///./test_sms.db"
engine = create_engine(SQLALCHEMY_TEST_URL, connect_args={"check_same_thread": False})

# Enable foreign keys in SQLite (needed for CASCADE)
from sqlalchemy import event
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


def auth_header(token=None):
    t = token or admin_token()
    return {"Authorization": f"Bearer {t}"}


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


# ── Admin CRUD Tests ──────────────────────────────────

class TestAdminStudents:
    def test_create_student(self):
        res = client.post("/admin/students", json={
            "first_name": "Test",
            "last_name": "Student",
            "dob": "2004-06-15",
            "email": "test@student.com",
            "phone": "9876543210"
        }, headers=auth_header())
        assert res.status_code == 201
        assert "test.student" in res.json()["message"]

    def test_list_students(self):
        res = client.get("/admin/students", headers=auth_header())
        assert res.status_code == 200
        assert isinstance(res.json(), list)
        assert len(res.json()) >= 1

    def test_update_student(self):
        students = client.get("/admin/students", headers=auth_header()).json()
        sid = students[0]["id"]
        res = client.put(f"/admin/students/{sid}", json={
            "email": "updated@student.com"
        }, headers=auth_header())
        assert res.status_code == 200

    def test_delete_student(self):
        client.post("/admin/students", json={
            "first_name": "Delete", "last_name": "Me", "dob": "2004-01-01"
        }, headers=auth_header())
        students = client.get("/admin/students", headers=auth_header()).json()
        target = [s for s in students if s["first_name"] == "Delete"]
        if target:
            res = client.delete(f"/admin/students/{target[0]['id']}", headers=auth_header())
            assert res.status_code == 200


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


# ── RBAC Tests ────────────────────────────────────────

class TestRBAC:
    def test_no_token_rejected(self):
        res = client.get("/admin/students")
        assert res.status_code in [401, 403]

    def test_invalid_token_rejected(self):
        res = client.get("/admin/students", headers={"Authorization": "Bearer invalidtoken"})
        assert res.status_code == 401


# ── Validation Tests (#4, #9) ─────────────────────────

class TestValidation:
    def test_weak_password_rejected(self):
        res = client.post("/auth/change-password", json={
            "old_password": "Admin1234",
            "new_password": "short"
        }, headers=auth_header())
        assert res.status_code == 422

    def test_invalid_email_rejected(self):
        res = client.post("/admin/students", json={
            "first_name": "Bad",
            "last_name": "Email",
            "dob": "2004-01-01",
            "email": "not-an-email"
        }, headers=auth_header())
        assert res.status_code == 422

    def test_invalid_phone_rejected(self):
        res = client.post("/admin/students", json={
            "first_name": "Bad",
            "last_name": "Phone",
            "dob": "2004-01-01",
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
