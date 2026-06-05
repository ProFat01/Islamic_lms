"""
seed_data.py — Populate Islamic LMS with demo data.

Run with:
    python manage.py shell < seed_data.py
    OR
    python seed_data.py  (from project root after setting DJANGO_SETTINGS_MODULE)

Creates:
  - 1 Admin user
  - 2 Teacher users
  - 3 Student users
  - 4 Demo courses with lessons
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'islamic_lms.settings')
django.setup()

from accounts.models import User
from courses.models import Course, Lesson, Enrollment

print("🌱 Seeding Islamic LMS database...")

# ── Clear existing demo data ─────────────────────
User.objects.filter(username__in=[
    'admin', 'sheikh_ali', 'ustadha_fatima',
    'student1', 'student2', 'student3'
]).delete()

# ── Admin ────────────────────────────────────────
admin = User.objects.create_superuser(
    username='admin',
    email='admin@nuralilm.com',
    password='admin123',
    first_name='Site',
    last_name='Admin',
    role=User.Role.ADMIN,
)
print(f"  ✅ Admin: {admin.username} / admin123")

# ── Teachers ─────────────────────────────────────
teacher1 = User.objects.create_user(
    username='sheikh_ali',
    email='ali@nuralilm.com',
    password='teacher123',
    first_name='Sheikh Ali',
    last_name='Hassan',
    role=User.Role.TEACHER,
    bio='Sheikh Ali Hassan has studied Islamic sciences for over 15 years at Al-Azhar University. He specialises in Quran recitation and Tajweed.',
)

teacher2 = User.objects.create_user(
    username='ustadha_fatima',
    email='fatima@nuralilm.com',
    password='teacher123',
    first_name='Ustadha Fatima',
    last_name='Rahman',
    role=User.Role.TEACHER,
    bio='Ustadha Fatima Rahman is a certified Islamic Studies teacher with expertise in Aqeedah and Fiqh for women and families.',
)
print(f"  ✅ Teachers: sheikh_ali, ustadha_fatima / teacher123")

# ── Students ─────────────────────────────────────
for i, (uname, fname, lname) in enumerate([
    ('student1', 'Ahmed', 'Malik'),
    ('student2', 'Aisha', 'Karimi'),
    ('student3', 'Yusuf', 'Osman'),
], 1):
    User.objects.create_user(
        username=uname,
        email=f'{uname}@example.com',
        password='student123',
        first_name=fname,
        last_name=lname,
        role=User.Role.STUDENT,
    )
print(f"  ✅ Students: student1, student2, student3 / student123")

# ── Courses ───────────────────────────────────────
course1 = Course.objects.create(
    teacher=teacher1,
    title='Introduction to Tajweed',
    short_description='Learn the rules of proper Quran recitation from the foundations. Master makharij, sifaat, and basic tajweed rules.',
    full_description="""This comprehensive beginner course covers everything you need to start reciting the Quran correctly.

What You Will Learn:
• The importance of Tajweed and its ruling in Islam
• Makharij al-Huruf — the articulation points of Arabic letters
• Sifaat al-Huruf — the characteristics of letters
• The rules of Noon Sakinah and Tanween (Idghaam, Ikhfaa, Iqlaab, Izhar)
• The rules of Meem Sakinah
• Rules of Madd (elongation)
• Waqf — rules of stopping and pausing

Prerequisites:
• Basic Arabic letter recognition
• No prior Tajweed knowledge required

This course is perfect for anyone who has learned to read Arabic script and wants to improve their Quran recitation to fulfil the Sunnah of reciting as the Prophet ﷺ taught.""",
    level='beginner',
    duration='8 weeks',
    is_published=True,
)

course2 = Course.objects.create(
    teacher=teacher2,
    title='Foundations of Islamic Aqeedah',
    short_description='A structured study of Islamic belief — from Tawheed to the pillars of Iman. Based on classical texts.',
    full_description="""Islamic Aqeedah (creed) is the foundation upon which all of a Muslim's deeds are built. This course provides a thorough grounding in correct Islamic belief.

Topics Covered:
• What is Aqeedah and why does it matter?
• The Six Pillars of Iman in depth
• Tawheed: its categories and importance (Rububiyyah, Uluhiyyah, Asma wa Sifat)
• Understanding the Names and Attributes of Allah
• Belief in the Angels, Prophets, and Books
• Belief in Qadar (Divine Decree) — its levels and wisdom
• Common misconceptions and deviations
• How Aqeedah shapes our daily life and worship

