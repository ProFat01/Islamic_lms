# Nur Al-Ilm — Islamic LMS Phase 1 MVP

> An Islamic Learning Management System built with Django.

---

## 🚀 Quick Start (5 Minutes)

### 1. Prerequisites
```
Python 3.10+
pip
```

### 2. Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate          # Mac/Linux
venv\Scripts\activate             # Windows
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run Migrations
```bash
python manage.py migrate
```

### 5. Load Demo Data (Optional but Recommended)
```bash
python seed_data.py
```

### 6. Start the Server
```bash
python manage.py runserver
```

### 7. Open in Browser
```
http://127.0.0.1:8000/
```

---

## 🔑 Demo Accounts

| Role    | Username          | Password    |
|---------|-------------------|-------------|
| Admin   | admin             | admin123    |
| Teacher | sheikh_ali        | teacher123  |
| Teacher | ustadha_fatima    | teacher123  |
| Student | student1          | student123  |
| Student | student2          | student123  |
| Student | student3          | student123  |

Admin panel: http://127.0.0.1:8000/admin/

---

## 📁 Project Structure

```
islamic_lms/
├── manage.py                  # Django management utility
├── requirements.txt           # Python dependencies
├── seed_data.py               # Demo data script
├── db.sqlite3                 # Database (auto-created)
│
├── islamic_lms/               # Project config package
│   ├── settings.py            # All settings
│   ├── urls.py                # Root URL config
│   └── wsgi.py                # WSGI entry point
│
├── accounts/                  # User accounts app
│   ├── models.py              # Custom User model (with roles)
│   ├── views.py               # Register, login, logout, profile
│   ├── forms.py               # Auth and profile forms
│   ├── urls.py                # /accounts/* URLs
│   ├── admin.py               # Admin registration
│   └── templates/accounts/
│       ├── login.html
│       ├── register.html
│       └── profile.html
│
├── courses/                   # Courses app
│   ├── models.py              # Course, Lesson, Enrollment
│   ├── views.py               # All course/lesson/dashboard views
│   ├── forms.py               # CourseForm, LessonForm
│   ├── urls.py                # /courses/* URLs
│   ├── admin.py               # Admin registration
│   └── templates/courses/
│       ├── course_list.html
│       ├── course_detail.html
│       ├── course_form.html
│       ├── course_manage.html
│       ├── lesson_view.html
│       ├── lesson_form.html
│       ├── lesson_confirm_delete.html
│       ├── student_dashboard.html
│       └── teacher_dashboard.html
│
├── templates/                 # Global templates
│   ├── base.html              # Master layout (navbar, footer)
│   ├── home.html              # Home page
│   └── about.html             # About page
│
├── static/
│   ├── css/main.css           # Full design system
│   └── js/main.js             # Theme toggle, nav, video embed
│
└── media/                     # User-uploaded files
    ├── thumbnails/
    └── profile_pics/
```

---

## 🎨 Features

### Student
- ✅ Register / Login / Logout
- ✅ Browse and filter published courses
- ✅ View course details and lesson list
- ✅ Enroll in courses (free)
- ✅ Watch lesson videos (YouTube/Vimeo embedded)
- ✅ Read lesson notes
- ✅ Personal dashboard with enrolled courses
- ✅ Edit profile

### Teacher
- ✅ Login with teacher account
- ✅ Teacher dashboard with course stats
- ✅ Create courses (title, description, level, duration, thumbnail)
- ✅ Edit courses
- ✅ Publish / unpublish courses
- ✅ Add, edit, delete lessons
- ✅ Upload video URL (YouTube/Vimeo auto-embedded)
- ✅ Write lesson notes

### Admin
- ✅ Full Django admin panel
- ✅ Manage users, courses, lessons, enrollments

### UI/UX
- ✅ Dark mode / Light mode toggle (persists in localStorage)
- ✅ Mobile responsive
- ✅ Islamic aesthetic (Scheherazade font, teal + gold palette)
- ✅ Auto-dismissing flash messages
- ✅ Geometric Islamic pattern backgrounds

---

## 🛡️ Security

- CSRF protection on all forms
- `@login_required` on all authenticated views
- Teacher ownership checks (teachers can only edit their own courses)
- Student enrollment gate on lesson viewing
- Django's built-in password hashing

---

## 🔧 Creating a Teacher Account

Teachers are created by the admin (they cannot self-register). To create one:

```bash
python manage.py shell
```
```python
from accounts.models import User
User.objects.create_user(
    username='new_teacher',
    password='securepassword',
    first_name='Sheikh',
    last_name='Ibrahim',
    role='teacher',
    email='ibrahim@example.com',
)
```

Or use the Django admin panel at `/admin/`.

---

## 🔮 Future Phases

| Phase | Features |
|-------|----------|
| 2     | Quiz system, progress tracking, lesson completion |
| 3     | Certificates, discussion forums |
| 4     | Email notifications, payment gateway |
| 5     | Mobile app, analytics dashboard |

---

## 🕌 About

Built for the global Muslim Ummah. Licensed for free use.

*"Seeking knowledge is an obligation upon every Muslim." — Ibn Mājah*
