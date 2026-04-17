# Student Management System (SMS)

A full-stack Student Management System built with **FastAPI** + **MySQL** + **HTML/CSS/JS**.

## Features
- **Role-based auth**: Admin, Teacher, Student (JWT + bcrypt)
- **Admin**: CRUD for students, teachers, courses; enrollment & teacher-course assignment
- **Teacher**: View assigned courses, mark attendance, create assessments, enter marks
- **Student**: View profile, attendance %, marks per assessment, change password
- **Auto password**: Default password = DOB (DDMMYYYY), forced change on first login

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
