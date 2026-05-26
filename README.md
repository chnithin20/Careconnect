# CareConnect — Family Health Management Platform

> A full-stack, multi-role health management web app that helps families monitor, coordinate, and understand the health of their elderly parents — powered by local AI, real-time messaging, JWT authentication, and a Supabase PostgreSQL backend.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Database Schema](#database-schema)
- [API Reference](#api-reference)
- [Setup & Installation](#setup--installation)
- [Environment Variables](#environment-variables)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)

---

## Overview

CareConnect connects five types of users — elderly patients, their children/family managers, doctors, hospital admins, and diagnostic labs — into a single coordinated platform. Each role gets a dedicated portal with relevant tools, and all data flows through a shared Supabase PostgreSQL database with Row Level Security.

The UI is built with a dark glassmorphism aesthetic, fully responsive via Tailwind CSS, and supports real-time updates through Socket.IO WebSockets with a 3-second polling fallback.

---

## Features

### Authentication & Security

- **JWT-based authentication** — every login issues a signed access token (24h) and a refresh token (30d)
- **Token stored in database** — each JWT has a unique `jti` claim saved to the `user_sessions` table; tokens can be revoked server-side instantly
- **Token rotation** — refresh tokens are single-use; a new pair is issued on every refresh
- **HttpOnly cookie** — access token is set as a secure HttpOnly cookie for browser sessions, preventing JS access
- **Password hashing** — SHA-256 hashing before storage; plaintext passwords never touch the database
- **Role-based access** — five distinct roles with separate dashboards, routes, and session scopes
- **Force logout** — `SessionRepository.revoke_all_for_user()` kills all active sessions for a user across all devices

Auth endpoints:

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/signup` | Create account, returns JWT pair |
| POST | `/api/auth/login` | Login, returns JWT pair |
| POST | `/api/auth/refresh` | Rotate refresh token, get new access token |
| POST | `/api/auth/logout` | Revoke token in DB, clear cookie |
| GET  | `/api/auth/me` | Get current user profile (requires JWT) |

---

### Role-Based Portals

#### Children Portal (`/dashboard/children`)
The primary family manager interface:
- Live vitals display (heart rate, blood pressure, blood sugar, BMI)
- Connected doctor card from most recent confirmed appointment
- Real-time medicine log feed — updates when the parent logs a medication
- Doctor's consultation notes feed
- Vitals trending chart (Chart.js line graph)
- Quick-access buttons: Book Appointment, Trigger SOS

Sub-pages:
- **Bookings** (`/children/appointments`) — book appointments for the parent, select doctor and department
- **AI Reports** (`/children/reports`) — upload medical files for AI analysis, view history
- **Family Chat** (`/children/chat`) — real-time messaging with the parent via Socket.IO
- **Family Circle** (`/children/family`) — manage connected family members, invite via link, change roles
- **Settings** (`/children/settings`) — account and notification preferences

#### Patient Portal (`/dashboard/patient`)
Designed for elderly users with a simple, large-text interface:
- Vitals overview (4 cards)
- Today's medications with one-tap "Took It" logging — notifies children instantly
- Upcoming appointments list
- Doctor's notes feed
- Chat with children (`/patient/chat`)
- Medication reminders (`/patient/reminders`)

#### Doctor Portal (`/dashboard/doctor`)
- Full patient registry table with ID, name, age, blood group, conditions
- Click any patient to open their full profile: vitals, appointments, consultation notes, reports
- Today's schedule (`/doctor/schedule`)
- Consultation notes editor (`/doctor/consultations`) — notes are visible to patients and children in real-time
- Latest appointment updates feed

#### Hospital Admin Portal (`/dashboard/hospital-admin`)
- Hospital stats overview: active doctors, bookings today, revenue target
- Doctor management table with on-duty/off-duty status
- Appointments management (`/admin/appointments`)
- Reports overview (`/admin/reports`)
- Doctor registry management (`/admin/doctors`)

#### Diagnostic Center Portal (`/dashboard/diagnostic`)
- Pending test queue with urgency badges
- Upload results interface (`/diagnostic/upload`) — files are analyzed by AI automatically
- Upload history (`/diagnostic/history`)

---

### Real-Time Chat

- **Socket.IO WebSocket** connection for instant message delivery — no delay
- **3-second polling fallback** for environments where WebSockets are unavailable
- `socketio.emit('new_message', msg, broadcast=True)` fires immediately after every save
- `since` parameter on `/api/chat/messages` — only fetches new messages after the last known timestamp, not the full history every poll
- **XSS protection** — all message content and sender names are escaped through `escapeHtml()` before DOM insertion
- Separate chat views for patient side and children side, both showing the same shared message thread
- Connection status indicator (Live / Offline) with pulse animation

---

### AI Report Analysis

- Upload medical files directly from the Children or Diagnostic portal
- Supported formats: JPG, PNG, WEBP, BMP, GIF, TIFF, PDF, TXT, CSV, MD
- Files are sent to a locally running **Ollama** instance for analysis
- AI returns a plain-English summary flagging abnormal values, trends, and recommendations
- Summaries are stored in the `reports` table and visible to all connected roles
- Configurable model via `OLLAMA_MODEL` env var (default: `llama3`; use `llava` for image/vision analysis)

---

### Family Circle

- Displays the logged-in user's name and initials dynamically from session data
- Loads connected family members from the patients API with real names, roles, and last-seen times
- Invite via Link — copies a shareable URL to clipboard
- Send Invite form with email input and feedback
- Change Role dialog for each member

---

### SOS Emergency System

- Floating SOS button on every dashboard page
- Triggers `SOSAlertRepository.create_alert()` — saves to `sos_alerts` table
- Database trigger (`notify_sos_alert`) automatically creates a notification for the doctor role
- Flash message confirms alert was sent to family and hospitals

---

### Notifications System

- Real-time notification bell in the top-right corner of every dashboard
- Polls `/api/notifications?role=<role>` every 3 seconds
- Bell shakes with animation when new notifications arrive
- Badge counter shows unread count (capped at 9+)
- Notifications are created automatically by database triggers:
  - New appointment booked → notifies doctor
  - Appointment status changed → notifies patient
  - SOS alert triggered → notifies doctor
- Notification panel shows title, body, timestamp, and optional action link
- Mark all read / Clear all controls

---

### Responsive UI (Tailwind CSS + Custom CSS)

- **Tailwind CSS** loaded via CDN with custom theme tokens matching the design system
- **Mobile-first breakpoints**: full layout at 1024px+, tablet at 640–1024px, mobile below 640px
- **Off-canvas sidebar** on mobile — slides in from the left with a hamburger button, overlay backdrop
- Sidebar auto-closes when a nav link is tapped on mobile
- Hero section text scales with `clamp()` for fluid typography
- Vitals grid collapses from 4-col → 2-col → 1-col across breakpoints
- Tables wrapped in horizontal scroll containers on small screens
- Buttons stack vertically on mobile, inline on desktop
- Glassmorphism cards, gradients, and animations preserved across all screen sizes
- Dark mode only — consistent `#000c24` background with CSS custom properties

---

### Database — Supabase PostgreSQL

All data persists to Supabase. No local database required.

Tables:

| Table | Purpose |
|-------|---------|
| `users` | All user accounts across all roles |
| `user_sessions` | JWT session store — jti, expiry, revoked flag |
| `patients` | Patient registry with vitals, conditions, allergies |
| `doctors` | Doctor registry with specialty and availability |
| `appointments` | Bookings with status, date, time, department |
| `messages` | Chat messages with sender, text, unix timestamp |
| `notifications` | Cross-role push notifications |
| `consultation_notes` | Doctor notes linked to patient and doctor |
| `medicine_log` | Patient medication intake records |
| `sos_alerts` | Emergency alert records |
| `reports` | AI-analyzed medical report records |
| `audit_logs` | Automatic audit trail for all data changes |

Database features:
- **Row Level Security (RLS)** enabled on all tables
- **Auto-update triggers** — `updated_at` maintained automatically
- **Audit logging trigger** — every INSERT/UPDATE/DELETE logged to `audit_logs`
- **Appointment notification trigger** — auto-creates notifications on booking/status change
- **SOS notification trigger** — auto-notifies doctor on emergency alert
- **Validation triggers** — patient age/blood group/gender, appointment status/date format, user role

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, Flask 3.1, Flask-SocketIO 5.5 |
| Database | Supabase (PostgreSQL), supabase-py 2.15 |
| Authentication | PyJWT 2.11 — HS256 signed tokens, DB-backed sessions |
| AI | Ollama (local) — llama3 (text), llava (vision) |
| Real-time | Socket.IO WebSockets + HTTP polling fallback |
| Frontend | Jinja2 templates, Tailwind CSS (CDN), Vanilla JS |
| Charts | Chart.js 4.4 |
| Icons | Phosphor Icons |
| Fonts | Inter, Outfit (Google Fonts) |
| File parsing | pypdf 5.4, python-docx 1.1, Pillow 11.2 |
| Config | python-dotenv 1.1 |
| Deployment | Vercel (HTTP), Railway/Render (recommended for WebSockets) |

---

## Project Structure

```
CareConnect/
│
├── app.py                    # Flask app — all routes, JWT helpers, Socket.IO handlers
├── supabase_db.py            # Data layer — repository classes for every table
├── ai_service.py             # Ollama AI integration for medical report analysis
├── config.py                 # Config class — reads all env vars
├── requirements.txt          # Pinned Python dependencies
├── vercel.json               # Vercel serverless deployment config
├── supabase_schema.sql       # Full DB schema, indexes, triggers, RLS policies
├── verify_supabase_connections.py  # Dev utility to test DB connectivity
│
├── .env                      # 🔒 Local secrets — never commit
├── .env.example              # Template showing all required env vars
├── .gitignore
├── README.md
│
├── static/
│   ├── css/
│   │   └── style.css         # Design tokens, glassmorphism, responsive breakpoints
│   ├── js/
│   │   └── main.js           # Shared frontend utilities
│   └── images/               # Static assets
│
└── templates/
    ├── base.html             # Master layout — Tailwind CDN, notifications, hamburger menu
    ├── index.html            # Public landing page
    ├── login.html            # Login form with JWT token storage
    ├── signup.html           # Multi-step role-based signup
    ├── demo.html             # Demo/preview page
    ├── 404.html / 500.html   # Error pages
    │
    ├── dashboards/           # Main dashboard for each role
    │   ├── children.html
    │   ├── patient.html
    │   ├── doctor.html
    │   ├── hospital_admin.html
    │   └── diagnostic.html
    │
    ├── children/             # Children role sub-pages
    │   ├── appointments.html
    │   ├── chat.html
    │   ├── family.html
    │   ├── reports.html
    │   └── settings.html
    │
    ├── patient/              # Patient role sub-pages
    │   ├── chat.html
    │   └── reminders.html
    │
    ├── doctor/               # Doctor role sub-pages
    │   ├── consultations.html
    │   ├── patient_detail.html
    │   └── schedule.html
    │
    ├── admin/                # Hospital admin sub-pages
    │   ├── appointments.html
    │   ├── doctors.html
    │   └── reports.html
    │
    └── diagnostic/           # Diagnostic center sub-pages
        ├── upload.html
        └── history.html
```

---

## Database Schema

Run `supabase_schema.sql` in your Supabase SQL editor to create all tables, indexes, triggers, and RLS policies in one shot.

Key design decisions:
- `users.email_role_key` — composite unique key `email_norm + role`, allowing the same email to register under different roles
- `messages.ts` — unix float timestamp used for efficient `since`-based polling queries
- `user_sessions.jti` — unique JWT ID per session; revoked flag allows instant server-side token invalidation
- All tables have `created_at_ts` (timezone-aware) and most have `updated_at` maintained by trigger

---

## API Reference

### Auth

```
POST /api/auth/signup        Body: {full_name, email, password, role, ...role_fields}
POST /api/auth/login         Body: {email, password, role}
POST /api/auth/refresh       Body: {refresh_token}
POST /api/auth/logout        Header: Authorization: Bearer <token>
GET  /api/auth/me            Header: Authorization: Bearer <token>
```

Response from login/signup:
```json
{
  "user": { "id": 1, "full_name": "...", "email": "...", "role": "..." },
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "Bearer",
  "expires_in": 86400,
  "dashboard": "/dashboard/children"
}
```

### Chat

```
GET  /api/chat/messages          Returns last 100 messages
GET  /api/chat/messages?since=ts Returns only messages newer than unix timestamp
POST /api/chat/send              Body: {sender, sender_name, text}
```

### Appointments

```
GET  /api/appointments                        All appointments
GET  /api/appointments?patient_name=<name>    Filter by patient
GET  /api/appointments?doctor=<name>          Filter by doctor
GET  /api/appointments/<id>                   Single appointment
POST /api/appointments/book                   Body: {patient_name, doctor, date, time, department}
```

### Patients

```
GET  /api/patients               All patients
GET  /api/patients/<id>          Patient + appointments + reports
POST /api/patients/register      Body: {name, age, gender, blood_group, phone, ...}
POST /api/patients/<id>/vitals   Body: {heart_rate, blood_pressure, blood_sugar, bmi}
```

### Doctors

```
GET  /api/doctors                All doctors
GET  /api/doctors/<id>           Single doctor
POST /api/doctors/register       Body: {name, specialty, phone, availability, medical_license_id}
```

### Reports & AI

```
GET  /api/reports                All reports
GET  /api/reports?patient_name=  Filter by patient
GET  /api/reports/<id>           Single report
POST /api/analyze-report         Multipart: file + patient_name — triggers Ollama AI analysis
```

### Notifications

```
GET  /api/notifications?role=<role>   Notifications for a role
POST /api/notifications/read          Body: {id}
```

### Medicine Log

```
GET  /api/medicine-log               All logs
GET  /api/medicine-log?taken_by=     Filter by user
POST /api/medicine-log/add           Body: {medicine, taken_by}
```

### SOS

```
POST /api/sos                Body: {triggered_by, location}
GET  /api/sos/alerts         All SOS alerts
```

### Consultation Notes

```
GET  /api/consultation-notes                    All notes
GET  /api/consultation-notes?patient_name=      Filter by patient
POST /api/consultation-notes/add                Body: {patient_name, doctor_name, note}
```

---

## Setup & Installation

### Prerequisites

- Python 3.11+
- A free [Supabase](https://supabase.com) account
- [Ollama](https://ollama.com) installed locally for AI features (optional)

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd "New folder (2)"
```

### 2. Create a virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up Supabase

1. Go to [supabase.com](https://supabase.com) and create a free project
2. Open the **SQL Editor** in your project dashboard
3. Paste and run the entire contents of `supabase_schema.sql`
4. Go to **Project Settings → API** and copy:
   - Project URL → `SUPABASE_URL`
   - `anon` / public key → `SUPABASE_KEY`
   - `service_role` key → `SUPABASE_SERVICE_KEY` (for admin ops)

### 5. Configure environment variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

```env
SECRET_KEY=your-32-char-random-string-here
JWT_SECRET=another-different-32-char-random-string
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-role-key
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=llama3
DEBUG=True
```

Generate secure keys with:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 6. Set up Ollama (optional — for AI report analysis)

```bash
# Install from https://ollama.com then:
ollama serve
ollama pull llama3          # text reports
ollama pull llava           # image/X-ray/MRI analysis
```

### 7. Run the development server

```bash
python app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000)

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SECRET_KEY` | ✅ | — | Flask session signing key |
| `JWT_SECRET` | ✅ | falls back to `SECRET_KEY` | JWT signing secret |
| `JWT_ACCESS_EXPIRES_HOURS` | ❌ | `24` | Access token lifetime in hours |
| `JWT_REFRESH_EXPIRES_DAYS` | ❌ | `30` | Refresh token lifetime in days |
| `SUPABASE_URL` | ✅ | — | Your Supabase project API URL |
| `SUPABASE_KEY` | ✅ | — | Supabase anon/public key |
| `SUPABASE_SERVICE_KEY` | ❌ | — | Service role key for admin ops |
| `SUPABASE_STORAGE_BUCKET` | ❌ | `careconnect-reports` | Storage bucket name |
| `OLLAMA_BASE_URL` | ❌ | `http://127.0.0.1:11434` | Ollama server URL |
| `OLLAMA_MODEL` | ❌ | `llama3` | Model name for text analysis |
| `OLLAMA_REQUEST_TIMEOUT_SEC` | ❌ | `45` | AI request timeout |
| `OLLAMA_NUM_CTX` | ❌ | `1024` | Context window size |
| `OLLAMA_NUM_PREDICT` | ❌ | `220` | Max tokens to generate |
| `DEBUG` | ❌ | `True` | Flask debug mode |

---

## Deployment

### Recommended: Railway or Render (supports WebSockets)

Both platforms support persistent servers, which means Socket.IO real-time chat works fully.

```bash
# Railway
railway login
railway init
railway up

# Set env vars in the Railway dashboard
```

### Vercel (HTTP only — WebSockets not supported)

Real-time chat falls back to 3-second polling automatically. Everything else works.

```bash
npm i -g vercel
vercel --prod
```

Set all environment variables in the Vercel project dashboard under **Settings → Environment Variables**.

### Production checklist

- [ ] Set `DEBUG=False`
- [ ] Use a strong, unique `SECRET_KEY` (32+ chars)
- [ ] Use a separate `JWT_SECRET` different from `SECRET_KEY`
- [ ] Use `SUPABASE_SERVICE_KEY` on the server (never expose in browser)
- [ ] Set `secure=True` on cookies (handled automatically when `DEBUG=False`)
- [ ] Point `OLLAMA_BASE_URL` to a hosted model API if not self-hosting Ollama
- [ ] Run `supabase_schema.sql` in your production Supabase project

---

## Troubleshooting

**Supabase connection fails**
- Verify `SUPABASE_URL` is the HTTPS API URL (e.g. `https://xxx.supabase.co`), not the PostgreSQL connection string
- Check that `SUPABASE_KEY` is the `anon` key, not the JWT secret
- If you see Row Level Security errors, run `supabase_schema.sql` to apply the access policies

**Ollama AI not working**
- Run `ollama serve` in a separate terminal
- Confirm the model is pulled: `ollama list`
- For image analysis (X-rays, MRIs), pull a vision model: `ollama pull llava`
- The app continues to work without Ollama — AI features return an error message

**Chat messages delayed**
- If Socket.IO is connecting, messages should be instant
- Check browser console for WebSocket errors
- The 3-second polling fallback activates automatically if the socket disconnects

**JWT token errors**
- `Token is invalid or has expired` — log in again to get a fresh token
- `Session has been revoked` — the token was explicitly revoked (logout or force-logout)
- Tokens are stored in `localStorage` as `cc_token` and as an HttpOnly cookie

**Tables don't exist**
- Run the full `supabase_schema.sql` in your Supabase SQL editor
- The `user_sessions` table is required for JWT auth — make sure it was created

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m "Add your feature"`
4. Push to the branch: `git push origin feature/your-feature`
5. Open a Pull Request

Review `CareConnect_PRD.docx` for the full product requirements and design spec.

---

*Built with Flask · Supabase · Socket.IO · Tailwind CSS · Ollama AI*
