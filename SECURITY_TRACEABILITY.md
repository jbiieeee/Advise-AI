# Security Traceability & STRIDE Guidelines: Advise-AI

This document serves as a guide for tracking security measurements and STRIDE implementations within the **Advise-AI** codebase.

## 1. STRIDE Mapping to Source Code

| Category | Security Measure | Primary File Location | Implementation Detail |
| :--- | :--- | :--- | :--- |
| **S**poofing | **Identity Authentication** | `django/core/views.py` | Validates credentials and social auth tokens. |
| | **Social Auth Isolation** | `django/config/settings.py` | `allauth` manages trustworthy social IDs. |
| **T**ampering | **CSRF Protection** | `django/config/settings.py` | `CsrfViewMiddleware` prevents CSRF attacks. |
| | **SQLi Prevention** | **PostgreSQL (ORM)** | Django ORM automatically sanitizes parameters. |
| **R**epudiation | **Activity Logging** | `django/core/models.py` | `Notification` model logs registrations & code usage. |
| | **Messaging History** | `django/core/models.py` | Persistent records of adviser interactions. |
| **I**nformation Disclosure| **Security Headers** | `django/config/settings.py` | `SECURE_SSL_REDIRECT`, `X-Frame-Options`. |
| | **Query Filtering** | `django/core/views.py` | Enforces thread visibility by current user. |
| **D**enial of Service | **Layered Rate Limiting** | `django/core/views.py` | `@ratelimit` (IP-based) + **Custom 5/6 Attempt Session Lockout** (Wait 1hr). |
| | **Brute-Force Attack Mitigation** | `django/core/views.py` | Session-aware lockout countdown starting from 3rd failure. |
| **E**levation of Privilege| **Role-Based Access Control** | `django/core/decorators.py` | Central decorators for student/adviser/admin. |

---

## 2. Security Checkpoint Locations

### Authentication & Authorization
- **Login Guard Logic**: `django/core/views.py` (lines 30-100) — Includes session-based lockout timer and attempt tracking.
- **Enrollment Security**: `django/core/views.py` — Ownership validation and lockout logic for code redemption.
- **Role Guards**: `django/core/decorators.py` (lines 44-109)
  - `@student_required`
  - `@adviser_required`
  - `@admin_required`

### Cloud & API Security
- **Gemini AI Engine**: `django/core/views.py` (line 2091)
- **Cloud Database Configuration**: `django/config/settings.py` (line 155)
- **Render Infrastructure Settings**: `django/config/settings.py` (line 208)

### Sensitive Data Protection
- **Email/ID Masking**: `django/core/views.py`
- **Internal Response Handling**: `django/core/views.py` (Help Form responses)

---

## 3. Deployment & Maintenance Guidelines

1. **New API Endpoints**: Always apply the `@ratelimit` decorator.
2. **Environment Variables**: Use `os.environ.get()` for all keys in `django/config/settings.py`.
3. **Database Guardrails**: Utilize `django/core/models.py` validators for sensitive field inputs.
4. **Timezone Uniformity**: Ensure `settings.py` is set to `Asia/Manila` to maintain audit trail consistency across PHT.
