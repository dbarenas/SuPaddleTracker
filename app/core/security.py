import base64
from datetime import datetime, timedelta, timezone # Added timezone
from passlib.context import CryptContext # Added for password hashing
from cryptography.fernet import Fernet
from jose import jwt, JWTError
from jose.exceptions import ExpiredSignatureError 

from app.config import Settings

settings = Settings()

# --- Fernet Encryption ---
secret_key_bytes = settings.SECRET_KEY.encode('utf-8')
padded_key = secret_key_bytes[:32].ljust(32, b'\0') 
encryption_key = base64.urlsafe_b64encode(padded_key)
cipher_suite = Fernet(encryption_key)

def encrypt_token(token: str) -> str:
    if not token:
        raise ValueError("Token cannot be empty for encryption")
    return cipher_suite.encrypt(token.encode()).decode()

def decrypt_token(encrypted_token: str) -> str:
    if not encrypted_token:
        raise ValueError("Encrypted token cannot be empty for decryption")
    return cipher_suite.decrypt(encrypted_token.encode()).decode()

# --- Password Hashing for Admin ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_admin_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against a hashed password."""
    if not plain_password or not hashed_password:
        return False
    return pwd_context.verify(plain_password, hashed_password)

def hash_admin_password(password: str) -> str: # Optional utility
    """Hashes a password using the configured context (bcrypt)."""
    return pwd_context.hash(password)

# --- JWT Authentication ---
ALGORITHM = "HS256"
# Use ACCESS_TOKEN_EXPIRE_MINUTES from settings if available, otherwise default
# The Settings class now has ACCESS_TOKEN_EXPIRE_MINUTES with a default
# ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES # This will be used from settings

def create_access_token(
    data: dict, 
    expires_delta: timedelta | None = None,
    is_admin: bool = False # New parameter for admin claim
) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta # Changed to timezone.utc
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES # Use from settings
        )
    to_encode.update({"exp": expire})

    if is_admin: # Add admin claim if true
        to_encode.update({"is_admin": True})
    
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> dict | None:
    try:
        # Ensure that datetime comparisons are timezone-aware if 'exp' is set with timezone
        # JWT 'exp' is usually a UTC timestamp, so this should be fine.
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except ExpiredSignatureError:
        return None 
    except JWTError:
        return None

# Example usage (optional, for testing this module directly)
# if __name__ == "__main__":
#     # Test Fernet (as before)
#     # ...

#     # Test Password Hashing
#     # print("\n--- Password Hashing Test ---")
#     # test_plain_password = "admin_password123"
#     # if not settings.ADMIN_PASSWORD_HASH or settings.ADMIN_PASSWORD_HASH == "your_generated_bcrypt_hash_here_e.g._$2b$12$..." or settings.ADMIN_PASSWORD_HASH == "":
#     #     print("ADMIN_PASSWORD_HASH not set in .env for testing verify_admin_password. Generating one for test.")
#     #     # This is only for the __main__ block test, actual hash should be in .env
#     #     test_hashed_password = hash_admin_password(test_plain_password) 
#     #     print(f"Generated hash for '{test_plain_password}': {test_hashed_password}")
#     # else:
#     #     test_hashed_password = settings.ADMIN_PASSWORD_HASH # Use from .env if set for more realistic test
#     #     print(f"Using ADMIN_PASSWORD_HASH from .env for verification test.")

#     # if verify_admin_password(test_plain_password, test_hashed_password):
#     #     print(f"Password verification successful for '{test_plain_password}'.")
#     # else:
#     #     print(f"Password verification FAILED for '{test_plain_password}'.")
#     # if verify_admin_password("wrong_password", test_hashed_password):
#     #     print(f"Error: Password verification succeeded for 'wrong_password'.")
#     # else:
#     #     print(f"Password verification correctly failed for 'wrong_password'.")


#     # Test JWT (as before, plus admin claim)
#     # print("\n--- JWT Test ---")
#     # user_jwt_payload = {"sub": "user123"}
#     # user_access_token = create_access_token(user_jwt_payload)
#     # print(f"Generated User JWT: {user_access_token}")
#     # verified_user_payload = verify_token(user_access_token)
#     # if verified_user_payload:
#     #     print(f"Verified User JWT payload: {verified_user_payload}")
#     #     assert "is_admin" not in verified_user_payload

#     # admin_jwt_payload = {"sub": settings.ADMIN_USERNAME, "custom_admin_info": "super_user"}
#     # admin_access_token = create_access_token(admin_jwt_payload, is_admin=True)
#     # print(f"Generated Admin JWT: {admin_access_token}")
#     # verified_admin_payload = verify_token(admin_access_token)
#     # if verified_admin_payload:
#     #     print(f"Verified Admin JWT payload: {verified_admin_payload}")
#     #     assert verified_admin_payload.get("is_admin") is True
#     #     assert verified_admin_payload.get("sub") == settings.ADMIN_USERNAME
    
#     # ... (expired token tests as before)
#     # import time # For sleep
