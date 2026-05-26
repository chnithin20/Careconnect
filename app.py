import logging
import uuid
import os
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_socketio import SocketIO, emit
import jwt as pyjwt
import time
from datetime import datetime, timezone, timedelta

from config import Config
import ai_service
from supabase_db import (
    UserRepository,
    PatientRepository,
    DoctorRepository,
    AppointmentRepository,
    MessageRepository,
    NotificationRepository,
    ConsultationNoteRepository,
    MedicineLogRepository,
    SOSAlertRepository,
    ReportRepository,
    AuditLogRepository,
    SessionRepository,
)

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = os.environ.get("SECRET_KEY") or "careconnect-dev-secret-key-12345"

# ---------------------------------------------------------------------------
# JWT Configuration
# ---------------------------------------------------------------------------
JWT_SECRET = os.environ.get("JWT_SECRET") or os.environ.get("SECRET_KEY") or "careconnect-jwt-secret-change-in-prod"
JWT_ALGORITHM = "HS256"
JWT_ACCESS_EXPIRES_HOURS = int(os.environ.get("JWT_ACCESS_EXPIRES_HOURS", "24"))   # 24 h default
JWT_REFRESH_EXPIRES_DAYS = int(os.environ.get("JWT_REFRESH_EXPIRES_DAYS", "30"))   # 30 d default


def _create_access_token(user: dict) -> tuple[str, str, datetime]:
    """Create a signed JWT access token.  Returns (token, jti, expires_at)."""
    jti = uuid.uuid4().hex
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=JWT_ACCESS_EXPIRES_HOURS)
    payload = {
        "sub": str(user["id"]),
        "jti": jti,
        "role": user.get("role", "children"),
        "full_name": user.get("full_name", ""),
        "email": user.get("email", ""),
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "type": "access",
    }
    token = pyjwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token, jti, expires_at


def _create_refresh_token(user: dict) -> tuple[str, str, datetime]:
    """Create a long-lived refresh token.  Returns (token, jti, expires_at)."""
    jti = uuid.uuid4().hex
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=JWT_REFRESH_EXPIRES_DAYS)
    payload = {
        "sub": str(user["id"]),
        "jti": jti,
        "role": user.get("role", "children"),
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "type": "refresh",
    }
    token = pyjwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token, jti, expires_at


def _decode_token(token: str) -> dict | None:
    """Decode and verify a JWT.  Returns payload dict or None on failure."""
    try:
        return pyjwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except pyjwt.ExpiredSignatureError:
        return None
    except pyjwt.InvalidTokenError:
        return None


def _extract_bearer(req) -> str | None:
    """Pull the raw token from Authorization: Bearer <token> header."""
    auth = req.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    # Also accept token stored in session cookie (for browser page loads)
    return req.cookies.get("access_token") or session.get("access_token")


def require_jwt(f):
    """Decorator: validates JWT + DB session for API routes.
    Injects `g.jwt_user` with the decoded payload.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        from flask import g
        token = _extract_bearer(request)
        if not token:
            return jsonify({"error": "Authentication required. Provide a Bearer token."}), 401

        payload = _decode_token(token)
        if not payload:
            return jsonify({"error": "Token is invalid or has expired."}), 401

        if payload.get("type") != "access":
            return jsonify({"error": "Access token required."}), 401

        # Verify the token is still active in the database (not revoked)
        jti = payload.get("jti", "")
        if not SessionRepository.is_valid(jti):
            return jsonify({"error": "Session has been revoked or expired. Please log in again."}), 401

        g.jwt_user = payload
        return f(*args, **kwargs)
    return decorated


def login_required(f):
    """Decorator for server-rendered page routes.
    Checks Flask session for a logged-in user.
    Redirects to /login with a flash message if not authenticated.
    Also validates the JWT cookie if present for extra security.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # Check Flask session first (set on login/signup)
        if not session.get("user"):
            flash("Please log in to access this page.", "danger")
            return redirect(url_for("login"))

        # Optionally validate the JWT cookie if present
        token = request.cookies.get("access_token") or session.get("access_token")
        if token:
            payload = _decode_token(token)
            if not payload:
                # Token expired — clear session and redirect
                session.clear()
                flash("Your session has expired. Please log in again.", "danger")
                return redirect(url_for("login"))

        return f(*args, **kwargs)
    return decorated


