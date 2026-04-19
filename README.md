# Advise-AI: Secure Intelligent Academic Portal (STRIDE Branch)

Welcome to the official repository for **Advise-AI**, a premium academic advising platform designed specifically for the modern institutional ecosystem. This branch (`stride`) represents the most secure iteration of the platform, implementing advanced threat modeling mitigations and AI-driven workflows.

---

## 🌟 Core Features

### 1. Intelligent Advising (Gemini 1.5 Flash)
- **AI Virtual Buddy**: Real-time academic Chatbot integrated using Google's 1.5 Flash model.
- **Context-Aware Recommendations**: Personalized guidance based on student curriculum status.

### 2. Secure Video Conferencing (Jitsi Integration)
- **Built-in Meet**: Seamless WebRTC conferencing directly in the browser.
- **Dynamic Security**: Automated room generation and real-time signalling for secure advising sessions.

### 3. Professional Academic Workflow
- **Curriculum Tracking**: Interactive progress boards for students and evaluation tools for advisers.
- **Enrollment Code System**: Single-use, cryptographically secure codes for streamlined enrollment overrides.

### 4. Advanced Communications
- **Real-Time Notification Engine**: Instant AJAX-based alerts for messages, calls, and session updates.
- **Automated Call Logs**: Persistent chat integration ensures meeting links are never lost.

---

## 🛡️ Security Architecture (STRIDE Implementation)

This project was built using the **STRIDE** methodology to ensure high-grade data protection:
- **Spoofing**: Defeated via Google/GitHub OAuth 2.0 and Adviser-specific OTP verification.
- **Tampering**: Guarded by Django's native CSRF protection and ORM parameterization.
- **Repudiation**: Enforced through a centralized immutable Activity Log (Audit Trail).
- **Information Disclosure**: Protected by Role-Based Access Control (RBAC) and SSL/TLS encryption.
- **Denial of Service**: Mitigated through cache-backed Rate Limiting (`django-ratelimit`).
- **Elevation of Privilege**: Secured via strict server-side middleware and permission checkpoints.

---

## 🚀 Local Installation & Setup

Follow these steps to deploy Advise-AI on your local workstation for development or evaluation.

### 1. Prerequisites
- **Python 3.12+**
- **Git**
- **Google Gemini API Key** (Get it from [Google AI Studio](https://aistudio.google.com/))
- **Google/GitHub OAuth Credentials** (Optional for local, required for Social Login features)

### 2. Clone the Repository
```bash
git clone https://github.com/jbiieeee/Advise-AI.git
cd Advise-AI
git checkout stride
```

### 3. Set Up Virtual Environment
```bash
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

### 4. Install Dependencies
```bash
cd django
pip install -r requirements.txt
```

### 5. Environment Configuration
Create a `.env` file inside the `django/` directory with the following variables:
```env
SECRET_KEY='your-secure-django-secret-key'
DEBUG=True
GEMINI_API_KEY='your-google-gemini-api-key'
# Optional: SMTP for OTP
EMAIL_HOST_USER='your-gmail@gmail.com'
EMAIL_HOST_PASSWORD='your-app-password'
# Optional: OAuth
SOCIAL_AUTH_GOOGLE_CLIENT_ID='xxx'
SOCIAL_AUTH_GOOGLE_SECRET='xxx'
```

### 6. Database Migrations & Superuser
```bash
python manage.py makemigrations
python manage.py migrate
# Create your administrator account
python manage.py createsuperuser
```

### 7. Launch the Platform
```bash
python manage.py runserver
```
Access the application at: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)

---

## 🛠️ Technical Stack
- **Backend**: Python 3.12, Django 6.0.1
- **UI/UX**: HTML5, Vanilla CSS3, Modern JavaScript (No heavy frameworks)
- **AI Engine**: Google Generative AI (Gemini 1.5 Flash)
- **Security**: Django-Allauth (OAuth), Django-Ratelimit, Cryptography
- **Database**: PostgreSQL (Production) / SQLite (Local)
- **Infrastructure**: Render Cloud, WhiteNoise Static Asset Management

---
