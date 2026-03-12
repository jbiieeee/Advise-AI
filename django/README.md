# Advise AI - Academic Advising System

This is a Django-based web application for an Academic Advising System.

## Prerequisites

Before you begin, ensure you have the following installed:
*   [Python 3.8+](https://www.python.org/downloads/)
*   [Node.js](https://nodejs.org/) (required for compiling Tailwind CSS)

## Installation & Setup

1.  **Clone the repository:**
    ```bash
    git clone <your-repository-url>
    cd <repository-directory>/django
    ```

2.  **Set up the Python Virtual Environment:**
    ```bash
    python -m venv venv
    ```
    *   **Windows:** `venv\Scripts\activate`
    *   **macOS/Linux:** `source venv/bin/activate`

3.  **Install Python Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Install Node Modules (for Tailwind CSS):**
    ```bash
    npm install
    ```

5.  **Apply Database Migrations:**
    ```bash
    python manage.py migrate
    ```

## Running the Application

To run the application locally, you need to start two processes in separate terminal windows:

### Terminal 1: Tailwind CSS Compiler
This process will watch your templates and automatically recompile the CSS when you make changes.
```bash
# Ensure you are in the django directory
npm run tailwind:watch
```

### Terminal 2: Django Development Server
This process runs the actual Python web server.
```bash
# Ensure your virtual environment is active
python manage.py runserver
```

The application will now be accessible at `http://127.0.0.1:8000/`.

## Tailwind CSS Notes

If you are just deploying to production or don't need the watch command, you can build the CSS once using:

```bash
npm run tailwind:build
```
