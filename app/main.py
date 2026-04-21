"""FastAPI application entry point."""

import logging
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, admin, teacher, student

logger = logging.getLogger(__name__)

app = FastAPI(title="Student Management System", version="1.0.0")

# ── CORS Middleware (#13) ─────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Register API routers
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(teacher.router)
app.include_router(student.router)


# ── Page Routes (serve HTML templates) ────────────────
# NOTE (#3): These page routes have no server-side auth guard.
# The HTML/JS is public; actual data is protected by JWT-guarded
# API endpoints. This is a standard SPA trade-off — the page
# structure is visible, but no data is exposed without a valid token.

@app.get("/", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/change-password", response_class=HTMLResponse)
def change_password_page(request: Request):
    return templates.TemplateResponse("change_password.html", {"request": request})

@app.get("/admin/dashboard", response_class=HTMLResponse)
def admin_dashboard_page(request: Request):
    return templates.TemplateResponse("admin/dashboard.html", {"request": request})

@app.get("/admin/bulk-edit", response_class=HTMLResponse)
def admin_bulk_edit_page(request: Request):
    return templates.TemplateResponse("admin/bulk_edit.html", {"request": request})

@app.get("/teacher/dashboard", response_class=HTMLResponse)
def teacher_dashboard_page(request: Request):
    return templates.TemplateResponse("teacher/dashboard.html", {"request": request})

@app.get("/student/dashboard", response_class=HTMLResponse)
def student_dashboard_page(request: Request):
    return templates.TemplateResponse("student/dashboard.html", {"request": request})


if __name__ == "__main__":
    import uvicorn
    logger.info("Starting SMS server on http://0.0.0.0:8000")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
