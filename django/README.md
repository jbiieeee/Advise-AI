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

---

## Recent Security & Architecture Changes

### 1. Application-Level Rate Limiting
To protect against brute-force attacks and API abuse, we have implemented rate limiting using `django-ratelimit`.

**Rate-Limited Endpoints:**
- **Login**: 5 attempts per 5 minutes per IP.
- **Registration**: 3 attempts per hour per IP.
- **Messaging (API)**: 10 messages per minute per user.
- **AI Chatbot**: 5 requests per minute per user.

### 2. Role-Based Access Control (RBAC) Decorators
The application has transitioned from inconsistent `if-else` logic inside views to centralized security decorators in `core/decorators.py`.

- `@student_required`: Restricts access to student tools.
- `@adviser_required`: Restricts access to advising dashboards.
- `@admin_required`: Restricts access to administrative panels.
- **Support Bypass**: Administrators (superusers) are granted bypass access to Student and Adviser views to provide tech support.

### 3. Cache & Production Deployment on Render
Rate limiting requires a cache backend. The system is currently configured to use **Local Memory Cache (LocMemCache)**.

**Configuring for Render:**
On Render, use a single-worker deployment by default. If you scale to multiple workers or instances, you **must** upgrade to a shared cache (Redis) to ensure rate limits are synchronized.

**Upgrade Steps for Redis on Render:**
1. Provision a **Render Redis** instance.
2. Add the `REDIS_URL` to your Render Environment Variables.
3. Update `django/config/settings.py` to use the Redis backend:
   ```python
   CACHES = {
       'default': {
           'BACKEND': 'django.core.cache.backends.redis.RedisCache',
           'LOCATION': os.environ.get('REDIS_URL'),
       }
   }
   ```
4. Remove `django_ratelimit.W001` and `django_ratelimit.E003` from `SILENCED_SYSTEM_CHECKS` in `settings.py`.