Textual References:
• Al-Aqeedah al-Wasitiyyah by Ibn Taymiyyah
• Explanation of the Three Fundamental Principles
• Selected hadith from Sahih al-Bukhari and Muslim""",
    level='beginner',
    duration='10 weeks',
    is_published=True,
)

course3 = Course.objects.create(
    teacher=teacher1,
    title='Arabic for Quran Understanding',
    short_description='Learn Quranic Arabic grammar and vocabulary so you can understand the words of Allah directly.',
    full_description="""This intermediate course bridges the gap between reading Arabic and truly understanding what you read in the Quran.

Module Breakdown:

Module 1 — Arabic Nouns (Ism)
• Definite and indefinite nouns
• Gender and number
• The construct state (Idaafah)

Module 2 — Arabic Verbs (Fi'l)
• Past, present, and command forms
• The 10 verb patterns (Awzaan)
• Derived nouns from verbs

Module 3 — Sentence Structure
• Nominal sentences (Jumlah Ismiyyah)
• Verbal sentences (Jumlah Fi'liyyah)
• Conditional sentences

Module 4 — Quranic Application
• Analysis of short surahs
• Word-by-word breakdown of selected ayaat
• Building a Quranic vocabulary of 500+ words

By the end of this course you will be able to read Quran with a basic understanding of 70% of its words.""",
    level='intermediate',
    duration='16 weeks',
    is_published=True,
)

course4 = Course.objects.create(
    teacher=teacher2,
    title='Fiqh of Worship (Ibaadaat)',
    short_description='A detailed study of the rulings of Salah, Zakah, Sawm, and Hajj according to authentic evidences.',
    full_description="""This advanced course covers the Fiqh (Islamic jurisprudence) of the four main acts of worship in Islam, drawing from primary sources and classical scholarship.

Topics Covered:

Salah (Prayer):
• Conditions, pillars, and obligatory acts
• Sunnah acts and what invalidates prayer
• Prayer of the traveller, sick person, and in congregation
• Jumu'ah, Eid, and Janazah prayers

Zakah (Almsgiving):
• Who must pay Zakah and when
• Nisaab for different types of wealth
• Who can receive Zakah
• Contemporary issues in Zakah

Sawm (Fasting):
• Rulings of Ramadan fasting
• What breaks the fast and its expiation
• Voluntary fasts throughout the year

Hajj and Umrah:
• The obligations and Sunnah acts of Hajj
• Step-by-step guide to performing Hajj
• Common mistakes and how to avoid them

Methodology: Comparative Fiqh approach referencing Hanafi, Maliki, Shafi'i, and Hanbali positions where relevant.""",
    level='advanced',
    duration='20 weeks',
    is_published=True,
)

print(f"  ✅ Created 4 courses")

# ── Lessons ───────────────────────────────────────
lessons_c1 = [
    ('What is Tajweed?', 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
     'Tajweed (تجويد) literally means to do something well or to beautify. In the context of the Quran, it refers to the rules governing pronunciation during recitation.\n\nThe ruling of Tajweed:\nAccording to the majority of scholars, it is obligatory (fard \'ayn) to recite the Quran with Tajweed. Imam Ibn al-Jazari said: "Applying Tajweed is an issue of absolute necessity, for whoever does not apply Tajweed to the Quran then a sinner is he."\n\nThe Origin of Tajweed:\nTajweed was not "invented" — it is simply a codification of how the Prophet Muhammad ﷺ recited the Quran as taught to him by Jibreel (AS), who received it from Allah.'),
    ('Makharij al-Huruf — Part 1', 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
     'Makharij (مخارج) are the articulation points — the places in the mouth, throat, and nose where letters are produced.\n\nThere are 5 main articulation areas:\n1. Al-Jawf (الجوف) — The Empty Space (throat and mouth)\n2. Al-Halq (الحلق) — The Throat\n3. Al-Lisaan (اللسان) — The Tongue\n4. Al-Shafataan (الشفتان) — The Two Lips\n5. Al-Khayshoom (الخيشوم) — The Nasal Passage\n\nExercise:\nPractice stopping the flow of air to feel where each letter originates. Place a finger on your throat as you say ح and feel the breath — this is a throat letter (Halqi).'),
    ('Rules of Noon Sakinah', None,
     'Noon Sakinah (نون ساكنة) is a Noon with a sukoon (ن) or Tanween (ـً ـٍ ـٌ). When followed by other letters, one of four rules applies:\n\n1. IZHAR (إظهار) — Clear pronunciation\n   Letters: ء ه ع ح غ خ\n   Rule: Pronounce the Noon clearly without any nasalization\n   Example: مِنْ أَهْلِهَا\n\n2. IDGHAAM (إدغام) — Merging\n   Letters: ي ر م ل و ن\n   Sub-types: with ghunnah (ي ن م و) and without ghunnah (ر ل)\n   Example: مَنْ يَقُولُ → the noon merges into the yaa\n\n3. IQLAAB (إقلاب) — Conversion\n   Letter: ب only\n   Rule: The noon is converted to a meem sound with ghunnah\n   Example: أَنْبِيَاء → pronounced as أَمْبِيَاء\n\n4. IKHFAA (إخفاء) — Concealment\n   Letters: All remaining 15 letters\n   Rule: Noon is hidden with a nasal sound (ghunnah)\n   Example: مِنْ تَحْتِهَا'),
]

for i, (title, video, notes) in enumerate(lessons_c1, 1):
    Lesson.objects.create(course=course1, title=title, video_url=video, note_content=notes, order=i)

lessons_c2 = [
    ('Introduction: Why Aqeedah Matters', 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
     'Aqeedah (عقيدة) comes from the root \'aqada (عقد) meaning to tie or bind — it is what the heart is firmly tied to.\n\nWhy Study Aqeedah?\n• It is the foundation of all accepted deeds — deeds without correct belief are like a building without foundations\n• It protects a Muslim from doubts and misconceptions\n• It was the first thing the Prophets called to: "Worship Allah and avoid Taghut" (16:36)\n\nThe Prophet ﷺ spent the first 13 years in Makkah calling people primarily to Tawheed before the practical laws were revealed in Madinah — this shows the primacy of correct belief.'),
    ('Tawheed: The Oneness of Allah', None,
     'Tawheed (توحيد) means to single out Allah alone for all worship. Scholars divide it into three categories:\n\n1. Tawheed al-Rububiyyah — Oneness of Lordship\n   Affirming that Allah alone is the Creator, Sustainer, and Controller of all affairs.\n   Even the Mushrikeen of Makkah affirmed this (43:87) — it is not sufficient on its own.\n\n2. Tawheed al-Uluhiyyah — Oneness of Worship\n   Singling out Allah alone for all acts of worship: dua, sacrifice, reliance, fear, hope, love.\n   This is the Tawheed that the Prophets called to and that the Mushrikeen rejected.\n\n3. Tawheed al-Asma wa al-Sifat — Oneness of Names and Attributes\n   Affirming all the Names and Attributes Allah has affirmed for Himself without:\n   • Tahrif (distortion)\n   • Ta\'til (denial)\n   • Takyif (asking how)\n   • Tamthil (comparing to creation)'),
]

for i, (title, video, notes) in enumerate(lessons_c2, 1):
    Lesson.objects.create(course=course2, title=title, video_url=video, note_content=notes, order=i)

lessons_c3 = [
    ('Arabic Nouns: Gender and Number', None,
     'In Arabic, every noun has a gender — either masculine (مذكر - Mudhakkar) or feminine (مؤنث - Muannath).\n\nFeminine markers:\n1. Taa Marboota (ة): مَدْرَسَة (school), طَالِبَة (female student)\n2. Alif Maqsoorah (ى): كُبْرَى (greatest), بُشْرَى (glad tidings)\n3. Alif Mamdoodah (اء): صَحْرَاء (desert), سَمَاء (sky)\n4. Natural feminines: أُمّ (mother), أَرْض (earth), نَفْس (soul)\n\nNumbers in Arabic:\n• Singular (مفرد): كِتَاب — one book\n• Dual (مثنى): كِتَابَان — two books\n• Plural (جمع): كُتُب — books\n\nQuranic Application:\nIn Surah Al-Fatiha: الْحَمْدُ لِلَّهِ — Al-Hamd is a masculine noun meaning "all praise."'),
]

for i, (title, video, notes) in enumerate(lessons_c3, 1):
    Lesson.objects.create(course=course3, title=title, video_url=video, note_content=notes, order=i)

print(f"  ✅ Created lessons for all courses")

# ── Enrollments ───────────────────────────────────
students = list(User.objects.filter(role=User.Role.STUDENT))
Enrollment.objects.create(student=students[0], course=course1)
Enrollment.objects.create(student=students[0], course=course2)
Enrollment.objects.create(student=students[1], course=course1)
Enrollment.objects.create(student=students[1], course=course3)
Enrollment.objects.create(student=students[2], course=course2)
Enrollment.objects.create(student=students[2], course=course4)
print(f"  ✅ Created sample enrollments")

print()
print("=" * 50)
print("✅ Seed complete! Login credentials:")
print()
print("  ADMIN:   admin / admin123")
print("  TEACHER: sheikh_ali / teacher123")
print("  TEACHER: ustadha_fatima / teacher123")
print("  STUDENT: student1 / student123")
print("  STUDENT: student2 / student123")
print("  STUDENT: student3 / student123")
print()
print("  Run: python manage.py runserver")
print("  Visit: http://127.0.0.1:8000/")
print("=" * 50)
