"""Auth routes — login and password change."""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.schemas import LoginRequest, LoginResponse, ChangePasswordRequest
from app.security import verify_password, hash_password, create_access_token
from app.dependencies import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate user and return JWT token."""
    user = db.query(User).filter(User.username == req.username).first()
    if not user or not verify_password(req.password, user.password_hash):
        logger.warning("Failed login attempt for username: %s", req.username)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")

    token = create_access_token({"user_id": user.id, "role": user.role.name})
    logger.info("User %s logged in (role: %s)", user.username, user.role.name)
    return LoginResponse(
        access_token=token,
        role=user.role.name,
        must_change_password=user.must_change_password
    )


@router.post("/change-password")
def change_password(req: ChangePasswordRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Change password. Also clears the must_change_password flag.
    New password must be at least 8 chars with mixed letters + numbers (#4).
    """
    if not verify_password(req.old_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Old password is incorrect")

    current_user.password_hash = hash_password(req.new_password)
    current_user.must_change_password = False
    db.commit()
    logger.info("User %s changed their password", current_user.username)
    return {"message": "Password changed successfully"}