def _issue_tokens_and_respond(user: dict, status_code: int = 200):
    """Create access + refresh tokens, persist sessions, return JSON response."""
    access_token, access_jti, access_exp = _create_access_token(user)
    refresh_token, refresh_jti, refresh_exp = _create_refresh_token(user)

    ua = request.headers.get("User-Agent", "")
    ip = request.remote_addr or ""

    # Persist both sessions to DB
    SessionRepository.create_session(
        user_id=int(user["id"]),
        jti=access_jti,
        role=user.get("role", "children"),
        expires_at=access_exp.isoformat(),
        user_agent=ua,
        ip_address=ip,
    )
    SessionRepository.create_session(
        user_id=int(user["id"]),
        jti=refresh_jti,
        role=user.get("role", "children"),
        expires_at=refresh_exp.isoformat(),
        user_agent=ua,
        ip_address=ip,
    )

    # Also keep Flask session for server-rendered pages
    session["role"] = _session_role_for_auth(user.get("role", "children"))
    session["user"] = {
        "id": user.get("id"),
        "full_name": user.get("full_name"),
        "email": user.get("email"),
        "role": user.get("role"),
    }
    session["access_token"] = access_token

    safe_user = {k: v for k, v in user.items() if k != "password_hash"}
    resp = jsonify({
        "user": safe_user,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
        "expires_in": JWT_ACCESS_EXPIRES_HOURS * 3600,
        "dashboard": _dashboard_url_for_role(user.get("role", "children")),
    })
    resp.status_code = status_code
    # Set HttpOnly cookie so browser pages can use it without JS access
    resp.set_cookie(
        "access_token",
        access_token,
        httponly=True,
        secure=not app.config.get("DEBUG", True),
        samesite="Lax",
        max_age=JWT_ACCESS_EXPIRES_HOURS * 3600,
    )
    return resp

# Initialize Socket.IO
# async_mode='threading' works locally and on Railway/Render.
# On Vercel (serverless), WebSockets are not supported — Socket.IO
# gracefully falls back to HTTP long-polling via simple-websocket.
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='threading',
    logger=False,
    engineio_logger=False,
)

# Configure logging for production feedback
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)
ALLOWED_AUTH_ROLES = {"patient", "children", "doctor", "hospital-admin", "diagnostic"}
ROLE_UNIQUE_LABELS = {
    "doctor": ("medical_license_id", "Medical License ID"),
    "hospital-admin": ("employee_id", "Employee ID"),
}


def _current_role() -> str:
    return session.get("role", "children")


def _normalize_auth_role(role: str) -> str:
    value = (role or "").strip().lower()
    if value == "admin":
        return "hospital-admin"
    return value


def _session_role_for_auth(role: str) -> str:
    return "admin" if role == "hospital-admin" else role


def _dashboard_url_for_role(role: str) -> str:
    return "/dashboard/hospital-admin" if role == "hospital-admin" else f"/dashboard/{role}"


def _sanitize_signup_profile(role: str, body: dict) -> dict:
    """Validate and normalize role-specific signup fields."""
    profile = {}

    if role == "doctor":
        specialty = (body.get("specialty") or "").strip()
        medical_license_id = (body.get("medical_license_id") or body.get("license") or "").strip()
        if not specialty:
            raise ValueError("Specialty is required for doctor signup.")
        if not medical_license_id:
            raise ValueError("Medical License ID is required for doctor signup.")
        profile["specialty"] = specialty
        profile["medical_license_id"] = medical_license_id

    elif role == "children":
        relationship = (body.get("relationship") or "").strip()
        if not relationship:
            raise ValueError("Relationship to patient is required for children signup.")
        profile["relationship"] = relationship

    elif role == "patient":
        age_raw = str(body.get("age") or "").strip()
        blood_group = (body.get("blood_group") or "").strip()
        if age_raw:
            try:
                age = int(age_raw)
            except Exception as exc:
                raise ValueError("Age must be a valid number.") from exc
            if age <= 0 or age > 130:
                raise ValueError("Age must be between 1 and 130.")
            profile["age"] = age
        if blood_group:
            profile["blood_group"] = blood_group

    elif role == "hospital-admin":
        hospital_name = (body.get("hospital_name") or "").strip()
        employee_id = (body.get("employee_id") or "").strip()
        if not hospital_name:
            raise ValueError("Hospital / Center Name is required for hospital admin signup.")
        if not employee_id:
            raise ValueError("Employee ID is required for hospital admin signup.")
        profile["hospital_name"] = hospital_name
        profile["employee_id"] = employee_id

    elif role == "diagnostic":
        lab_name = (body.get("lab_name") or "").strip()
        location = (body.get("location") or "").strip()
        if not lab_name:
            raise ValueError("Diagnostic Lab Name is required for diagnostic signup.")
        if not location:
            raise ValueError("Facility Address is required for diagnostic signup.")
        profile["lab_name"] = lab_name
        profile["location"] = location

    return profile


# --- Error Handlers ---

@app.errorhandler(404)
def page_not_found(e):
    logger.warning(f"404 Error: {request.url}")
    return render_template("404.html"), 404


