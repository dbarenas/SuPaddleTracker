import pytest
from fastapi.testclient import TestClient
from app.config import Settings # To get ADMIN_USERNAME for test login

@pytest.mark.asyncio
async def test_admin_login_success(client: TestClient, test_settings: Settings):
    # Arrange
    login_data = {
        "username": test_settings.ADMIN_USERNAME, # Use username from test_settings
        "password": "testadminpass" # The plain password corresponding to the hash in test_settings
    }
    
    # Act
    response = client.post("/admin/login", data=login_data, allow_redirects=False)
    
    # Assert
    assert response.status_code == 303, "Expected redirect to admin dashboard"
    assert "location" in response.headers
    # Assuming the route for admin_dashboard is named "admin_dashboard" in admin_auth router
    # and that router.url_path_for("admin_dashboard") correctly resolves to "/admin/dashboard"
    # For TestClient, it's often simpler to check the direct path if it's fixed.
    assert response.headers["location"] == "/admin/dashboard" 
    
    # Check for admin_access_token cookie
    assert "admin_access_token" in response.cookies
    admin_cookie = response.cookies["admin_access_token"]
    assert admin_cookie is not None
    # Further cookie checks (HttpOnly, Secure, Path) are harder with TestClient's simple cookie jar
    # but we can at least verify it's set.

@pytest.mark.asyncio
async def test_admin_login_failure_wrong_password(client: TestClient, test_settings: Settings):
    # Arrange
    login_data = {
        "username": test_settings.ADMIN_USERNAME,
        "password": "wrongadminpassword"
    }
    
    # Act
    response = client.post("/admin/login", data=login_data, allow_redirects=False)
    
    # Assert
    # Expecting login page re-render with error (status 400 as per current router)
    assert response.status_code == 400, response.text 
    assert "admin_access_token" not in response.cookies
    assert "Invalid username or password." in response.text # Check for error message

@pytest.mark.asyncio
async def test_admin_login_failure_wrong_username(client: TestClient):
    # Arrange
    login_data = {
        "username": "nonexistentadmin",
        "password": "testadminpass"
    }
    
    # Act
    response = client.post("/admin/login", data=login_data, allow_redirects=False)
    
    # Assert
    assert response.status_code == 400, response.text
    assert "admin_access_token" not in response.cookies
    assert "Invalid username or password." in response.text

@pytest.mark.asyncio
async def test_admin_logout(client: TestClient, test_settings: Settings):
    # Arrange: First, log in as admin to get the cookie
    login_data = {
        "username": test_settings.ADMIN_USERNAME,
        "password": "testadminpass" 
    }
    login_response = client.post("/admin/login", data=login_data, allow_redirects=False)
    assert login_response.status_code == 303
    assert "admin_access_token" in login_response.cookies
    
    # Act: Call logout endpoint (client will use cookies from previous response)
    logout_response = client.post("/admin/logout", allow_redirects=False)
    
    # Assert
    assert logout_response.status_code == 303
    # Assuming admin_login_form route is named "admin_login_form" in admin_auth router
    # and that router.url_path_for("admin_login_form") correctly resolves to "/admin/login"
    assert logout_response.headers["location"] == "/admin/login" 
    
    # Check that the cookie is cleared
    assert "set-cookie" in logout_response.headers
    assert "admin_access_token=;" in logout_response.headers["set-cookie"]
    assert "Max-Age=0" in logout_response.headers["set-cookie"]
