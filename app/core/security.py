import base64
from datetime import datetime, timedelta

from cryptography.fernet import Fernet
from jose import jwt, JWTError
from jose.exceptions import ExpiredSignatureError # Specific exception for expired tokens

from app.config import Settings

settings = Settings()

# --- Fernet Encryption for Strava Tokens (from previous setup) ---
# Prepare the key for Fernet:
secret_key_bytes = settings.SECRET_KEY.encode('utf-8')
padded_key = secret_key_bytes[:32].ljust(32, b'\0') 
encryption_key = base64.urlsafe_b64encode(padded_key)
cipher_suite = Fernet(encryption_key)

def encrypt_token(token: str) -> str:
    """Encrypts a token using Fernet."""
    if not token:
        raise ValueError("Token cannot be empty for encryption")
    return cipher_suite.encrypt(token.encode()).decode()

def decrypt_token(encrypted_token: str) -> str:
    """Decrypts an encrypted token using Fernet."""
    if not encrypted_token:
        raise ValueError("Encrypted token cannot be empty for decryption")
    return cipher_suite.decrypt(encrypted_token.encode()).decode()

# --- JWT Authentication ---
ALGORITHM = "HS256"
# Consider making this configurable via settings for different environments
ACCESS_TOKEN_EXPIRE_MINUTES = 30 

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """
    Creates a JWT access token.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    # Using settings.SECRET_KEY directly for JWT, as it's a shared secret for HS256
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> dict | None:
    """
    Verifies a JWT access token.
    Returns the payload if valid, None otherwise.
    More specific error handling can be added or exceptions can be raised.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except ExpiredSignatureError:
        # Token has expired
        # Depending on policy, could raise HTTPException(status_code=401, detail="Token has expired")
        return None 
    except JWTError:
        # Any other JWT error (e.g., invalid signature, malformed token)
        # Depending on policy, could raise HTTPException(status_code=401, detail="Invalid token")
        return None

# Example usage (optional, for testing this module directly)
# if __name__ == "__main__":
#     # Test Fernet
#     if not settings.SECRET_KEY or settings.SECRET_KEY == "YOUR_VERY_SECRET_KEY_FOR_ENCRYPTION_AND_JWT":
#         print("Warning: SECRET_KEY is not set or is using the default placeholder for Fernet.")
#     else:
#         original_strava_token = "my_super_secret_strava_access_token"
#         encrypted = encrypt_token(original_strava_token)
#         decrypted = decrypt_token(encrypted)
#         assert decrypted == original_strava_token
#         print("Fernet encryption/decryption test successful.")

#     # Test JWT
#     jwt_payload_data = {"sub": "user123", "custom_claim": "some_value"}
#     access_token = create_access_token(jwt_payload_data)
#     print(f"\nGenerated JWT: {access_token}")
    
#     verified_payload = verify_token(access_token)
#     if verified_payload:
#         print(f"Verified JWT payload: {verified_payload}")
#         assert verified_payload["sub"] == "user123"
#     else:
#         print("JWT verification failed (or token expired).")

#     # Test expired token
#     # expired_token = create_access_token(jwt_payload_data, expires_delta=timedelta(seconds=-10))
#     # print(f"\nGenerated Expired JWT: {expired_token}")
#     # verified_payload_expired = verify_token(expired_token)
#     # if verified_payload_expired is None:
#     #     print("Expired JWT correctly identified as invalid/expired.")
#     # else:
#     #     print("Error: Expired JWT was not identified as invalid.")
#     # This part of direct test might be tricky if ACCESS_TOKEN_EXPIRE_MINUTES is very short
#     # and execution takes time. Better to test with a negative delta.
#     expired_token_short = create_access_token({"sub": "test_expired"}, expires_delta=timedelta(seconds=-5))
#     time.sleep(1) # Ensure it's definitely expired if system clocks are slightly off
#     if verify_token(expired_token_short) is None:
#         print("Expired JWT test: Successfully identified as expired.")
#     else:
#         print("Expired JWT test: Failed. Token should be expired.")
#
#     # Need to import time for the sleep in the test
#     # import time 
#     # print("Remember to import 'time' if running the __main__ block with sleep.")
