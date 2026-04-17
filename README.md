# Advise-AI: Academic Advising & Enrollment Management System

Advise-AI is a comprehensive web-based platform designed to streamline academic advising and enrollment workflows. It features an AI-powered assistant (Gemini), a robust messaging system, and a secure role-based management dashboard for students, advisers, and administrators.

---

## 🚀 Quick Start: Run from GitHub

Follow these steps to get the system running on your local machine.

### 1. Prerequisites
Ensure you have the following installed:
- [Python 3.14+](https://www.python.org/downloads/)
- [Node.js & npm](https://nodejs.org/) (Required for Tailwind CSS)
- [Git](https://git-scm.com/)

### 2. Clone the Repository
```powershell
git clone https://github.com/your-username/WebSys2-Advise-AI.git
cd WebSys2-Advise-AI
```

### 3. Setup Backend (Django)
Navigate to the `django` folder and set up your virtual environment:
```powershell
cd django
python -m venv venv
# Activate on Windows:
.\venv\Scripts\activate
# Activate on macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 4. Setup Frontend (Tailwind CSS)
Navigate to the `frontend` folder to install styling dependencies:
```powershell
cd ../frontend
npm install
```

### 5. Environment Configuration
Create an environment variable or a `.env` file in the `django` directory with your **Gemini API Key**:
```env
GEMINI_API_KEY=your_actual_api_key_here
SECRET_KEY=your_django_secret_key
```

### 6. Initialize Database
Go back to the `django` directory and apply migrations:
```powershell
cd ../django
python manage.py migrate
```

### 7. Run the System
You need to run both the CSS compiler and the Django server.

**Terminal A (Tailwind Watch):**
```powershell
cd ../frontend
npm run tailwind:watch
```

**Terminal B (Django Server):**
```powershell
cd ../django
python manage.py runserver
```
Visit `http://127.0.0.1:8000` in your browser.

---

## 🛡️ Security & Architecture

This project implements the **STRIDE** threat modeling framework and **DREAD** risk assessment.

- **Role-Based Access Control (RBAC)**: Enforced via custom decorators (`@student_required`, `@adviser_required`).
- **Rate-Limiting**: Secured using `django-ratelimit` to protect against brute-force attacks.
- **AI Integration**: Powered by **Google Gemini 1.5 Flash** for real-time academic guidance.

For a deep dive into security, see:
- [Threat Modeling Report](Threat_Modeling_Report.md)
- [Security Traceability Matrix](SECURITY_TRACEABILITY.md)
- [Technical System Details](SYSTEM_DETAILS.md)

---

## 👥 Group Members
Chico, Marvin Joshua (UI/UX)
Cruz, Elbert Andriel D. (UI/UX/Documentation)
Leones, Leo Jermin Ace  P. (Documentation)
Longay, James Bryan N. (Lead Dev./Documentation)
Magbanua, Matt Christian S. (Asst. Dev./STRIDE)


---
*Created for WebSys2 - Final Project