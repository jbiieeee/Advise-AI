# Advise-AI: System Architecture & Technical Details

This document provides a deep dive into the technical implementation of the Advise-AI platform.

---

## 1. Technical Stack (The "How It's Built")

### Backend Architecture
- **Framework**: **Django (v6.0.1)**. Chosen for its "batteries-included" security and rapid development features.
- **Logic**: Uses **Django Signals** (`django/core/signals.py`) for decoupled event handling and `LastActivityMiddleware` for real-time user tracking.
- **Authentication**: **Django All-auth**. Supports standard credential login and **Social OAuth2 (Google, GitHub only)**.
- **Environment Management**: Securely configured using `os.environ` for production API keys and database credentials.

### Artificial Intelligence Integration
- **Engine**: **Google Gemini 1.5 Flash**.
- **SDK**: `google-generativeai`.
- **Knowledge Awareness**: Data-aware of BSIT/BSCS curricula. Handles 24/7 inquiries, enrollment rules, and provides "Must-Take" subject recommendations via a custom server-side process.

### Frontend & User Interface
- **Styling**: Semantic HTML5, CSS3 (**Vanilla + TailwindCSS**).
- **Interactivity**: **Fetch API and AJAX** for real-time messaging and dynamic notifications without page reloads.

### Database & Deployment
- **Database**: **Cloud PostgreSQL** (Managed via Render).
- **Static Asset Management**: **WhiteNoise** for serving compressed static files.
- **PaaS Platform**: **Render Cloud**.

---

## 2. Core System Architectures

### Enrollment & Advising Engine
The system operates on a **Three-Tier Approval System**:
1. **Adviser Stage**: Generates unique 12-character Enrollment Codes for specific approved subjects.
2. **Student Stage**: Codes are delivered via internal messages; the student redeems the code in their dashboard.
3. **Admin Stage**: Final oversight of enrollment status and database finalization.

### Messaging System
- **Logic**: Split-screen interface with a 30% sidebar (contact list) and a 70% chat interface.
- **Access Control**: Role-based decorators in `django/core/decorators.py` (`@student_required`, `@adviser_required`) ensure that staff-only channels are completely inaccessible to students.
- **Real-time**: Leverages AJAX polling for a seamless communication experience.

### Help & Reporting Loop
- Students submit structured forms which are processed by Admins.
- Automated triggers notify Admins via the `Notification` system (`django/core/models.py`) upon new submissions.

---

## 3. Security Implementation (STRIDE)

- **S (Spoofing)**: Mitigated via Django’s session management and `allauth` OAuth validation.
- **T (Tampering)**: Managed through backend logic validation and Django’s built-in CSRF protection.
- **R (Repudiation)**: Tracked through the `Notification` and `Message` models which maintain an immutable audit trail of system events.
- **I (Information Disclosure)**: Secured via enforced HTTPS/TLS and strict environment variable isolation for secrets.
- **D (Denial of Service)**: **Implemented** via `@ratelimit` decorators on all sensitive login, registration, and AI endpoints.
- **E (Elevation of Privilege)**: Strictly enforced via centralized Role-Based Access Control (RBAC) decorators.
