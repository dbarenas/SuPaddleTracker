# PaddleTrack - SUP Competition Manager

## Overview

PaddleTrack is a web application designed to manage Stand-Up Paddle (SUP) competition registrations. It integrates with Strava for user authentication, allowing users to sign up for competitions using their Strava identity. The application handles user login, race registration (including payment proof upload), and basic user session management.

## Features

*   **Strava OAuth Integration**: Secure user login and authentication via Strava.
*   **User Profile**: Fetches basic user information from Strava (name, profile picture).
*   **Competition Registration**: Allows logged-in users to register for SUP competitions.
*   **Payment Proof Upload**: Users can upload a payment proof during registration.
*   **Token Encryption**: Strava access tokens are encrypted before storage.
*   **JWT Session Management**: Uses JSON Web Tokens for managing user sessions.
*   **Async Backend**: Built with FastAPI, SQLAlchemy (async), and `aiosqlite` for asynchronous operations.
*   **Template-based UI**: Uses Jinja2 for rendering HTML pages.
*   **Testing Suite**: Includes unit and integration tests using Pytest.

## Strava Application Setup

Integration with Strava requires you to create an application on the Strava platform. This provides the necessary Client ID and Client Secret for the OAuth flow.

1.  **Navigate to Strava Apps**: Go to [https://www.strava.com/settings/api](https://www.strava.com/settings/api) and log in with your Strava account.
2.  **Create New Application**:
    *   Click on "Create & Manage Your Apps" (or similar, the interface may change).
    *   Fill in the application details:
        *   **Application Name**: Choose a name, e.g., "PaddleTrack Local Dev" or your project name.
        *   **Website**: Can be a placeholder, e.g., `http://localhost` or your actual app's future website.
        *   **Application Description**: Optional.
        *   **Authorization Callback Domain**: This is crucial.
            *   For local development, set this to `localhost`.
            *   For production, this should be your application's domain (e.g., `your-app-domain.com`).
            *   **Important**: The `STRAVA_REDIRECT_URI` in your `.env` file must match a URI under this domain and configuration (e.g., if callback is `http://localhost:8000/auth/strava/callback`, then `localhost` is the domain).
3.  **Agree to Terms**: Accept the Strava API Agreement.
4.  **Save Application**: After saving, you will find your **Client ID** and **Client Secret**. These are needed for the `.env` file.

*(Placeholder for screenshot: Strava application configuration page)*

## Local Development Setup

### Prerequisites

*   Python 3.8 or newer.
*   Git.

### 1. Clone the Repository

```bash
git clone <your-repository-url>
cd paddletrack-sup-competition-manager # Or your project directory name
```

### 2. Create and Activate Virtual Environment

It's highly recommended to use a virtual environment:

```bash
python -m venv venv
```

Activate the environment:

*   On Windows:
    ```bash
    .\venv\Scripts\activate
    ```
*   On macOS/Linux:
    ```bash
    source venv/bin/activate
    ```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables (`.env` file)

The application uses a `.env` file to manage sensitive data and configuration settings. Create a file named `.env` in the root directory of the project.

Copy the content from `.env.example` (if provided) or use the template below, filling in your actual Strava Client ID, Client Secret, and generating a strong `SECRET_KEY`.

**`.env` file template:**

```env
STRAVA_CLIENT_ID="YOUR_STRAVA_CLIENT_ID"
STRAVA_CLIENT_SECRET="YOUR_STRAVA_CLIENT_SECRET"
STRAVA_REDIRECT_URI="http://localhost:8000/auth/strava/callback" # Must match Strava app config
DATABASE_URL="sqlite+aiosqlite:///./strava_app.db" # Default SQLite, or your preferred DB URL
SECRET_KEY="YOUR_STRONG_RANDOM_SECRET_KEY_HERE" # For JWT and token encryption
```

**Important:**
*   Replace `YOUR_STRAVA_CLIENT_ID` and `YOUR_STRAVA_CLIENT_SECRET` with the values from your Strava application.
*   Ensure `STRAVA_REDIRECT_URI` exactly matches what you configure in the Strava app settings (including `http` or `https` and port if specified). For `localhost` as the domain, `http://localhost:8000/auth/strava/callback` is a common setup.
*   Generate a strong, random string for `SECRET_KEY`. You can use Python's `secrets` module for this (e.g., `python -c "import secrets; print(secrets.token_hex(32))"`).

## Running the Application Locally

Once the setup is complete:

1.  Ensure your virtual environment is activated.
2.  Run the Uvicorn server from the project root:

    ```bash
    uvicorn app.main:app --reload
    ```
3.  The application will typically be available at `http://localhost:8000`.

## Running Tests

The project includes a suite of unit and integration tests using Pytest.

1.  Ensure your virtual environment is activated and development dependencies (including test dependencies from `requirements.txt`) are installed.
2.  Run tests from the project root:

    ```bash
    pytest
    ```
3.  Tests run on a separate, temporary test database (`test.db` by default, defined in `tests/conftest.py`) and will not affect your development database.

## User Flow Walkthrough

### 1. Logging In

1.  Navigate to the application's home page (e.g., `http://localhost:8000/`) or the explicit login page (`/auth/display_login`).
    *(Placeholder for screenshot: Application login page with "Login with Strava" button)*
2.  Click the "Login with Strava" button.
3.  You will be redirected to the Strava website to authorize the application.
    *(Placeholder for screenshot: Strava authorization consent screen)*
4.  If you approve, Strava redirects you back to the application, typically to the home page, now showing your logged-in status.
    *(Placeholder for screenshot: Application home page showing logged-in status)*

### 2. Registering for a Competition (Race Subscription)

1.  Once logged in, navigate to the competition registration page (e.g., by clicking a "Register for Competition" link, usually available on the home page or in the navigation bar).
    *(Placeholder for screenshot: Competition registration form with pre-filled user details)*
2.  The registration form may pre-fill some details from your Strava profile (like your name).
3.  Fill in any remaining required details (e.g., age, competition category).
4.  Upload your payment proof file.
5.  Submit the form.
6.  You should see a success message confirming your registration.
    *(Placeholder for screenshot: Success message after registration)*

### 3. Logging Out

1.  Click the "Logout" button, typically found in the navigation bar.
    *(Placeholder for screenshot: Logout button)*
2.  You will be logged out of the application. Your session with PaddleTrack is cleared, and an attempt is made to deauthorize the application with Strava. You are usually redirected to the login page or home page.

## Project Structure

A brief overview of the main directories and files:

*   `app/`: Contains the core application logic.
    *   `core/`: Security functions (encryption, JWT), application settings.
    *   `crud/`: Functions for Create, Read, Update, Delete database operations.
    *   `db/`: Database setup (base model, session management).
    *   `dependencies.py`: FastAPI dependency functions (e.g., getting current user).
    *   `main.py`: FastAPI application instance and root endpoint.
    *   `models/`: SQLAlchemy database models and Pydantic schemas used for data validation and serialization related to database entities.
    *   `routers/`: API route definitions (e.g., auth, registration).
    *   `schemas/`: Pydantic schemas primarily for API request/response validation (e.g., token schemas).
    *   `templates/`: Jinja2 HTML templates for the user interface.
*   `static/`: Static files (CSS, JavaScript, images). Currently minimal.
    *   `payments/`: Directory where payment proofs are uploaded (ensure this is properly secured and managed in a production environment).
*   `tests/`: Unit and integration tests.
    *   `crud/`: Tests for CRUD operations.
    *   `conftest.py`: Pytest configuration and shared fixtures.
    *   Other test files for specific modules (e.g., `test_auth_flow.py`, `test_security.py`).
*   `.env.example`: An example template for the `.env` file.
*   `.gitignore`: Specifies intentionally untracked files that Git should ignore.
*   `requirements.txt`: A list of Python dependencies for the project.
*   `README.md`: This file, providing information about the project.

---

This README provides a comprehensive guide to understanding, setting up, and using the PaddleTrack application.
