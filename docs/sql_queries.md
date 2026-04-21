# SQL Query Appendix

These are representative DBMS-style queries that match the implemented schema.

## 1. Students Below 75 Percent Attendance
```sql
SELECT
    s.roll_number,
    CONCAT(s.first_name, ' ', s.last_name) AS student_name,
    c.code AS course_code,
    co.academic_year,
    co.semester,
    ROUND(
        100.0 * SUM(CASE WHEN a.status = 'PRESENT' THEN 1 ELSE 0 END) / COUNT(a.id),
        1
    ) AS attendance_percentage
FROM attendance a
JOIN enrollments e ON e.id = a.enrollment_id
JOIN students s ON s.id = e.student_id
JOIN course_offerings co ON co.id = e.offering_id
JOIN courses c ON c.id = co.course_id
GROUP BY s.id, co.id
HAVING attendance_percentage < 75
ORDER BY attendance_percentage ASC;
```

## 2. Topper Per Course Offering
```sql
SELECT
    co.id AS offering_id,
    c.code AS course_code,
    s.roll_number,
    CONCAT(s.first_name, ' ', s.last_name) AS student_name,
    SUM(m.marks_obtained) AS total_marks
FROM course_offerings co
JOIN courses c ON c.id = co.course_id
JOIN assessments ass ON ass.offering_id = co.id
JOIN marks m ON m.assessment_id = ass.id
JOIN students s ON s.id = m.student_id
GROUP BY co.id, s.id
ORDER BY co.id, total_marks DESC;
```

## 3. Section-Wise Average Sessional
```sql
SELECT
    sec.branch_code,
    sec.name AS section_name,
    ROUND(AVG(m.marks_obtained), 2) AS avg_marks
FROM marks m
JOIN students s ON s.id = m.student_id
JOIN sections sec ON sec.id = s.section_id
GROUP BY sec.id
ORDER BY sec.branch_code, sec.name;
```

## 4. Monthly Attendance Trend
```sql
SELECT
    DATE_FORMAT(a.date, '%Y-%m') AS month_key,
    COUNT(*) AS total_records,
    SUM(CASE WHEN a.status = 'PRESENT' THEN 1 ELSE 0 END) AS present_records,
    ROUND(
        100.0 * SUM(CASE WHEN a.status = 'PRESENT' THEN 1 ELSE 0 END) / COUNT(*),
        1
    ) AS present_percentage
FROM attendance a
GROUP BY month_key
ORDER BY month_key;
```

## 5. Audit Trail For Attendance Changes
```sql
SELECT
    aa.changed_at,
    t.first_name,
    t.last_name,
    s.roll_number,
    aa.date,
    aa.period,
    aa.sub_period,
    aa.old_status,
    aa.new_status
FROM attendance_audits aa
JOIN teachers t ON t.id = aa.teacher_id
JOIN enrollments e ON e.id = aa.enrollment_id
JOIN students s ON s.id = e.student_id
ORDER BY aa.changed_at DESC;
```
