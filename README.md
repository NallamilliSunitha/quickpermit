# CampusIQ

A college management system built with Django and MySQL, developed as a final year project. CampusIQ provides a unified platform for managing permissions, certificates, and meetings across a college hierarchy.

---

## Table of Contents

- [Overview](#overview)
- [Modules](#modules)
- [Tech Stack](#tech-stack)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Project](#running-the-project)
- [Role Hierarchy](#role-hierarchy)
- [Features](#features)
- [Project Structure](#project-structure)

---

## Overview

CampusIQ is a role-based college management platform that allows students, staff, HODs, deans, and principals to interact through three core modules — Permissions, Certificates, and Meetings — with a centralized notification system and AI-powered features.

---

## Modules

### 1. Permission Module
- Students and staff can submit permission/leave requests
- Role-based authority chain: Student → Proctor/Staff → HOD → Dean → Principal
- Authorities can approve, reject, forward, or reassign requests
- **Auto-escalation**: If an authority does not act within the set time, the request is automatically escalated to the next authority
- 10-minute reminder email sent before auto-escalation
- **AI Letter Generator**: Uses Groq (Llama 3) to generate professional permission letters based on the requester's role
- **AI Insight**: Authorities get an AI-powered analysis of each request with approval score, recommendation, and monthly statistics
- Bulk forward support
- Request tracking with full history

### 2. Certificate Module
- Students can apply for study certificates, bonafide certificates, transfer certificates, and marks memos
- Dean reviews and approves or forwards to Principal
- Approved certificates are generated as PDFs with QR code verification
- Certificate download with digital signature and stamp support

### 3. Meeting Module
- Staff, HODs, Deans, and Principals can create and schedule meetings
- Jitsi-powered video conferencing embedded in the platform
- Live attendance tracking via checkpoint system (10, 20, 30 minutes)
- Real-time whiteboard with multi-page support and PDF download
- Live captions using Web Speech API
- Meeting transcript saved automatically
- **AI Summary**: Auto-generates a structured meeting summary using Groq (Llama 3) when the meeting ends
- Attendance report PDF download
- Meeting history with filters

### 4. Notification Module
- Centralized notifications for all three modules
- Notifications for: request submitted, approved, rejected, forwarded, reassigned, auto-escalated, meeting invited, meeting ended, meeting cancelled, certificate approved, certificate rejected
- Mark read / Mark all read
- Direct links to the relevant request or meeting

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Django 3.0 |
| Database | MySQL |
| Frontend | Tailwind CSS, Vanilla JS |
| Video Conferencing | Jitsi iFrame API |
| AI / LLM | Groq API (Llama 3.3 70B) |
| PDF Generation | ReportLab, jsPDF |
| Background Tasks | APScheduler |
| Email | Django SMTP |
| Authentication | Django Auth |

---

## Installation

### Prerequisites
- Python 3.10
- MySQL
- pip

### Steps

```bash
# Clone the repository
git clone https://github.com/NallamilliSunitha/campusiq.git
cd campusiq

# Install dependencies
pip install django mysqlclient pillow reportlab groq apscheduler python-dotenv PyPDF2 python-docx qrcode

# Create .env file in project root
echo GROQ_API_KEY=your_groq_api_key_here > .env
```

---

## Configuration

### Database (campusiq/settings.py)
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'campusiq',
        'USER': 'your_mysql_user',
        'PASSWORD': 'your_mysql_password',
        'HOST': 'localhost',
        'PORT': '3306',
    }
}
```

### Email (campusiq/settings.py)
```python
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your_email@gmail.com'
EMAIL_HOST_PASSWORD = 'your_app_password'
DEFAULT_FROM_EMAIL = 'your_email@gmail.com'
```

### Groq API Key (.env)
```
GROQ_API_KEY=gsk_your_key_here
```

Get a free API key from: https://console.groq.com/keys

---

## Running the Project

```bash
# Apply migrations
python manage.py makemigrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Run the server
python manage.py runserver 0.0.0.0:8000
```

The auto-escalation scheduler starts automatically when the server starts.

For college network access, other users can connect via:
```
http://<your-ip>:8000
```

---

## Role Hierarchy

```
Principal
    └── Dean
          └── HOD
                ├── Staff / Proctor
                │       └── Student
                └── Student
```

### Registration URLs
- Students: `/accounts/register/?type=student`
- Employees (Staff, HOD, Dean): `/accounts/register/?type=employee`
- Principal: `/accounts/register/?type=principal`

---

## Features

### AI Features (Powered by Groq - Free)
- **Permission Letter Generator** — Generates formal letters based on requester role, reason, and dates
- **AI Insight for Authorities** — Score, recommendation (APPROVE/REJECT/REVIEW), flags, and monthly stats
- **Meeting AI Summary** — Auto-generates structured summary from meeting transcript

### Auto Escalation
- Runs every 1 minute via APScheduler
- Escalates overdue requests through the role chain automatically
- Sends 10-minute reminder email before escalation
- Sends escalation emails to both new authority and student
- Marks request as expired if it reaches top authority with no action

### Whiteboard
- Multi-page canvas drawing
- Save page and continue on new page
- Download all pages as PDF

### Attendance
- Checkpoint-based attendance (10, 20, 30 minutes)
- Live attendance view for host
- Attendance PDF report download
- Left early tracking

---

## Project Structure

```
campusiq/
├── accounts/          # Auth, login, registration, dashboard
├── permissions/       # Permission request module
│   └── scheduler.py   # Auto-escalation background job
├── certificates/      # Certificate request module
├── meetings/          # Meeting module
├── core/              # Notifications, utilities, analytics
├── templates/         # All HTML templates
├── campusiq/          # Django settings and URLs
├── .env               # API keys (not committed to git)
├── manage.py
└── README.md
```

---

## Academic Information

- **Project**: Final Year Project (4th Year, 2nd Semester)
- **Institution**: College of Engineering
- **Department**: Computer Science and Engineering
- **Platform**: CampusIQ — AI-Powered College Management System

---

## Notes

- The `.env` file is excluded from git for security — never commit API keys
- Auto-escalation works automatically as long as the server is running
- Groq API is completely free (14,400 requests/day)
- Jitsi video conferencing works on the college local network