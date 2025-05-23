from fastapi import APIRouter, Depends, Request, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from typing import Optional

from app.config import Settings
from app.core.security import verify_admin_password, create_access_token
from app.dependencies import require_admin_auth # Import the dependency
# No db session needed for basic admin login if checking against .env

settings = Settings()
router = APIRouter(prefix="/admin", tags=["Admin Authentication"])
templates = Jinja2Templates(directory="app/templates")

@router.get("/login", response_class=HTMLResponse, name="admin_login_form")
async def admin_login_page(request: Request, error_message: Optional[str] = None):
    return templates.TemplateResponse("admin/admin_login.html", {"request": request, "error_message": error_message})

@router.post("/login", response_class=RedirectResponse, name="admin_login_post")
async def handle_admin_login(
    request: Request, # Keep for potential future use or if passing messages
    username: str = Form(...), 
    password: str = Form(...)
):
    if not settings.ADMIN_PASSWORD_HASH: # Ensure hash is set in .env
        # In a real scenario, log this critical misconfiguration
        # Re-render login form with a generic error
        return templates.TemplateResponse(
            "admin/admin_login.html", 
            {"request": request, "error_message": "Admin login is not configured."},
            status_code=status.HTTP_400_BAD_REQUEST # Or 500 internal server error
        )

    is_valid_username = (username == settings.ADMIN_USERNAME)
    is_valid_password = verify_admin_password(password, settings.ADMIN_PASSWORD_HASH)

    if not (is_valid_username and is_valid_password):
        # Re-render login form with an error message
        # One way to pass error to GET is via query param, or use flash messages if implemented
        # For simplicity, directly rendering here (though PRG pattern is better)
        return templates.TemplateResponse(
            "admin/admin_login.html", 
            {"request": request, "error_message": "Invalid username or password."},
            status_code=status.HTTP_400_BAD_REQUEST # Or 401 if preferred for failed login attempt
        )
        # Or, using a redirect to GET with a query parameter for the error:
        # return RedirectResponse(
        #     url=router.url_path_for("admin_login_form") + "?error_message=Invalid username or password.", 
        #     status_code=status.HTTP_303_SEE_OTHER
        # )


    # Credentials are valid, create admin JWT
    admin_jwt_payload = {"sub": settings.ADMIN_USERNAME} # Subject can be admin username
    admin_access_token = create_access_token(data=admin_jwt_payload, is_admin=True)

    # Redirect to admin dashboard
    response = RedirectResponse(
        url=router.url_path_for("admin_dashboard"), # Use named route
        status_code=status.HTTP_303_SEE_OTHER
    )
    response.set_cookie(
        key="admin_access_token",
        value=admin_access_token, 
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60, # Use configured expiry
        samesite="Lax",
        # secure=settings.SECURE_COOKIE, # Add if SECURE_COOKIE is in settings and app is HTTPS
    )
    return response

@router.post("/logout", response_class=RedirectResponse, name="admin_logout_post")
async def handle_admin_logout(request: Request): # Keep request for consistency
    # Redirect to admin login page after logout
    response = RedirectResponse(url=router.url_path_for("admin_login_form"), status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(key="admin_access_token", httponly=True, samesite="Lax") # Add secure if used
    return response

@router.get("/dashboard", response_class=HTMLResponse, name="admin_dashboard")
async def admin_dashboard_page(
    request: Request,
    admin_username: Optional[str] = Depends(require_admin_auth) # Protect route
):
    return templates.TemplateResponse(
        "admin/dashboard_admin.html", 
        {"request": request, "admin_user": admin_username} # Pass admin_username if needed by template
    )
