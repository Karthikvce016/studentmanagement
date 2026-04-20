# Student Management System (SMS)

Student Management System built with **FastAPI**, **SQLAlchemy**, **MySQL**, and **HTML/CSS/JS** for a **Database Management Systems** course. The current design emphasizes relational modeling, offering-based academic workflows, integrity rules, audit trails, and report queries instead of treating the project as a generic CRUD app.

## What The Project Demonstrates
- Normalized auth/profile separation: `users`, `students`, `teachers`
- Academic delivery modeled through `course_offerings`
- Many-to-many mappings:
  - `students <-> course_offerings` via `enrollments`
  - `teachers <-> course_offerings` via `teacher_courses`
- Integrity constraints:
  - unique usernames, roll numbers, course codes
  - unique enrollment per `student_id + offering_id`
  - unique teacher assignment per `teacher_id + offering_id`
  - unique attendance slot per `enrollment_id + date + period + sub_period`
  - unique assessment name per `offering_id + type + name`
- Controlled domains with enums for attendance, assessment type, gender, admission category, category, and area
- Audit history:
  - `password_reset_audits`
  - `attendance_audits`
  - `mark_audits`
- Database-backed reporting:
  - attendance risk
  - course toppers
  - section performance
  - pass/fail summary
  - monthly attendance trend

## Product Features
- **Admin**
  - CRUD for students, teachers, courses
  - create and manage course offerings
  - assign teachers to offerings
  - enroll students into offerings
  - reset any student password to DOB in `DDMMYYYY`
  - run academic reports from the dashboard
- **Teacher**
  - view assigned offerings
  - filter students and attendance by section
  - one-click checkbox attendance with immediate save
  - create assessments with enforced structure
  - enter marks and keep mark history
- **Student**
  - view profile
  - view attendance by offering
  - view marks report with sessional and SGPA
  - change password

## Schema Direction
The central refinement from the earlier version is the introduction of **course offerings**.

Instead of binding enrollments, assignments, and assessments directly to a global course record, the project now models:

`course` -> `course_offering` -> `teacher assignment / enrollment / assessment`

That makes the schema closer to a real academic database because the same catalog course can be delivered in different semesters, years, and sections without duplicating catalog metadata.

## Setup

### 1. Prerequisites
- Python 3.10+
- MySQL running locally

### 2. Create the database
```sql
CREATE DATABASE sms_db;
```

### 3. Configure environment
Edit `.env` if your local credentials differ:
```env
DATABASE_URL=mysql+pymysql://root:root@localhost:3306/sms_db
JWT_SECRET_KEY=replace-me
```

### 4. Install dependencies
```bash
python3 -m pip install -r requirements.txt
```

### 5. Apply migrations
```bash
alembic upgrade head
```

### 6. Seed demo data
```bash
python3 seed.py
```

### 7. Run the server
```bash
python3 -m app.main
```

Open [http://localhost:8000](http://localhost:8000)

## Default Credentials
- **Admin**: `admin / admin123`
- **Teachers**
  - `rajesh.kumar / 15031985`
  - `priya.sharma / 22071988`
  - `amit.patel / 08111982`
  - `sunita.rao / 10041986`
- **Students**
  - username = `roll_number`
  - password = DOB in `DDMMYYYY`
  - example: `1602-24-733-001 / 16032007`

## Project Structure
```text
sms_py/
├── alembic/                    # Migration environment and revisions
├── app/
│   ├── main.py                 # FastAPI entry point
│   ├── config.py               # Environment config
│   ├── database.py             # SQLAlchemy setup
│   ├── models.py               # ORM schema
│   ├── schemas.py              # Pydantic validation
│   ├── security.py             # JWT + password hashing
│   ├── dependencies.py         # Auth and RBAC helpers
│   └── routers/
│       ├── auth.py
│       ├── admin.py
│       ├── teacher.py
│       └── student.py
├── docs/
│   ├── dbms_submission.md
│   ├── schema_erd.md
│   └── sql_queries.md
├── seed.py
├── static/
├── templates/
└── tests/
```

## Submission Aids
- [DBMS submission notes](/Users/karthik/4th%20sem%20projects/sms_py/docs/dbms_submission.md)
- [Schema ERD](/Users/karthik/4th%20sem%20projects/sms_py/docs/schema_erd.md)
- [SQL query appendix](/Users/karthik/4th%20sem%20projects/sms_py/docs/sql_queries.md)

## Demo Flow For Viva
1. Show the ERD and point out why `course_offerings` exists.
2. Create a student and explain roll number plus section assignment.
3. Create a course offering for a semester/section.
4. Assign a teacher to the offering and enroll a student.
5. Mark attendance for a period, then show the attendance audit trail in the database.
6. Create an assessment, upload marks, and show the mark audit trail.
7. Open the reports tab and explain how those results are derived from relational joins and aggregates.
