# 🚀 QuickPermit (CampusIQ)

A college management system built with Django and MySQL, developed as a final year project. QuickPermit (CampusIQ) provides a unified platform for managing permissions, certificates, and meetings across a college hierarchy.

---

## 🌐 Live Demo

👉 https://sunitha11.pythonanywhere.com

---

## 📌 Table of Contents

* [Overview](#overview)
* [Modules](#modules)
* [Tech Stack](#tech-stack)
* [Installation](#installation)
* [Configuration](#configuration)
* [Running the Project](#running-the-project)
* [Role Hierarchy](#role-hierarchy)
* [Features](#features)
* [Project Structure](#project-structure)
* [Author](#author)

---

## 📖 Overview

QuickPermit (CampusIQ) is a role-based college management platform that allows students, staff, HODs, deans, and principals to interact through three core modules — Permissions, Certificates, and Meetings — with a centralized notification system and AI-powered features.

---

## 🧩 Modules

### 1. Permission Module

* Students and staff can submit permission/leave requests
* Role-based authority chain: Student → Proctor/Staff → HOD → Dean → Principal
* Authorities can approve, reject, forward, or reassign requests
* **Auto-escalation** for pending requests
* 10-minute reminder email before escalation
* **AI Letter Generator** using Groq (Llama 3)
* **AI Insight** with approval score and recommendation
* Bulk forward support
* Full request tracking

---

### 2. Certificate Module

* Apply for study, bonafide, transfer certificates, and marks memos
* Dean approval workflow
* PDF generation with QR verification
* Digital signature and stamp support

---

### 3. Meeting Module

* Schedule and manage meetings
* Jitsi-based video conferencing
* Attendance tracking (10, 20, 30 min checkpoints)
* Whiteboard with PDF export
* Live captions
* Transcript saving
* **AI Meeting Summary (Groq - Llama 3)**
* Attendance report download

---

### 4. Notification Module

* Centralized notifications
* Real-time alerts for all modules
* Mark read / Mark all read
* Direct navigation links

---

## 🛠️ Tech Stack

| Layer              | Technology               |
| ------------------ | ------------------------ |
| Backend            | Django 3.0               |
| Database           | MySQL                    |
| Frontend           | Tailwind CSS, JavaScript |
| Video Conferencing | Jitsi API                |
| AI / LLM           | Groq API (Llama 3.3 70B) |
| PDF                | ReportLab, jsPDF         |
| Scheduler          | APScheduler              |
| Email              | Django SMTP              |

---

## ⚙️ Installation

### Prerequisites

* Python 3.10
* MySQL
* pip

### Steps

```bash
# Clone the repository
git clone https://github.com/NallamilliSunitha/quickpermit.git
cd quickpermit

# Install dependencies
pip install django mysqlclient pillow reportlab groq apscheduler python-dotenv PyPDF2 python-docx qrcode

# Create .env file
echo GROQ_API_KEY=your_groq_api_key_here > .env
```

---

## 🔧 Configuration

### Database (settings.py)

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

### Email Configuration

```python
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your_email@gmail.com'
EMAIL_HOST_PASSWORD = 'your_app_password'
```

### Environment Variables (.env)

```
SECRET_KEY=your_secret_key
GROQ_API_KEY=your_api_key
EMAIL_HOST_USER=your_email
EMAIL_HOST_PASSWORD=your_password
```

---

## ▶️ Running the Project

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

---

## 🏫 Role Hierarchy

```
Principal
    └── Dean
          └── HOD
                ├── Staff / Proctor
                │       └── Student
                └── Student
```

---

## ✨ Features

### 🤖 AI Features

* Permission Letter Generator
* AI Approval Insights
* Meeting Summary Generator

### ⏱️ Auto Escalation

* Runs every minute
* Escalates pending requests
* Sends email reminders

### 🎨 Whiteboard

* Multi-page drawing
* PDF export

### 📊 Attendance

* Time-based checkpoints
* Attendance reports

---

## 📂 Project Structure

```
campusiq/
├── accounts/
├── permissions/
├── certificates/
├── meetings/
├── core/
├── templates/
├── campusiq/
├── manage.py
├── .env
└── README.md
```

---

## 👤 Author

**Nallamilli Sunitha**
Final Year CSE Student
Project: QuickPermit (CampusIQ)

---

## 📌 Notes

* `.env` file is not pushed to GitHub for security
* Auto-escalation runs automatically
* Groq API free tier supported
* Works on college/local network

---

## 📜 License

This project is developed for academic purposes.
