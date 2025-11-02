from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from kitchen_scheduler.core import security
from kitchen_scheduler.schemas.auth import TokenResponse

router = APIRouter()


@router.post("/token", response_model=TokenResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends()) -> TokenResponse:
    """
    Authenticate a planner against stored credentials.

    Replaced with real user lookup once persistence is wired. For now, this
    endpoint relies on the security module to validate a demo user.
    """
    user = security.verify_demo_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    access_token_expires = timedelta(minutes=security.settings.jwt_access_token_expires_minutes)
    token = security.create_access_token(subject=user["username"], expires_delta=access_token_expires)
    return TokenResponse(access_token=token, token_type="bearer")
