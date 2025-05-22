import pytest
from fastapi.testclient import TestClient
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from httpx import Response, codes as http_status_codes
import io
import os
import glob

from app.config import Settings
# MOCK_STRAVA_TOKEN_RESPONSE is needed for login simulation
from .test_auth_flow import MOCK_STRAVA_TOKEN_RESPONSE 

# Define a specific Strava ID for these tests to make assertions easier
TEST_USER_STRAVA_ID = MOCK_STRAVA_TOKEN_RESPONSE["athlete"]["id"] # Should be 12345 from test_auth_flow

# Helper function to simulate login and get JWT
async def simulate_login_get_jwt(client: TestClient, httpx_mock, test_settings: Settings, monkeypatch) -> str:
    """
    Simulates the Strava OAuth callback to log in a user and get a JWT.
    """
    monkeypatch.setattr('app.routers.auth.settings', test_settings)
    
    httpx_mock.add_response(
        method="POST",
        url="https://www.strava.com/oauth/token",
        json=MOCK_STRAVA_TOKEN_RESPONSE, # Uses the athlete data from here
        status_code=http_status_codes.OK
    )
    # No separate athlete fetch mock needed if athlete data in token response
    
    callback_url = f"/auth/strava/callback?code=testcode_for_reg_test&scope=read,profile:read_all"
    response = client.get(callback_url)
    assert response.status_code == http_status_codes.OK
    return response.json()["access_token"]


@pytest.mark.asyncio
async def test_get_register_unauthorized(client: TestClient):
    response = client.get("/register")
    # Expecting 401 Unauthorized because get_current_user_strava_id uses auto_error=True
    assert response.status_code == http_status_codes.UNAUTHORIZED 
    assert "Not authenticated" in response.json()["detail"] # Or "Could not validate credentials"

@pytest.mark.asyncio
async def test_get_register_authorized(
    client: TestClient, db_session: AsyncSession, httpx_mock, test_settings: Settings, monkeypatch
):
    monkeypatch.setattr('app.routers.registration.settings', test_settings, raising=False)
    # The registration router itself doesn't use settings, but its dependencies might (like auth)

    jwt_token = await simulate_login_get_jwt(client, httpx_mock, test_settings, monkeypatch)
    headers = {"Authorization": f"Bearer {jwt_token}"}
    
    response = client.get("/register", headers=headers)
    assert response.status_code == http_status_codes.OK
    content = response.text
    assert f"Logged in as: <strong>{MOCK_STRAVA_TOKEN_RESPONSE['athlete']['firstname']} {MOCK_STRAVA_TOKEN_RESPONSE['athlete']['lastname']}</strong>" in content
    assert f"(Strava ID: {TEST_USER_STRAVA_ID})" in content
    assert f'<input type="text" name="nombre" value="{MOCK_STRAVA_TOKEN_RESPONSE["athlete"]["firstname"]} {MOCK_STRAVA_TOKEN_RESPONSE["athlete"]["lastname"]}">' in content


@pytest.mark.asyncio
async def test_post_register_unauthorized(client: TestClient):
    # Prepare mock form data (though it won't be processed)
    form_data = {'nombre': 'Test User', 'edad': '30', 'categoria': 'elite'}
    mock_file_content = b"mock payment content for unauthorized test"
    files = {'pago': ('test_payment_unauth.pdf', io.BytesIO(mock_file_content), 'application/pdf')}
    
    response = client.post("/register", data=form_data, files=files)
    assert response.status_code == http_status_codes.UNAUTHORIZED
    assert "Not authenticated" in response.json()["detail"] # Or "Could not validate credentials"

@pytest.mark.asyncio
async def test_post_register_authorized_successful(
    client: TestClient, db_session: AsyncSession, httpx_mock, test_settings: Settings, monkeypatch
):
    monkeypatch.setattr('app.routers.registration.settings', test_settings, raising=False)

    jwt_token = await simulate_login_get_jwt(client, httpx_mock, test_settings, monkeypatch)
    headers = {"Authorization": f"Bearer {jwt_token}"}
    
    form_data = {'nombre': 'Test Reg User', 'edad': '33', 'categoria': 'sub12'}
    mock_file_content = b"actual mock payment content for registration"
    # Use a unique filename to avoid clashes if tests run concurrently or don't clean up fully
    payment_filename = f"test_payment_reg_{TEST_USER_STRAVA_ID}.pdf" 
    
    # Correct way to pass UploadFile-like data to TestClient for files:
    # files = {'pago': (filename, BytesIO_object, content_type)}
    files_data = {'pago': (payment_filename, io.BytesIO(mock_file_content), 'application/pdf')}
    
    # Path where file is expected to be saved
    expected_payments_dir = "static/payments/"
    # The filename in the app is constructed as: f"payment_{strava_id}_{safe_filename}"
    expected_saved_filename = f"payment_{TEST_USER_STRAVA_ID}_{payment_filename}"
    expected_filepath = os.path.join(expected_payments_dir, expected_saved_filename)

    # Ensure the directory exists (app should create it, but good for test setup too)
    os.makedirs(expected_payments_dir, exist_ok=True)
    
    # Clean up before test, in case of previous failed run
    if os.path.exists(expected_filepath):
        os.remove(expected_filepath)

    try:
        response = client.post("/register", data=form_data, files=files_data, headers=headers)
        
        assert response.status_code == http_status_codes.OK
        response_data = response.json()
        assert f"Registrado con éxito para Strava ID {TEST_USER_STRAVA_ID}" in response_data["msg"]
        assert response_data["nombre"] == form_data["nombre"]
        assert response_data["categoria"] == form_data["categoria"]
        assert response_data["strava_id"] == TEST_USER_STRAVA_ID
        assert response_data["payment_proof_filename"] == expected_saved_filename
        
        # Verify file was saved
        assert os.path.exists(expected_filepath), f"File not found at {expected_filepath}"
        with open(expected_filepath, "rb") as f:
            saved_content = f.read()
            assert saved_content == mock_file_content
            
    finally:
        # Clean up the created file
        if os.path.exists(expected_filepath):
            os.remove(expected_filepath)
        # Attempt to remove directory if empty (optional, might conflict if other tests use it)
        # if os.path.exists(expected_payments_dir) and not os.listdir(expected_payments_dir):
        #     os.rmdir(expected_payments_dir)

@pytest.mark.asyncio
async def test_post_register_file_upload_error(
    client: TestClient, db_session: AsyncSession, httpx_mock, test_settings: Settings, monkeypatch
):
    # This test would require a way to make pago.read() fail or os.makedirs/open fail.
    # Mocking these low-level os/file operations can be complex and might be better
    # as a unit test for the router logic itself if that level of detail is needed.
    # For an integration test, it's hard to simulate this without more invasive mocking.
    # For now, we'll skip this specific error simulation.
    pass
