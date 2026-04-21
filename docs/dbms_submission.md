# DBMS Submission Notes

## Why This Is A DBMS Project
This project is centered on relational data design and database-driven workflows, not just UI screens.

The main database concepts demonstrated are:
- entity separation between authentication and profiles
- one-to-one relationships (`users -> students`, `users -> teachers`)
- many-to-many relationships through junction tables
- uniqueness constraints and referential integrity
- audit history tables for important state changes
- aggregate reporting over academic data

## Normalization Notes

### First Normal Form
- atomic values only
- no repeating groups inside student, teacher, attendance, or mark records

### Second Normal Form
- non-key attributes depend on the full key of each table
- example: attendance status depends on the full attendance slot key, not only on date or enrollment alone

### Third Normal Form
- authentication data is not duplicated in profile tables
- course catalog data is separated from course delivery data
- section metadata is separated from student records and reused through foreign keys

## Important Tables
- `users`
- `roles`
- `students`
- `teachers`
- `sections`
- `courses`
- `course_offerings`
- `teacher_courses`
- `enrollments`
- `attendance`
- `assessments`
- `marks`
- `password_reset_audits`
- `attendance_audits`
- `mark_audits`

## Integrity Rules Worth Mentioning In Viva
- username is unique
- roll number is unique
- course code is unique
- a student cannot be enrolled twice in the same offering
- a teacher cannot be assigned twice to the same offering
- an attendance slot is unique for one enrollment on one date/period/sub-period
- assessment names are unique within an offering and assessment type
- assessment type also controls allowed count and max marks

## Good Demo Talking Points
- why `course_offerings` is more realistic than directly attaching everything to `courses`
- why audit tables matter for accountability
- why section-based filtering belongs in the database model, not only in the frontend
- how attendance and marks reports use joins and aggregates across normalized tables