@app.errorhandler(500)
def internal_server_error(e):
    logger.error(f"500 Error: {e}")
    if request.path.startswith("/api/"):
        return jsonify({"error": "Server error while processing the request."}), 500
    return render_template("500.html"), 500


@app.errorhandler(Exception)
def unhandled_exception(e):
    logger.exception(f"Unhandled error: {e}")
    if request.path.startswith("/api/"):
        message = str(e)
        if "row-level security" in message.lower():
            message = "Supabase blocked this action with Row Level Security. Apply supabase_schema.sql policies or set SUPABASE_SERVICE_KEY on the server."
        return jsonify({"error": message}), 500
    return render_template("500.html"), 500


# --- Core Routes ---

@app.route("/")
def index():
    """Initial landing page."""
    return render_template("index.html")


@app.route("/login")
def login():
    return render_template("login.html", title="Log In")


@app.route("/dashboard")
def dashboard_redirect():
    """Redirects base dashboard link to children dashboard as default."""
    return redirect(url_for("children_dashboard"))


@app.route("/dashboard/children")
@login_required
def children_dashboard():
    session["role"] = "children"
    vitals = {"heart_rate": 72, "blood_pressure": "118/76", "blood_sugar": 95, "bmi": 21.5}

    # Only fetch the single most-recent confirmed appointment for this user,
    # not all 100 appointments from the whole table.
    user_name = (session.get("user") or {}).get("full_name", "")
    connected_doctor = None
    if user_name:
        user_apts = AppointmentRepository.get_confirmed_doctor_for_user(user_name)
        if user_apts:
            connected_doctor = user_apts

    return render_template("dashboards/children.html", vitals=vitals, connected_doctor=connected_doctor, title="Children Portal")


@app.route("/dashboard/patient")
@login_required
def patient_dashboard():
    session["role"] = "patient"
    # Fetch only this specific patient by their ID — not the whole patients table
    patient_id = request.args.get("patient_id") or session.get("patient_id")
    patient = None
    if patient_id:
        session["patient_id"] = patient_id
        patient = PatientRepository.get_patient_by_id(patient_id)
    vitals = (patient or {}).get("vitals") or {"heart_rate": 72, "blood_pressure": "118/76", "blood_sugar": 95, "bmi": 21.5}
    patient_name = (patient or {}).get("name") or ""
    return render_template(
        "dashboards/patient.html",
        vitals=vitals,
        patient_id=patient_id,
        patient_name=patient_name,
        title="Patient Portal",
    )


@app.route("/dashboard/doctor")
@login_required
def doctor_dashboard():
    session["role"] = "doctor"
    return render_template("dashboards/doctor.html", title="Doctor Portal")


@app.route("/dashboard/hospital-admin")
@login_required
def hospital_admin_dashboard():
    session["role"] = "admin"
    return render_template("dashboards/hospital_admin.html", title="Admin Overview")


@app.route("/dashboard/diagnostic")
@login_required
def diagnostic_dashboard():
    session["role"] = "diagnostic"
    return render_template("dashboards/diagnostic.html", title="Lab Terminal")


# --- Children Role Routes ---

@app.route("/children/appointments")
@login_required
def children_appointments():
    session["role"] = "children"
    # Only load patients/doctors lists when the booking page is actually opened,
    # and only fetch names (not full rows) for the dropdowns
    patients = PatientRepository.get_patient_names_only()
    doctors = DoctorRepository.get_doctor_names_only()
    return render_template("children/appointments.html", title="Bookings", patients=patients, doctors=doctors)


@app.route("/children/reports")
@login_required
def children_reports():
    session["role"] = "children"
    # Only need patient names for the dropdown — not full patient records
    patients = PatientRepository.get_patient_names_only()
    return render_template("children/reports.html", title="AI Reports", patients=patients)


@app.route("/children/family")
@login_required
def children_family():
    session["role"] = "children"
    return render_template("children/family.html", title="Family Circle")


@app.route("/children/settings")
@login_required
def children_settings():
    session["role"] = "children"
    return render_template("children/settings.html", title="Settings")


@app.route("/children/chat")
@login_required
def children_chat():
    session["role"] = "children"
    # Only fetch the connected doctor name for this user — not all appointments
    user_name = (session.get("user") or {}).get("full_name", "")
    connected_doctor_name = None
    if user_name:
        connected_doctor_name = AppointmentRepository.get_confirmed_doctor_for_user(user_name)
    return render_template("children/chat.html", title="Family Chat", connected_doctor=connected_doctor_name)


# --- Patient Role Routes ---

@app.route("/patient/reminders")
@login_required
def patient_reminders():
    session["role"] = "patient"
    return render_template("patient/reminders.html", title="Reminders")


@app.route("/patient/chat")
@login_required
def patient_chat():
    session["role"] = "patient"
    return render_template("patient/chat.html", title="Family Chat")


