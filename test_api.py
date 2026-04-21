from app.database import SessionLocal
from app.models import User
import sys
db = SessionLocal()
admin = db.query(User).filter_by(username="admin").first()
print(admin.username if admin else "No admin user found")
