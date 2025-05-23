# PaddleTrack - SUP Competition & Virtual Challenge Platform

## Overview

PaddleTrack is a lightweight web application for managing Paddle SUP competitions and virtual events. It supports athlete registration via Strava, event creation, timing, and detailed result classification.

## Core Features

*   **Strava OAuth Integration**: Secure user login and registration via Strava.
*   **User Dashboard**: Personalized space for athletes to view registered events, personal bests, payment proofs, and synced virtual activities.
*   **Event Management (Admin)**: Create and manage events, categories, and distances.
*   **User Event Registration**: Allows authenticated users to sign up for events.
*   **Timing Panel (Admin)**: Tools for managing race day timing, including dorsal assignment, start/finish time recording, and net time calculation.
*   **Results Display**:
    *   Public classification per event (by category and distance).
    *   Yearly and overall leaderboards for standard distances.
*   **Strava Virtual Activity Sync**: Users can manually sync their Strava activities, which are then processed and stored as virtual results.
*   **Dockerized Environment**: Configured for easy setup and deployment using Docker and Docker Compose.
*   **Async Backend**: Built with FastAPI, SQLAlchemy (async), and `aiosqlite`.
*   **Jinja2 Templates**: For server-rendered HTML.
*   **Testing Suite**: Includes unit and integration tests using Pytest.

## Strava Application Setup

To use Strava integration, you must create an application on the Strava platform:

1.  **Go to Strava Apps**: [https://www.strava.com/settings/api](https://www.strava.com/settings/api).
2.  **Create New Application**:
    *   **Application Name**: e.g., "PaddleTrack Local Dev".
    *   **Website**: e.g., `http://localhost:8000`.
    *   **Authorization Callback Domain**: For local development, this **must** be `localhost`. For production, your application's domain.
    *   **Logo**: Optional.
3.  **Save**: Note your **Client ID** and **Client Secret**. These are required for the `.env` file.
    *   The `STRAVA_REDIRECT_URI` in your `.env` file (e.g., `http://localhost:8000/auth/strava/callback`) must be under the Authorization Callback Domain you set (e.g., `localhost`).

## Running Locally with Docker

This is the recommended way to run the application for local development.

### Prerequisites

*   Docker: [Install Docker](https://docs.docker.com/get-docker/)
*   Docker Compose: Usually included with Docker Desktop. [Install Docker Compose](https://docs.docker.com/compose/install/) if needed.
*   Git (for cloning the repository).

### Setup Steps

1.  **Clone the Repository**:
    ```bash
    git clone <your-repository-url>
    cd paddle-track-project # Or your project directory name
    ```

2.  **Configure Environment Variables (`.env` file)**:
    Create a file named `.env` in the project root directory by copying the example file:
    ```bash
    cp .env.example .env
    ```
    Now, edit the `.env` file and fill in the required values:
    *   `STRAVA_CLIENT_ID`: Your Strava application's Client ID.
    *   `STRAVA_CLIENT_SECRET`: Your Strava application's Client Secret.
    *   `STRAVA_REDIRECT_URI`: Should be `http://localhost:8000/auth/strava/callback` for local setup if your Strava app is configured with `localhost` as the callback domain.
    *   `SECRET_KEY`: A strong, random string for JWTs and token encryption. You can generate one using:
        ```bash
        python -c "import secrets; print(secrets.token_hex(32))"
        ```
    *   `DATABASE_URL`: Defaults to `sqlite+aiosqlite:///strava_app.db`. The SQLite database file (`strava_app.db`) will be created in your project root on your host machine due to the volume mount in `docker-compose.yml`.

3.  **Build and Run with Docker Compose**:
    From the project root directory, run:
    ```bash
    docker-compose up --build
    ```
    *   This command builds the Docker image (if not already built or if changes were made) and starts the application service.
    *   To run in detached mode (in the background), add the `-d` flag: `docker-compose up --build -d`.
    *   The `web` service (FastAPI app) will be available at [http://localhost:8000](http://localhost:8000).

4.  **Database Initialization**:
    The application is configured to create database tables automatically on startup if they don't exist (via `init_db()` in `app/db/session.py` which calls `Base.metadata.create_all`).

5.  **Accessing the Application**:
    Open your web browser and go to [http://localhost:8000](http://localhost:8000).

6.  **Development Notes**:
    *   The `docker-compose.yml` mounts the current project directory (`.`) into `/app` inside the container. This means changes to your Python code on your host machine are immediately reflected inside the container.
    *   However, the `uvicorn` server in the Docker `CMD` is not started with `--reload` by default. For Python code changes to take effect, you'll typically need to restart the service: `docker-compose restart web` or stop and start `docker-compose up`.
    *   Alternatively, for a more active development reload, you can modify the `CMD` in `docker/Dockerfile` to include `--reload` (e.g., `CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]`) but be aware this might have performance implications or issues with some types of file changes.

7.  **Stopping the Application**:
    To stop the Docker Compose services, press `Ctrl+C` in the terminal where `docker-compose up` is running (if not in detached mode), or run:
    ```bash
    docker-compose down
    ```

## Running Tests

Tests are configured to run against a separate test database.

1.  **Ensure Docker services are running** (as some tests might interact with a live app or need DB setup similar to app). Or, tests can be run directly on the host if Python environment is set up, as they create their own in-memory/test file DB.
    For running tests within the Docker environment (if you prefer, to match the app's environment closely):
    ```bash
    docker-compose exec web pytest
    ```
    Alternatively, if you have a local Python environment set up with dependencies from `requirements.txt`:
    ```bash
    pytest
    ```

## Project Structure

*   `app/`: Core application logic (FastAPI, services, models, routers, templates).
*   `docker/`: Docker configuration.
    *   `Dockerfile`: Instructions to build the application image.
*   `static/`: Static files (CSS, JS - currently minimal).
*   `tests/`: Pytest tests.
*   `.dockerignore`: Specifies files to exclude from Docker image.
*   `.env.example`: Template for environment variable configuration.
*   `.gitignore`: Files and directories ignored by Git.
*   `docker-compose.yml`: Defines services for Docker Compose (application).
*   `requirements.txt`: Python dependencies.
*   `README.md`: This file.

---
This updated README should provide clear instructions for Docker-based local setup.