# --- Doctor Role Routes ---

@app.route("/doctor/schedule")
@login_required
def doctor_schedule():
    session["role"] = "doctor"
    return render_template("doctor/schedule.html", title="Today's Schedule")


@app.route("/doctor/consultations")
@login_required
def doctor_consultations():
    session["role"] = "doctor"
    return render_template("doctor/consultations.html", title="Consultations")


# --- Hospital Admin Role Routes ---

@app.route("/admin/doctors")
@login_required
def admin_doctors():
    session["role"] = "admin"
    return render_template("admin/doctors.html", title="Manage Doctors")


@app.route("/admin/appointments")
@login_required
def admin_appointments():
    session["role"] = "admin"
    return render_template("admin/appointments.html", title="Appointments")


@app.route("/admin/reports")
@login_required
def admin_reports():
    session["role"] = "admin"
    return render_template("admin/reports.html", title="Hospital Reports")


# --- Diagnostic Role Routes ---

@app.route("/diagnostic/upload")
@login_required
def upload_results():
    session["role"] = "diagnostic"
    return render_template("diagnostic/upload.html", title="Upload Results")


@app.route("/diagnostic/history")
@login_required
def diagnostic_history():
    session["role"] = "diagnostic"
    return render_template("diagnostic/history.html", title="Diagnostic History")


# --- Legacy route aliases to keep older links functional ---

@app.route("/appointments")
def appointments_alias():
    role = _current_role()
    if role == "patient":
        return redirect(url_for("patient_reminders"))
    if role == "doctor":
        return redirect(url_for("doctor_schedule"))
    if role == "admin":
        return redirect(url_for("admin_appointments"))
    return redirect(url_for("children_appointments"))


@app.route("/reports")
def reports_alias():
    role = _current_role()
    if role == "admin":
        return redirect(url_for("admin_reports"))
    return redirect(url_for("children_reports"))


@app.route("/chat")
def chat_alias():
    role = _current_role()
    if role == "patient":
        return redirect(url_for("patient_chat"))
    return redirect(url_for("children_chat"))


@app.route("/consultations")
def consultations_alias():
    return redirect(url_for("doctor_consultations"))


@app.route("/family")
def family_alias():
    return redirect(url_for("children_family"))


@app.route("/settings")
def settings_alias():
    return redirect(url_for("children_settings"))


# --- Shared action routes ---

@app.route("/action/medicine-taken")
def medicine_taken():
    med = request.args.get("med", "Morning Medication")
    pid = request.args.get("patient_id")
    MedicineLogRepository.create_log(
        user_id=pid,
        medicine_name=med,
        taken_by="patient",
        taken_at=datetime.now().isoformat()
    )
    flash(f"{med} logged! Your children have been notified.", "success")
    return redirect(url_for("patient_dashboard"))


@app.route("/action/view-patient/<id>")
def view_patient(id):
    flash(f"Loading health history for Patient {id}...", "info")
    return redirect(url_for("doctor_dashboard"))


@app.route("/action/confirm-appointment", methods=["POST"])
def confirm_appointment():
    patient_name = request.form.get("patient_name", "Unknown Patient")
    doctor = request.form.get("doctor", "Assigned Doctor")
    department = request.form.get("department", "General")
    date = request.form.get("date", "")
    time_str = request.form.get("time", "")
    apt = AppointmentRepository.create_appointment(
        patient_name=patient_name,
        doctor_name=doctor,
        appointment_date=date,
        appointment_time=time_str,
        department=department,
        status="Confirmed"
    )
    flash(
        f"Appointment confirmed for {patient_name} with {doctor} on {date}!",
        "success",
    )
    return redirect(request.referrer or url_for("children_appointments"))


@app.route("/action/view-summary/<id>")
def view_summary(id):
    flash(f"Retrieving AI Summary for Report #{id}...", "info")
    return redirect(request.referrer or url_for("children_reports"))


@app.route("/emergency")
def emergency():
    try:
        SOSAlertRepository.create_alert(
            triggered_by=session.get("user", {}).get("full_name") or "Patient",
            location=request.args.get("location", "Unknown"),
            created_at=datetime.now().isoformat()
        )
    except Exception as e:
        logger.error(f"Emergency alert persistence failed: {e}")
    flash("Emergency alert sent. Family members and hospitals have been notified.", "danger")
    return redirect(request.referrer or url_for("index"))


@app.route("/demo")
def demo():
    return render_template("demo.html", title="Watch Demo")


@app.route("/signup")
def signup():
    return render_template("signup.html", title="Sign Up")


