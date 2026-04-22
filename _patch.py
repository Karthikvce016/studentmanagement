"""Patch script to add 'Assign Teacher' button to courses table in admin dashboard."""
import sys

path = 'templates/admin/dashboard.html'
with open(path, 'r') as f:
    content = f.read()

# Find the first editCourse button and add Assign Teacher before it
old = """<button class="btn btn-outline btn-sm" onclick='editCourse"""
new = """<button class="btn btn-primary btn-sm" data-course-id="${esc(course.id)}" data-course-name="${esc(course.code)}" onclick="openAssignCourseModal({preCourseId: this.dataset.courseId, courseName: this.dataset.courseName})">+ Assign Teacher</button>\r\n                        <button class="btn btn-outline btn-sm" onclick='editCourse"""

if old not in content:
    print("ERROR: Could not find target string", file=sys.stderr)
    sys.exit(1)

# Only replace the first occurrence (courses table, not editCourse modal)
content = content.replace(old, new, 1)

with open(path, 'w') as f:
    f.write(content)

print("Patched successfully!")
