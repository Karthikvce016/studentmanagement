Here is the exact list of backend changes I made, and why each one improves the project.

**1. Added Roll Number Parsing**
Changed:
- Added `parse_roll_number()` in `app/models.py`.
- Student API output now includes:
  - `roll_college_code`
  - `roll_joining_year`
  - `roll_serial`

Why better:
- Earlier, the roll number was just stored as text.
- Now the system can extract meaningful academic information from `1602-24-733-016`.
- This supports your roadmap item: using roll numbers for auto-categorization.
- It also makes viva/demo explanation stronger because roll number logic is now explicit.

Example:
```json
{
  "roll_number": "1602-24-733-016",
  "roll_college_code": "1602",
  "roll_joining_year": 2024,
  "roll_serial": 16
}
```

**2. Added Sub-Period Attendance**
Changed:
- Added `sub_period` to the `Attendance` model.
- Attendance is now identified by:
  - student enrollment
  - date
  - period
  - sub-period

Why better:
- Previously, attendance supported only one record per period.
- Now it supports split periods or lab-style periods.
- Example: period `7`, sub-period `2`.
- This better matches real college schedules where one lab/class can span multiple slots.

Old uniqueness:
```text
student + date + period
```

New uniqueness:
```text
student + date + period + sub_period
```

**3. Increased Attendance Period Support**
Changed:
- Period validation changed from `1-6` to `1-7`.

Why better:
- Your roadmap mentioned realistic daily periods and asked whether the system should handle more than the current setup.
- The backend now supports 7 standard periods per day.
- This is closer to many college timetables.

**4. Added Teacher Course Section Discovery**
Changed:
- Added endpoint:
```text
GET /teacher/courses/{course_id}/sections
```

Why better:
- Earlier, teachers could filter by `section_id`, but there was no teacher-side endpoint to know which sections exist for a course.
- Now a teacher can fetch sections for an assigned course before managing attendance or marks.
- This supports section-based teacher workflows.

**5. Added Attendance Grid Backend**
Changed:
- Added endpoint:
```text
GET /teacher/attendance/{course_id}/grid
```

Why better:
- The roadmap asked for spreadsheet-like teacher entry.
- You told me not to touch frontend, so I added backend support only.
- This endpoint returns rows shaped for an Excel-like UI later.

It gives data like:
```json
{
  "roll_number": "1602-24-733-001",
  "student_name": "Karthik Reddy",
  "section": "A",
  "date": "2026-03-01",
  "period": 7,
  "sub_period": 2,
  "status": "PRESENT"
}
```

**6. Added Attendance CSV Template Download**
Changed:
- Added endpoint:
```text
GET /teacher/attendance/{course_id}/template
```

Why better:
- Teachers can download a CSV template for attendance entry.
- It includes roll number, name, section, date, period, sub-period, and status.
- This reduces manual entry mistakes because the rows are generated from enrolled students.

**7. Added Attendance CSV Upload**
Changed:
- Added endpoint:
```text
POST /teacher/attendance/{course_id}/upload-csv
```

Why better:
- Teachers can upload attendance in bulk using roll numbers.
- The backend validates:
  - CSV is not empty
  - required columns exist
  - roll number belongs to the course
  - roll number belongs to the selected section, if section filter is used
  - duplicate roll numbers are rejected
  - attendance status is valid

This is much better than manually entering every student one by one.

**8. Added Marks Grid Backend**
Changed:
- Added endpoint:
```text
GET /teacher/marks/{assessment_id}/grid
```

Why better:
- Returns all enrolled students for an assessment, including students who do not have marks yet.
- This is better than the old marks view, which only returned students who already had marks.
- It supports spreadsheet-style entry later without frontend changes now.

**9. Added Marks CSV Template Download**
Changed:
- Added endpoint:
```text
GET /teacher/marks/{assessment_id}/template
```

Why better:
- Teachers can download a prefilled marks template with:
  - roll number
  - student name
  - section
  - marks obtained
  - max marks

This directly supports the roadmap’s external upload workflow.

**10. Added Marks CSV Upload**
Changed:
- Added endpoint:
```text
POST /teacher/marks/{assessment_id}/upload-csv
```

Why better:
- Teachers can upload marks in bulk.
- The backend validates:
  - required columns exist
  - roll number is enrolled in the course
  - duplicate roll numbers are rejected
  - marks are numeric
  - marks are not negative
  - marks do not exceed max marks

This is safer and faster than individual mark entry.

**11. Enforced Strict Assessment Structure**
Changed:
- Internal tests must use max marks `30`.
- Quizzes must use max marks `5`.
- Assignments must use max marks `5`.
- Limits remain:
  - 2 Internals
  - 3 Quizzes
  - 3 Assignments

Why better:
- Previously, the count limits existed, but a teacher could still create an internal with wrong max marks like `20`.
- Now the backend enforces the standardized structure from the roadmap.
- This makes marks calculation more reliable.

**12. Blocked Duplicate Assessment Names**
Changed:
- Added uniqueness for:
```text
course_id + assessment_type + assessment_name
```

Why better:
- Prevents duplicate names like two `Int1` records for the same course/type.
- Keeps reports predictable because `Int1`, `Int2`, `Quiz1`, etc. should be unique.

**13. Improved Marks Upload Validation**
Changed:
- The normal JSON marks upload now checks:
  - student is enrolled in the assessment’s course
  - duplicate student IDs are rejected
  - marks do not exceed max marks

Why better:
- Previously, it was easier to accidentally upload marks for the wrong student/course.
- Now the backend protects academic data consistency.

**14. Updated Student Attendance Detail**
Changed:
- Student attendance detail now displays sub-period records correctly.

Why better:
- If a teacher marks period `7`, sub-period `2`, the student view can show it as:
```text
period_7_2
```

Previously, sub-periods were impossible to represent.

**15. Updated Seed Data**
Changed:
- Seeded attendance records now include `sub_period=1`.

Why better:
- The seed script remains compatible with the new attendance model.
- Existing generated demo data still works.

**16. Added Tests**
Changed:
- Test count increased from `22` to `24`.
- Added tests for:
  - roll number parsed output
  - teacher course sections
  - strict assessment max marks
  - marks CSV template/upload
  - marks grid
  - sub-period attendance
  - attendance CSV template/upload
  - attendance grid

Why better:
- The roadmap features are now verified by automated tests.
- Future edits are less likely to break these flows silently.

**17. Did Not Touch Frontend**
Changed:
- No files in `templates/` were modified.
- No files in `static/` were modified.

Why better:
- You specifically asked not to touch frontend.
- All roadmap progress was added through backend/API support only.

**Current Validation**
The backend passed:

```text
24 passed, 1 warning
```

Also compiled successfully:

```text
python -m compileall -q app
```

**Important DB Note**
Because I added `attendance.sub_period`, an existing MySQL database needs a migration or reset/reseed.

If you are using your current MySQL database, the app may fail until the `attendance` table gets the new column.