@app.route("/api/auth/signup", methods=["POST"])
def api_auth_signup():
    body = request.get_json(silent=True) or {}
    full_name = (body.get("full_name") or "").strip()
    email = (body.get("email") or "").strip()
    password = body.get("password") or ""
    confirm_password = body.get("confirm_password") or ""
    role = _normalize_auth_role(body.get("role"))

    if not full_name or not email or not password or not role:
        return jsonify({"error": "full_name, email, password, and role are required."}), 400
    if role not in ALLOWED_AUTH_ROLES:
        return jsonify({"error": "Invalid role selected."}), 400
    if "@" not in email or "." not in email.split("@")[-1]:
        return jsonify({"error": "Please enter a valid email address."}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters long."}), 400
    if confirm_password and confirm_password != password:
        return jsonify({"error": "Passwords do not match."}), 400

    try:
        profile = _sanitize_signup_profile(role, body)
        user = UserRepository.create_user(
            full_name=full_name,
            email=email,
            password=password,
            role=role,
            **profile,
        )
        # Issue JWT tokens and persist session to DB
        return _issue_tokens_and_respond(user, status_code=201)
    except ValueError as e:
        message = str(e)
        lower_message = message.lower()
        if "already exists" in lower_message or "already registered" in lower_message:
            return jsonify({"error": message}), 409
        return jsonify({"error": message}), 400
    except Exception as e:
        message = str(e)
        logger.error(f"Signup failed: {message}")
        lower_message = message.lower()
        if "duplicate key" in lower_message or "23505" in lower_message:
            if "email_role_key" in lower_message:
                return jsonify({"error": "This email is already registered for the selected role."}), 409
            if "email_norm" in lower_message:
                return jsonify({
                    "error": "This Supabase database still has a global unique constraint on email_norm. Drop users_email_norm_key so the same email can be used for different roles."
                }), 409
            return jsonify({"error": "A matching account already exists."}), 409
        return jsonify({"error": f"Signup failed: {message}"}), 500


@app.route("/api/auth/login", methods=["POST"])
def api_auth_login():
    body = request.get_json(force=True)
    email = (body.get("email") or "").strip()
    password = body.get("password") or ""
    role = _normalize_auth_role(body.get("role"))

    if not email or not password or not role:
        return jsonify({"error": "email, password, and role are required."}), 400
    if role not in ALLOWED_AUTH_ROLES:
        return jsonify({"error": "Invalid role selected."}), 400

    user = UserRepository.get_user_by_email_role(email=email, role=role, password=password)
    if not user:
        return jsonify({"error": "Invalid credentials for this role."}), 401

    # Issue JWT tokens and persist session to DB
    return _issue_tokens_and_respond(user, status_code=200)


@app.route("/api/auth/refresh", methods=["POST"])
def api_auth_refresh():
    """Exchange a valid refresh token for a new access + refresh token pair (rotation)."""
    body = request.get_json(force=True) or {}
    refresh_token = body.get("refresh_token") or _extract_bearer(request)
    if not refresh_token:
        return jsonify({"error": "refresh_token is required."}), 400

    payload = _decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        return jsonify({"error": "Invalid or expired refresh token."}), 401

    jti = payload.get("jti", "")
    if not SessionRepository.is_valid(jti):
        return jsonify({"error": "Refresh token has been revoked. Please log in again."}), 401

    # Rotate: revoke old refresh token so it can never be reused
    SessionRepository.revoke_session(jti)

    user_id = int(payload.get("sub", 0))
    user = UserRepository.get_user_by_id(user_id)
    if not user:
        return jsonify({"error": "User not found."}), 404

    return _issue_tokens_and_respond(user, status_code=200)


@app.route("/api/auth/logout", methods=["POST"])
def api_auth_logout():
    """Revoke the current access token and clear the Flask session."""
    token = _extract_bearer(request)
    if token:
        payload = _decode_token(token)
        if payload and payload.get("jti"):
            SessionRepository.revoke_session(payload["jti"])

    session.clear()
    resp = jsonify({"message": "Logged out successfully."})
    resp.delete_cookie("access_token")
    return resp, 200


@app.route("/api/auth/me")
@require_jwt
def api_auth_me():
    """Return the currently authenticated user's profile (requires valid JWT)."""
    from flask import g
    user_id = int(g.jwt_user.get("sub", 0))
    user = UserRepository.get_user_by_id(user_id)
    if not user:
        return jsonify({"error": "User not found."}), 404
    safe_user = {k: v for k, v in user.items() if k != "password_hash"}
    return jsonify(safe_user)



# ---------------------------------------------------------------------------
# Real-Time API Endpoints
# ---------------------------------------------------------------------------

@app.route("/api/chat/messages")
def api_get_messages():
    # Always filter by since — never dump the full messages table
    since = float(request.args.get("since", 0))
    if since > 0:
        msgs = MessageRepository.get_messages_since(since)
    else:
        # Initial load: only last 50 messages, not 100
        msgs = MessageRepository.get_all_messages(limit=50)
    return jsonify(msgs)


@app.route("/api/chat/send", methods=["POST"])
def api_send_message():
    body = request.get_json(force=True)
    sender = body.get("sender", "children")
    sender_name = body.get("sender_name", "Unknown")
    text = body.get("text", "").strip()
    if not text:
        return jsonify({"error": "Empty message"}), 400
    msg = MessageRepository.create_message(
        sender_id=sender,
        sender_name=sender_name,
        message_text=text,
        created_at=datetime.now().isoformat()
    )
    if msg:
        socketio.emit('new_message', msg, broadcast=True)
    return jsonify(msg)


@app.route("/api/appointments")
def api_get_appointments():
    patient_name = request.args.get("patient_name")
    doctor = request.args.get("doctor")
    appointment_id = request.args.get("id")

    # Always filter — never dump the whole table unless admin explicitly requests it
    if appointment_id:
        apt = AppointmentRepository.get_appointment_by_id(int(appointment_id))
        return jsonify(apt) if apt else (jsonify({"error": "Not found"}), 404)
    if patient_name:
        return jsonify(AppointmentRepository.get_appointments_by_patient(patient_name))
    # Auto-filter by logged-in doctor's name
    if not doctor and session.get("role") == "doctor" and session.get("user"):
        doctor = session["user"].get("full_name")
    if doctor:
        return jsonify(AppointmentRepository.get_appointments_by_doctor(doctor))
    # Fallback for admin views only — scoped to limit 20 most recent
    return jsonify(AppointmentRepository.get_all_appointments(limit=20))


@app.route("/api/appointments/book", methods=["POST"])
def api_book_appointment():
    body = request.get_json(force=True)
    patient_name = (body.get("patient_name") or "").strip()
    doctor = (body.get("doctor") or "").strip()
    date = (body.get("date") or "").strip()
    if not patient_name or not doctor or not date:
        return jsonify({"error": "patient_name, doctor, and date are required"}), 400
    apt = AppointmentRepository.create_appointment(
        patient_name=patient_name,
        doctor_name=doctor,
        appointment_date=date,
        appointment_time=body.get("time", ""),
        department=body.get("department", "General"),
        status="Pending"
    )
    return jsonify(apt)


@app.route("/api/notifications")
def api_get_notifications():
    role = request.args.get("role", "children")
    since = float(request.args.get("since", 0))
    patient_id = request.args.get("patient_id") or session.get("patient_id")
    # Always filtered by role + since — never full table
    notifs = NotificationRepository.get_notifications_by_role(role=role, since_ts=since)
    if role == "patient" and patient_id:
        notifs.extend(NotificationRepository.get_notifications_by_role(
            role=f"patient:{patient_id}", since_ts=since))
        notifs.sort(key=lambda item: item.get("ts") or 0, reverse=True)
    return jsonify(notifs)


@app.route("/api/notifications/read", methods=["POST"])
def api_mark_read():
    nid = request.get_json(force=True).get("id")
    if nid:
        NotificationRepository.mark_notification_as_read(notification_id=nid)
    return jsonify({"ok": True})


@app.route("/api/medicine-log")
def api_medicine_log():
    taken_by = request.args.get("taken_by")
    # Always require taken_by filter — never dump the whole log table
    if taken_by:
        return jsonify(MedicineLogRepository.get_logs_by_user(taken_by) or [])
    # If no filter, use the logged-in user's name from session
    user_name = (session.get("user") or {}).get("full_name", "")
    if user_name:
        return jsonify(MedicineLogRepository.get_logs_by_user(user_name) or [])
    return jsonify([])


@app.route("/api/medicine-log/add", methods=["POST"])
def api_add_medicine():
    body = request.get_json(force=True)
    taken_by = body.get("taken_by") or (session.get("user") or {}).get("full_name") or "patient"
    entry = MedicineLogRepository.create_log(
        user_id=session.get("user_id"),
        medicine_name=body.get("medicine", "Medicine"),
        taken_by=taken_by,
        taken_at=datetime.now().isoformat()
    )
    return jsonify(entry)


@app.route("/api/consultation-notes")
def api_get_notes():
    patient_name = request.args.get("patient_name")
    doctor_name = request.args.get("doctor_name")
    # Always filter by patient or doctor — never dump all notes
    if patient_name:
        return jsonify(ConsultationNoteRepository.get_notes_by_patient(patient_name) or [])
    if doctor_name:
        return jsonify(ConsultationNoteRepository.get_notes_by_doctor(doctor_name) or [])
    # Auto-filter by logged-in doctor
    if session.get("role") == "doctor" and session.get("user"):
        doc = session["user"].get("full_name", "")
        if doc:
            return jsonify(ConsultationNoteRepository.get_notes_by_doctor(doc) or [])
    return jsonify([])


@app.route("/api/consultation-notes/add", methods=["POST"])
def api_add_note():
    body = request.get_json(force=True)
    note = ConsultationNoteRepository.create_note(
        patient_name=body.get("patient_name", "Patient"),
        doctor_name=body.get("doctor_name", "Doctor"),
        note_content=body.get("note", ""),
        created_at=datetime.now().isoformat()
    )
    return jsonify(note)


@app.route("/api/sos", methods=["POST"])
def api_sos():
    body = request.get_json(force=True)
    alert = SOSAlertRepository.create_alert(
        triggered_by=body.get("triggered_by", "Patient"),
        location=body.get("location", "Unknown"),
        created_at=datetime.now().isoformat()
    )
    return jsonify(alert)


@app.route("/api/sos/alerts")
def api_sos_alerts():
    # Scoped to last 20 — admin view only
    return jsonify(SOSAlertRepository.get_all_alerts(limit=20))


@app.route("/api/reports")
def api_reports():
    patient_name = request.args.get("patient_name")
    uploaded_by = request.args.get("uploaded_by")
    # Always filter by patient or uploader — never dump all reports
    if patient_name:
        return jsonify(ReportRepository.get_reports_by_patient(patient_name))
    if uploaded_by:
        return jsonify(ReportRepository.get_reports_by_uploader(uploaded_by))
    # Auto-filter by logged-in user
    user_name = (session.get("user") or {}).get("full_name", "")
    role = session.get("role", "")
    if user_name and role in ("children", "diagnostic"):
        return jsonify(ReportRepository.get_reports_by_uploader(user_name))
    if user_name and role == "patient":
        return jsonify(ReportRepository.get_reports_by_patient(user_name))
    return jsonify([])


@app.route("/api/patients")
def api_get_patients():
    # Doctor/admin list view — full records needed here, scoped to limit 50
    return jsonify(PatientRepository.get_all_patients(limit=50))


@app.route("/api/patients/names")
def api_get_patient_names():
    # Lightweight endpoint for dropdowns — only id + name
    return jsonify(PatientRepository.get_patient_names_only())


@app.route("/api/doctors/names")
def api_get_doctor_names():
    # Lightweight endpoint for dropdowns — only id + name + specialty
    return jsonify(DoctorRepository.get_doctor_names_only())


@app.route("/api/storage/backend")
def api_storage_backend():
    return jsonify({"backend": "supabase", "status": "connected"})


@app.route("/api/reports/<int:report_id>")
def api_report_by_id(report_id):
    # Fetch single report by ID — targeted lookup
    r = ReportRepository.get_report_by_id(report_id=report_id)
    if not r:
        return jsonify({"error": f"Report #{report_id} not found"}), 404
    return jsonify(r)


# ---------------------------------------------------------------------------
# Per-Record ID Lookup Endpoints — always by specific ID
# ---------------------------------------------------------------------------

@app.route("/api/appointments/<int:appt_id>")
def api_appointment_by_id(appt_id):
    apt = AppointmentRepository.get_appointment_by_id(appointment_id=appt_id)
    if not apt:
        return jsonify({"error": f"Appointment #{appt_id} not found"}), 404
    return jsonify(apt)


@app.route("/api/notes/<int:note_id>")
def api_note_by_id(note_id):
    note = ConsultationNoteRepository.get_note_by_id(note_id=note_id)
    if not note:
        return jsonify({"error": f"Note #{note_id} not found"}), 404
    return jsonify(note)


@app.route("/api/medicine-log/<int:med_id>")
def api_medicine_entry_by_id(med_id):
    entry = MedicineLogRepository.get_log_by_id(log_id=med_id)
    if not entry:
        return jsonify({"error": f"Medicine entry #{med_id} not found"}), 404
    return jsonify(entry)


# ---------------------------------------------------------------------------
# Patient Registry API
# ---------------------------------------------------------------------------

@app.route("/api/patients/<pid>")
def api_patient_by_id(pid):
    # Single patient by ID — targeted lookup
    p = PatientRepository.get_patient_by_id(patient_id=pid)
    if not p:
        return jsonify({"error": f"Patient #{pid} not found"}), 404
    p_copy = dict(p)
    # Fetch related data scoped to this patient only
    p_copy["appointments"] = AppointmentRepository.get_appointments_by_patient(p["name"])
    p_copy["reports"] = ReportRepository.get_reports_by_patient(p["name"])
    return jsonify(p_copy)


@app.route("/api/patients/register", methods=["POST"])
def api_register_patient():
    body = request.get_json(force=True)
    name = (body.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Patient name is required"}), 400
    patient = PatientRepository.create_patient(
        full_name=name,
        age=int(body.get("age", 0)),
        gender=body.get("gender", "Unknown"),
        blood_type=body.get("blood_group", "Unknown"),
        phone=body.get("phone", ""),
        address=body.get("address", ""),
        emergency_contact=body.get("emergency_contact", ""),
        medical_history="",
        created_at=datetime.now().isoformat()
    )
    return jsonify(patient), 201


@app.route("/api/patients/<pid>/vitals", methods=["POST"])
def api_update_vitals(pid):
    vitals = request.get_json(force=True)
    try:
        # Update only this patient's vitals by ID
        updated = PatientRepository.update_patient_vitals(patient_id=pid, vitals=vitals)
        if not updated:
            return jsonify({"error": f"Patient #{pid} not found"}), 404
        return jsonify(updated)
    except Exception as e:
        logger.error(f"Vitals update error: {e}")
        return jsonify({"error": str(e)}), 400


# Patient detail page (Doctor portal) — all data scoped to one patient
@app.route("/doctor/patient/<pid>")
@login_required
def doctor_view_patient(pid):
    p = PatientRepository.get_patient_by_id(patient_id=pid)
    if not p:
        flash(f"Patient #{pid} not found in the registry.", "danger")
        return redirect(url_for("doctor_dashboard"))
    # All three queries are filtered by this patient's name — no full scans
    appts = AppointmentRepository.get_appointments_by_patient(p["name"])
    notes = ConsultationNoteRepository.get_notes_by_patient(p["name"])
    reps = ReportRepository.get_reports_by_patient(p["name"])
    session["role"] = "doctor"
    return render_template("doctor/patient_detail.html", patient=p, appointments=appts,
                           notes=notes, reports=reps, title=f"Patient #{pid}")


# ---------------------------------------------------------------------------
# Doctor Registry API
# ---------------------------------------------------------------------------

@app.route("/api/doctors")
def api_get_doctors():
    # Full list — only used by admin views, scoped to limit 50
    return jsonify(DoctorRepository.get_all_doctors(limit=50))


@app.route("/api/doctors/<did>")
def api_doctor_by_id(did):
    # Single doctor by ID — targeted lookup
    d = DoctorRepository.get_doctor_by_id(doctor_id=did)
    if not d:
        return jsonify({"error": f"Doctor #{did} not found"}), 404
    return jsonify(d)


@app.route("/api/doctors/register", methods=["POST"])
def api_register_doctor():
    body = request.get_json(force=True)
    name = (body.get("name") or "").strip()
    specialty = (body.get("specialty") or "General").strip()
    if not name:
        return jsonify({"error": "Doctor name is required"}), 400
    doc = DoctorRepository.create_doctor(
        full_name=name,
        specialty=specialty,
        phone=body.get("phone", ""),
        availability=body.get("availability", "Mon-Fri"),
        medical_license_id=body.get("medical_license_id", ""),
        created_at=datetime.now().isoformat()
    )
    return jsonify(doc), 201


@app.route("/api/analyze-report", methods=["POST"])
def analyze_report():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    file = request.files["file"]
    if not file or file.filename == "":
        return jsonify({"error": "No file selected"}), 400
    if not ai_service.is_supported(file.filename):
        exts = "JPG, PNG, WEBP, BMP, GIF, TIFF, PDF, TXT, CSV, MD"
        return jsonify({"error": f"Unsupported file type. Accepted: {exts}"}), 400
    try:
        file_content = file.read()
        if not file_content:
            return jsonify({"error": "The uploaded file is empty."}), 400
        summary = ai_service.analyze_medical_report(file_content, file.filename)
        # Store report scoped to the specific patient from the form
        patient_name = request.form.get("patient_name") or \
                       (session.get("user") or {}).get("full_name") or "Unknown"
        report = ReportRepository.create_report(
            patient_name=patient_name,
            report_type=file.filename.split('.')[-1].upper(),
            ai_analysis=summary,
            created_at=datetime.now().isoformat()
        )
        return jsonify({"summary": summary, "report": report})
    except ValueError as e:
        logger.warning(f"Validation/analysis warning: {e}")
        return jsonify({"error": str(e)}), 400
    except ConnectionError as e:
        logger.error(f"Ollama connectivity error: {e}")
        return jsonify({"error": str(e)}), 503
    except Exception as e:
        logger.error(f"Error processing document: {e}")
        return jsonify({"error": str(e)}), 500


@socketio.on('new_message')
def handle_new_message(data):
    """No-op — broadcasting handled server-side in api_send_message after DB save."""
    pass


if __name__ == "__main__":
    socketio.run(
        app,
        debug=app.config.get("DEBUG", False),
        host='0.0.0.0',
        port=5000,
        allow_unsafe_werkzeug=True,
        use_reloader=False,
    )
