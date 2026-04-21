# Student Management System (SMS)

A full-stack Student Management System built with **FastAPI** + **MySQL** + **HTML/CSS/JS** for a **Database Management Systems** course project. The app demonstrates database design, integrity constraints, role-based workflows, and reporting on top of a relational schema.

## Features
- **Role-based auth**: Admin, Teacher, Student (JWT + bcrypt)
- **Admin**: CRUD for students, teachers, courses; enrollment & teacher-course assignment; reset student passwords
- **Teacher**: View assigned courses, mark attendance with one-click checkbox actions, create assessments, enter marks
- **Student**: View profile, attendance %, marks per assessment, change password
- **Auto password**: Default password = DOB (DDMMYYYY), forced change on first login

## DBMS Course Alignment
- **Normalized entity design**: `users` stores authentication, while `students` and `teachers` store profile data in separate tables.
- **One-to-one relationships**: `users -> students` and `users -> teachers`.
- **Many-to-many relationships**:
  - `students <-> courses` through `enrollments`
  - `teachers <-> courses` through `teacher_courses`
- **Integrity constraints**:
  - unique usernames, roll numbers, course codes
  - unique student-course enrollment
  - unique attendance slot per `enrollment_id + date + period + sub_period`
- **Controlled domains and validation**:
  - enums for attendance status, gender, admission category, assessment type
  - Pydantic validation for payload rules such as password strength, phone format, credits, and period range
- **Database-backed workflows and reports**:
  - attendance summary and per-slot attendance grid
  - section-wise student assignment through roll number logic
  - marks entry, assessment limits, and report-style student views

## Recommended Demo Focus For DBMS Submission
1. Show the schema and explain why auth is separated from student and teacher profiles.
2. Demonstrate many-to-many mappings by enrolling a student in a course and assigning a teacher to that course.
3. Show attendance uniqueness by marking a date/period/sub-period slot and then updating the same slot.
4. Show validation and integrity rules by triggering one rejected case, such as duplicate assignment or invalid credits.
5. Show reporting queries through dashboard stats, attendance summary, and marks views.

## Quick Start (For Demo)
Run the following steps to quickly start the project:

### 1. Create the Database
Log into your MySQL terminal (or client) and run:
```sql
CREATE DATABASE sms_db;
```

### 2. Install and Run
Run these commands in your code editor terminal (using `python3` instead of `python` if you're on a Mac):
```bash
python3 -m pip install -r requirements.txt
python3 seed.py
python3 -m app.main
```

### 3. Login
- Open **http://localhost:8000** in your browser.
- **Admin Username**: `admin`
- **Admin Password**: `admin123`

## Setup

### 1. Prerequisites
- Python 3.10+
- MySQL Server running locally

### 2. Create the database
```sql
CREATE DATABASE sms_db;
```

### 3. Configure connection
Edit `.env` if your MySQL credentials differ from the defaults:
```
DATABASE_URL=mysql+pymysql://root:root@localhost:3306/sms_db
```

### 4. Install dependencies
```bash
pip install -r requirements.txt
```

### 5. Seed sample data
```bash
python seed.py
```

### 6. Run the server
```bash
python -m app.main
```
Server starts at **http://localhost:8000**

### 7. API Docs
Open **http://localhost:8000/docs** for Swagger UI.

## Test Credentials

| Role    | Username       | Password   |
|---------|---------------|------------|
| Admin   | admin         | admin123   |
| Teacher | rajesh.kumar  | 15031985   |
| Teacher | priya.sharma  | 22071988   |
| Student | aarav.singh   | 10012004   |
| Student | diya.gupta    | 20052004   |

## Project Structure
```
sms_py/
├── app/
│   ├── main.py          # FastAPI entry point
│   ├── config.py         # Environment config
│   ├── database.py       # SQLAlchemy setup
│   ├── models.py         # All ORM models (10 tables)
│   ├── schemas.py        # Pydantic validation
│   ├── security.py       # JWT + bcrypt utils
│   ├── dependencies.py   # Auth & RBAC dependencies
│   └── routers/          # API route handlers
│       ├── auth.py
│       ├── admin.py
│       ├── teacher.py
│       └── student.py
├── static/css/style.css  # Global styles
├── static/js/app.js      # Shared JS utilities
├── templates/            # Jinja2 HTML pages
├── seed.py               # Sample data seeder
├── .env                  # Config
└── requirements.txt
```
