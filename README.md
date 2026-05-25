# CareConnect - Parent Health Management System

CareConnect is a premium, multi-role web application built beautifully to help families monitor, coordinate, and understand the health metrics of their elderly parents securely and efficiently. Designed with an elegant, "Apple-inspired" dark mode aesthetic, it leverages modern glassmorphism UI, real-time interactive elements, robust **local AI integrations** (Ollama), **Supabase PostgreSQL persistence**, and full **role-based authentication**.

**Modular Flask architecture** separates concerns: core app (`app.py`), config (`.env`/`config.py`), data layer (`data_store.py`), AI service (`ai_service.py`).

---

## 🌟 Key Features

### Multi-Portal Role-Based Dashboards
Seamless routing with auth/signup:
- **Children Portal**: Monitor vitals, book appointments, family chat, AI reports, settings.
- **Patient Dashboard**: Log symptoms/medicines, reminders, chat, telehealth waiting.
- **Doctor Portal**: Patient registry, schedule, consultations, video calls, notes.
- **Hospital Admin**: Manage doctors/appointments/reports/analytics.
- **Diagnostic Partner**: Upload lab results (auto AI analysis).

### 🚨 Live Geolocation SOS + Emergency Protocols
- Full-screen pulsating red alert + Web Audio API siren.
- WhatsApp live location sharing via browser geolocation.
- Cross-role notifications (children/doctor/admin).

### 🤖 Fully Local AI Report Analysis (Ollama)
Processes **images** (X-ray/MRI via vision models: llava/bakllava) & **PDF/text** reports:
- `ai_service.py` extracts text (PyPDF2), sends to local Ollama (vision/text fallback).
- Plain-English summaries stored in DB, notified to roles.
- Supports 10+ file types, memory error handling.

### 🎥 WebRTC Video Consultations
Native `getUserMedia()` for secure camera/mic toggles, room timers.

### 📱 Full Real-Time APIs + Notifications
REST endpoints for: chat/messages, appointments/booking, medicine logs, SOS alerts, patients/doctors registry, vitals, reports, auth (signup/login).

Push notifications across roles for appointments, messages, SOS, reports, etc.

### 🔒 Secure Multi-Role Auth
Flask-Login/WTF + password hashing; role-specific sessions (patient/children/doctor/etc.).

---

## 📁 Project Structure
```
e:/New folder (2)/
├── app.py              # Flask core routes + APIs
├── config.py           # Env-based config (Supabase, secrets)
├── data_store.py       # PostgreSQL/InMemoryStore (auth, patients, appts, etc.)
├── database.py         # SQLAlchemy models + PostgreSQL setup
├── ai_service.py       # Ollama medical image/PDF analysis
├── requirements.txt    # Python deps
├── README.md           # This file
├── .env                # Secrets (SUPABASE_URL, SECRET_KEY)
├── database/           # DB helpers
├── db/                 # DB setup
├── static/             # CSS/JS/Icons (Phosphor, Chart.js)
├── templates/          # HTML dashboards/portals
└── CareConnect_PRD.pdf # Product specs
```

---

## 🛠 Tech Stack

**Backend**: Python 3.x, Flask, Flask-Login/SQLAlchemy/WTF/Talisman  
**Database**: PostgreSQL (Supabase) with SQLAlchemy ORM / InMemory fallback  
**AI/ML**: Ollama (local: llama3/llava-med/Mistral/phi3) + PyPDF2/base64  
**Frontend**: HTML5, Vanilla JS, Custom CSS (glassmorphism/dark mode)  
**Security**: python-dotenv, cryptography, Werkzeug hashing  
**Prod**: gunicorn, whitenoise  
**APIs**: REST/JSON, WebRTC, Web Audio/Geolocation

---

## 🚀 Setup & Installation

### Prerequisites
- **Python 3.8+**
- **Supabase Account** (free tier available at https://supabase.com)
- **PostgreSQL** (Supabase hosts this for you)
- **Ollama** (local AI): [Install](https://ollama.com/) & run `ollama serve`
  - Pull models: `ollama pull llama3` (text), `ollama pull llava` (vision)

### 1. Clone & Navigate
```bash
cd "e:/New folder (2)"
```

### 2. Virtual Environment (Recommended)
```bash
python -m venv venv
venv\Scripts\activate  # Windows
pip install --upgrade pip
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure `.env` with Supabase
Copy `.env.example` or create `.env`:
```env
SECRET_KEY=your-super-secret-key-here-32chars-min
SUPABASE_URL=postgresql://postgres:your_password@your-project.supabase.co:5432/postgres
DATABASE_URL=postgresql://postgres:your_password@your-project.supabase.co:5432/postgres
OLLAMA_BASE_URL=http://127.0.0.1:11434  # Default
DEBUG=True  # Set False for prod
```

**Getting Supabase Credentials:**
1. Sign up at https://supabase.com
2. Create a new project
3. Go to Project Settings → Database → Connection String
4. Copy the PostgreSQL connection string
5. Replace `[YOUR-PASSWORD]` with your database password
6. Paste into `.env` as `SUPABASE_URL` and `DATABASE_URL`

### 5. Run Server
```bash
python app.py
```
Visit: [http://127.0.0.1:5000](http://127.0.0.1:5000)

**Production**: `gunicorn -w 4 -b 0.0.0.0:5000 app:app`

*(Enable browser perms for camera/geolocation on localhost)*

---

## 📋 API Endpoints Overview
- `/api/auth/signup` & `/api/auth/login` (role-based)
- `/api/chat/*` (messages/notifications)
- `/api/appointments/*` (book/list)
- `/api/reports/*` & `/api/analyze-report` (AI upload)
- `/api/patients/*` & `/api/doctors/*` (registry/vitals)
- `/api/sos/*` (emergency)
- Full list in `app.py`.

---

## 🧪 Local Development
- **Ollama Vision**: `ollama pull llava:7b` or `llava-med` for medical images.
- **Supabase**: Use free tier for development (free PostgreSQL database).
- **Fallback**: App runs without Supabase (in-memory + errors).
- **Seeds**: Auto-populates demo patients/doctors/appointments/messages.
- **Logs**: `logging.INFO` for API calls/errors.

## 🚀 Deployment
1. Set `DEBUG=False`, strong `SECRET_KEY`.
2. Deploy Supabase (already hosted).
3. `gunicorn` + nginx/Cloudflare.
4. Static files via whitenoise.
5. Ollama on same host (Docker compose possible).

## ❗ Troubleshooting
- **Ollama errors**: Check `ollama serve`, ports, models pulled.
- **Supabase**: Verify connection string in `.env`; app falls back to memory.
- **Files**: AI supports JPG/PNG/PDF/TXT/etc.; see `ai_service.py`.
- **Auth**: Role-specific logins (e.g., children@demo.com / pass123).
- **Database**: Tables auto-created on first run via SQLAlchemy.

---

*Designed dynamically. Built reliably. Secured locally. Powered by local AI. Persisted in PostgreSQL.*

**Contributing**: Fork/PR welcome. Review `CareConnect_PRD.pdf` for specs.

---

## Migration from MongoDB
If you're migrating from MongoDB:
1. Update `.env` with Supabase PostgreSQL URL (see section 4 above)
2. Install new dependencies: `pip install -r requirements.txt`
3. Run the app - tables will auto-create via SQLAlchemy ORM
4. Demo data will auto-seed on first run
5. Existing functionality remains identical (same API, same data structure)



