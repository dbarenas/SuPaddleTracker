import pytest
from datetime import datetime, timedelta

# Assuming test_settings from conftest.py provides the consistent SECRET_KEY
from app.core.security import (
    encrypt_token, 
    decrypt_token, 
    create_access_token, 
    verify_token,
    settings as security_module_settings, # The settings instance used by security.py
    ALGORITHM, # Import for use in tests if needed, or rely on function defaults
    # Re-initialize cipher_suite if it's module-level and depends on settings.SECRET_KEY
    # This is the tricky part. We'll try to re-initialize it via a fixture.
)
from app.config import Settings # To create a settings object for patching
from jose import JWTError
from jose.exceptions import ExpiredSignatureError
from cryptography.fernet import Fernet
import base64


@pytest.fixture(autouse=True)
def override_security_module_settings(monkeypatch, test_settings: Settings):
    """
    Overrides the settings used by the security module and re-initializes
    any global objects that depend on these settings (like cipher_suite).
    """
    # Patch the settings instance directly within the security module
    monkeypatch.setattr(security_module_settings, 'SECRET_KEY', test_settings.SECRET_KEY)
    monkeypatch.setattr(security_module_settings, 'DATABASE_URL', test_settings.DATABASE_URL) # if security module uses it
    # Add other settings if security module uses them

    # Re-initialize cipher_suite as it's created at module load time in security.py
    # This logic must match how cipher_suite is initialized in app.core.security
    try:
        secret_key_bytes = test_settings.SECRET_KEY.encode('utf-8')
        padded_key = secret_key_bytes[:32].ljust(32, b'\0') 
        encryption_key_for_fernet = base64.urlsafe_b64encode(padded_key)
        reinitialized_cipher_suite = Fernet(encryption_key_for_fernet)
        monkeypatch.setattr('app.core.security.cipher_suite', reinitialized_cipher_suite)
    except Exception as e:
        pytest.fail(f"Failed to re-initialize cipher_suite for testing: {e}")


def test_token_encryption_decryption():
    original_token = "my_secret_strava_token_data_!@#$%^"
    encrypted = encrypt_token(original_token)
    assert encrypted != original_token
    decrypted = decrypt_token(encrypted)
    assert decrypted == original_token

def test_encrypt_empty_token_raises_value_error():
    with pytest.raises(ValueError, match="Token cannot be empty for encryption"):
        encrypt_token("")

def test_decrypt_empty_token_raises_value_error():
    with pytest.raises(ValueError, match="Encrypted token cannot be empty for decryption"):
        decrypt_token("")

def test_decrypt_invalid_token_raises_fernet_error():
    # Fernet typically raises InvalidToken, which is a subclass of Exception.
    # The exact exception might vary if our decrypt_token catches and re-raises.
    # Our current decrypt_token does not explicitly catch Fernet's InvalidToken.
    with pytest.raises(Exception): # Broad exception, Fernet's InvalidToken is expected
        decrypt_token("this_is_not_a_valid_fernet_token")

def test_jwt_creation_verification():
    payload_data = {"sub": "testuser@example.com", "strava_id": 12345}
    jwt_token = create_access_token(data=payload_data)
    assert jwt_token is not None
    
    verified_payload = verify_token(jwt_token)
    assert verified_payload is not None
    assert verified_payload["sub"] == payload_data["sub"]
    assert verified_payload["strava_id"] == payload_data["strava_id"]
    assert "exp" in verified_payload

def test_jwt_custom_expiry():
    custom_delta = timedelta(minutes=5)
    payload_data = {"sub": "test_expiry_user", "strava_id": 67890}
    jwt_token = create_access_token(data=payload_data, expires_delta=custom_delta)
    
    verified_payload = verify_token(jwt_token)
    assert verified_payload is not None
    
    expected_expiry_time = datetime.utcnow() + custom_delta
    actual_expiry_time = datetime.fromtimestamp(verified_payload["exp"])
    # Allow for a small difference due to token creation/verification time
    assert abs((expected_expiry_time - actual_expiry_time).total_seconds()) < 5 

def test_jwt_expired():
    # Create a token that expired 10 seconds ago
    expired_delta = timedelta(seconds=-10)
    payload_data = {"sub": "expired_user", "strava_id": 13579}
    expired_jwt_token = create_access_token(data=payload_data, expires_delta=expired_delta)
    
    # verify_token is designed to return None for expired or invalid tokens
    assert verify_token(expired_jwt_token) is None
    
    # If we wanted to check for the specific exception from jose.jwt.decode:
    with pytest.raises(ExpiredSignatureError):
        # Attempt to decode directly to catch the specific error
        from jose import jwt as jose_jwt
        jose_jwt.decode(expired_jwt_token, security_module_settings.SECRET_KEY, algorithms=[ALGORITHM])


def test_jwt_invalid_signature():
    payload_data = {"sub": "user_bad_sig", "strava_id": 24680}
    jwt_token = create_access_token(data=payload_data)
    
    # Tamper with the token or use a wrong key for verification
    # For simplicity, let's try to verify with a wrong key
    wrong_key = "a_completely_different_secret_key_!@#$"
    
    with pytest.raises(JWTError): # jose.exceptions.JWTError is the base for signature errors
        from jose import jwt as jose_jwt
        jose_jwt.decode(jwt_token, wrong_key, algorithms=[ALGORITHM])

    # Test that our verify_token function returns None for this case
    # To do this, we need to make verify_token use the wrong key temporarily
    # This is harder without refactoring verify_token or more complex patching.
    # A simpler test for verify_token itself:
    # Create a token with one key, try to verify with another via our verify_token
    
    # Create token with current (test) settings
    token_good_key = create_access_token({"data": "test"})
    
    # Temporarily change the key used by verify_token (via its settings object)
    original_key = security_module_settings.SECRET_KEY
    security_module_settings.SECRET_KEY = "another_key_entirely_different_123"
    try:
        assert verify_token(token_good_key) is None
    finally:
        security_module_settings.SECRET_KEY = original_key # Restore for other tests


def test_verify_malformed_token():
    malformed_token = "this.is.not.a.jwt"
    assert verify_token(malformed_token) is None

    # If we wanted to check for the specific exception from jose.jwt.decode:
    with pytest.raises(JWTError):
        from jose import jwt as jose_jwt
        jose_jwt.decode(malformed_token, security_module_settings.SECRET_KEY, algorithms=[ALGORITHM])
