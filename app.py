import logging
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify

from config import Config
import data_store
import ai_service

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = "super_secret_careconnect_key_123"  # Secret key for session management

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
        connect_patient = (body.get("connect_patient") or "").strip()
        if not relationship:
            raise ValueError("Relationship to patient is required for children signup.")
        profile["relationship"] = relationship
        if connect_patient:
            profile["connect_patient"] = connect_patient

    elif role == "patient":
        age_raw = str(body.get("age") or "").strip()
        blood_group = (body.get("blood_group") or "").strip()
        conditions_raw = (body.get("conditions") or "").strip()
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
        if conditions_raw:
            profile["conditions"] = [item.strip() for item in conditions_raw.split(",") if item.strip()]

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
def children_dashboard():
    session["role"] = "children"
    vitals = {"heart_rate": 72, "blood_pressure": "118/76", "blood_sugar": 95, "bmi": 21.5}
    apts = data_store.get_all_appointments()
    connected_doctor = None
    if apts:
        # Most recent confirmed appointment
        confirmed = [a for a in apts if a.get("status") == "Confirmed"]
        if confirmed:
            doc_name = confirmed[0].get("doctor")
            connected_doctor = data_store.get_doctor_by_name(doc_name)
    return render_template("dashboards/children.html", vitals=vitals, connected_doctor=connected_doctor, title="Children Portal")


@app.route("/dashboard/patient")
def patient_dashboard():
    session["role"] = "patient"
    vitals = {"heart_rate": 72, "blood_pressure": "118/76", "blood_sugar": 95, "bmi": 21.5}
    return render_template("dashboards/patient.html", vitals=vitals, title="Patient Portal")


@app.route("/dashboard/doctor")
def doctor_dashboard():
    session["role"] = "doctor"
    return render_template("dashboards/doctor.html", title="Doctor Portal")


@app.route("/dashboard/hospital-admin")
def hospital_admin_dashboard():
    session["role"] = "admin"
    return render_template("dashboards/hospital_admin.html", title="Admin Overview")


@app.route("/dashboard/diagnostic")
def diagnostic_dashboard():
    session["role"] = "diagnostic"
    return render_template("dashboards/diagnostic.html", title="Lab Terminal")


# --- Children Role Routes ---

@app.route("/children/appointments")
def children_appointments():
    session["role"] = "children"
    patients = data_store.get_all_patients()
    doctors = data_store.get_all_doctors()
    return render_template("children/appointments.html", title="Bookings", patients=patients, doctors=doctors)


@app.route("/children/reports")
def children_reports():
    session["role"] = "children"
    patients = data_store.get_all_patients()
    return render_template("children/reports.html", title="AI Reports", patients=patients)


@app.route("/children/family")
def children_family():
    session["role"] = "children"
    return render_template("children/family.html", title="Family Circle")


@app.route("/children/settings")
def children_settings():
    session["role"] = "children"
    return render_template("children/settings.html", title="Settings")


@app.route("/children/chat")
def children_chat():
    session["role"] = "children"
    apts = data_store.get_all_appointments()
    connected_doctor_name = None
    if apts:
        confirmed = [a for a in apts if a.get("status") == "Confirmed"]
        if confirmed:
            connected_doctor_name = confirmed[0].get("doctor")
    return render_template("children/chat.html", title="Family Chat", connected_doctor=connected_doctor_name)


# --- Patient Role Routes ---

@app.route("/patient/reminders")
def patient_reminders():
    session["role"] = "patient"
    return render_template("patient/reminders.html", title="Reminders")


@app.route("/patient/chat")
def patient_chat():
    session["role"] = "patient"
    return render_template("patient/chat.html", title="Family Chat")


# --- Doctor Role Routes ---

@app.route("/doctor/schedule")
def doctor_schedule():
    session["role"] = "doctor"
    return render_template("doctor/schedule.html", title="Today's Schedule")


@app.route("/doctor/consultations")
def doctor_consultations():
    session["role"] = "doctor"
    return render_template("doctor/consultations.html", title="Consultations")


@app.route("/doctor/video")
def doctor_video():
    session["role"] = "doctor"
    return render_template("video_call.html", title="Video Room")


# --- Hospital Admin Role Routes ---

@app.route("/admin/doctors")
def admin_doctors():
    session["role"] = "admin"
    return render_template("admin/doctors.html", title="Manage Doctors")


@app.route("/admin/appointments")
def admin_appointments():
    session["role"] = "admin"
    return render_template("admin/appointments.html", title="Appointments")


@app.route("/admin/reports")
def admin_reports():
    session["role"] = "admin"
    return render_template("admin/reports.html", title="Hospital Reports")


# --- Diagnostic Role Routes ---

@app.route("/diagnostic/upload")
def upload_results():
    session["role"] = "diagnostic"
    return render_template("diagnostic/upload.html", title="Upload Results")


@app.route("/diagnostic/history")
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
    data_store.log_medicine(med, taken_by="patient")
    flash(f"{med} logged! Your children have been notified.", "success")
    return redirect(url_for("patient_dashboard"))


@app.route("/action/video-call")
def video_call():
    return render_template("video_call.html", title="Video Room")


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
    data_store.add_appointment(patient_name, doctor, department, date, time_str, booked_by="children")
    flash(
        f"Appointment confirmed for {patient_name} with {doctor} on {data_store.format_date(date)}!",
        "success",
    )
    return redirect(request.referrer or url_for("children_appointments"))


@app.route("/action/view-summary/<id>")
def view_summary(id):
    flash(f"Retrieving AI Summary for Report #{id}...", "info")
    return redirect(request.referrer or url_for("children_reports"))


@app.route("/emergency")
def emergency():
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
        user = data_store.register_user(
            full_name=full_name,
            email=email,
            password=password,
            role=role,
            **profile,
        )
        session["role"] = _session_role_for_auth(role)
        session["user"] = {
            "id": user.get("id"),
            "full_name": user.get("full_name"),
            "email": user.get("email"),
            "role": role,
        }
        return jsonify({"user": user, "dashboard": _dashboard_url_for_role(role)}), 201
    except ValueError as e:
        message = str(e)
        lower_message = message.lower()
        if "already exists" in lower_message or "already registered" in lower_message:
            return jsonify({"error": message}), 409
        return jsonify({"error": message}), 400
    except Exception as e:
        logger.error(f"Signup failed: {e}")
        return jsonify({"error": f"Signup failed: {str(e)}"}), 500


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

    user = data_store.authenticate_user(email=email, password=password, role=role)
    if not user:
        return jsonify({"error": "Invalid credentials for this role."}), 401

    session["role"] = _session_role_for_auth(role)
    session["user"] = {
        "id": user.get("id"),
        "full_name": user.get("full_name"),
        "email": user.get("email"),
        "role": role,
    }
    return jsonify({"user": user, "dashboard": _dashboard_url_for_role(role)}), 200


# ---------------------------------------------------------------------------
# Real-Time API Endpoints
# ---------------------------------------------------------------------------

@app.route("/api/chat/messages")
def api_get_messages():
    since = float(request.args.get("since", 0))
    msgs = data_store.get_messages_since(since) if since else data_store.get_all_messages()
    return jsonify(msgs)


@app.route("/api/chat/send", methods=["POST"])
def api_send_message():
    body = request.get_json(force=True)
    sender = body.get("sender", "children")
    sender_name = body.get("sender_name", "Unknown")
    text = body.get("text", "").strip()
    if not text:
        return jsonify({"error": "Empty message"}), 400
    msg = data_store.add_message(sender, sender_name, text)
    return jsonify(msg)


@app.route("/api/appointments")
def api_get_appointments():
    patient_name = request.args.get("patient_name")
    doctor = request.args.get("doctor")

    # If the current session user is a doctor, filter by their name automatically
    if not doctor and session.get("role") == "doctor" and session.get("user"):
        doctor = session["user"].get("full_name")

    return jsonify(data_store.get_all_appointments(patient_name=patient_name, doctor=doctor))


@app.route("/api/appointments/book", methods=["POST"])
def api_book_appointment():
    body = request.get_json(force=True)
    patient_name = (body.get("patient_name") or "").strip()
    doctor = (body.get("doctor") or "").strip()
    date = (body.get("date") or "").strip()

    if not patient_name or not doctor or not date:
        return jsonify({"error": "patient_name, doctor, and date are required"}), 400

    apt = data_store.add_appointment(
        patient_name=patient_name,
        doctor=doctor,
        department=body.get("department", "General"),
        date=date,
        time_str=body.get("time", ""),
        booked_by=body.get("booked_by", "children"),
    )
    return jsonify(apt)


@app.route("/api/notifications")
def api_get_notifications():
    role = request.args.get("role", "children")
    since = float(request.args.get("since", 0))
    notifs = data_store.get_notifications(role, since)
    return jsonify(notifs)


@app.route("/api/notifications/read", methods=["POST"])
def api_mark_read():
    nid = request.get_json(force=True).get("id")
    if nid:
        data_store.mark_read(nid)
    return jsonify({"ok": True})


@app.route("/api/medicine-log")
def api_medicine_log():
    return jsonify(data_store.get_medicine_log())


@app.route("/api/medicine-log/add", methods=["POST"])
def api_add_medicine():
    body = request.get_json(force=True)
    entry = data_store.log_medicine(body.get("medicine", "Medicine"), body.get("taken_by", "patient"))
    return jsonify(entry)


@app.route("/api/consultation-notes")
def api_get_notes():
    return jsonify(data_store.get_consultation_notes())


@app.route("/api/consultation-notes/add", methods=["POST"])
def api_add_note():
    body = request.get_json(force=True)
    note = data_store.add_consultation_note(
        body.get("patient_name", "Patient"),
        body.get("doctor_name", "Doctor"),
        body.get("note", ""),
    )
    return jsonify(note)


@app.route("/api/sos", methods=["POST"])
def api_sos():
    body = request.get_json(force=True)
    alert = data_store.add_sos_alert(
        triggered_by=body.get("triggered_by", "Patient"),
        location=body.get("location", "Unknown"),
    )
    return jsonify(alert)



@app.route("/api/sos/alerts")
def api_sos_alerts():
    return jsonify(data_store.get_sos_alerts())


@app.route("/api/reports")
def api_reports():
    patient_name = request.args.get("patient_name")
    return jsonify(data_store.get_reports(patient_name=patient_name))


@app.route("/api/storage/backend")
def api_storage_backend():
    return jsonify({"backend": data_store.backend_name()})


@app.route("/api/reports/<int:report_id>")
def api_report_by_id(report_id):
    r = data_store.get_report_by_id(report_id)
    if not r:
        return jsonify({"error": f"Report #{report_id} not found"}), 404
    return jsonify(r)


# ---------------------------------------------------------------------------
# Per-Record ID Lookup Endpoints
# ---------------------------------------------------------------------------

@app.route("/api/appointments/<int:appt_id>")
def api_appointment_by_id(appt_id):
    apt = data_store.get_appointment_by_id(appt_id)
    if not apt:
        return jsonify({"error": f"Appointment #{appt_id} not found"}), 404
    return jsonify(apt)


@app.route("/api/notes/<int:note_id>")
def api_note_by_id(note_id):
    note = data_store.get_note_by_id(note_id)
    if not note:
        return jsonify({"error": f"Note #{note_id} not found"}), 404
    return jsonify(note)


@app.route("/api/medicine-log/<int:med_id>")
def api_medicine_entry_by_id(med_id):
    entry = data_store.get_medicine_entry_by_id(med_id)
    if not entry:
        return jsonify({"error": f"Medicine entry #{med_id} not found"}), 404
    return jsonify(entry)


# ---------------------------------------------------------------------------
# Patient Registry API
# ---------------------------------------------------------------------------

@app.route("/api/patients")
def api_get_patients():
    return jsonify(data_store.get_all_patients())


@app.route("/api/patients/<pid>")
def api_patient_by_id(pid):
    p = data_store.get_patient_by_id(pid)
    if not p:
        return jsonify({"error": f"Patient #{pid} not found"}), 404
    # Attach their appointments
    p_copy = dict(p)
    p_copy["appointments"] = data_store.get_all_appointments(patient_name=p["name"])
    p_copy["reports"] = data_store.get_reports(patient_name=p["name"])
    return jsonify(p_copy)


@app.route("/api/patients/register", methods=["POST"])
def api_register_patient():
    body = request.get_json(force=True)
    name = (body.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Patient name is required"}), 400
    patient = data_store.register_patient(
        name=name,
        age=int(body.get("age", 0)),
        gender=body.get("gender", "Unknown"),
        blood_group=body.get("blood_group", "Unknown"),
        phone=body.get("phone", ""),
        address=body.get("address", ""),
        emergency_contact=body.get("emergency_contact", ""),
        conditions=body.get("conditions", []),
        allergies=body.get("allergies", []),
        registered_by=body.get("registered_by", _current_role()),
    )
    return jsonify(patient), 201


@app.route("/api/doctor/start-call", methods=["POST"])
def api_doctor_start_call():
    body = request.get_json(force=True)
    patient_name = body.get("patient_name", "Patient")
    doctor_name = session.get("user", {}).get("full_name") or "Your Doctor"

    # Notify children and patient
    data_store.add_notification("children", "Video Consultation Request", f"{doctor_name} is starting a video consultation for {patient_name}.", "primary")
    data_store.add_notification("patient", "Video Consultation Starting", f"{doctor_name} is online for your consultation.", "primary")

    return jsonify({"room_url": "/doctor/video"})


@app.route("/api/patients/<pid>/vitals", methods=["POST"])
def api_update_vitals(pid):
    vitals = request.get_json(force=True)
    updated = data_store.update_patient_vitals(pid, vitals)
    if not updated:
        return jsonify({"error": f"Patient #{pid} not found"}), 404
    return jsonify(updated)


# Patient detail page (Doctor portal)
@app.route("/doctor/patient/<pid>")
def doctor_view_patient(pid):
    p = data_store.get_patient_by_id(pid)
    if not p:
        flash(f"Patient #{pid} not found in the registry.", "danger")
        return redirect(url_for("doctor_dashboard"))
    appts = data_store.get_all_appointments(patient_name=p["name"])
    notes = [n for n in data_store.get_consultation_notes() if n.get("patient_name", "").lower() == p["name"].lower()]
    reps  = data_store.get_reports(patient_name=p["name"])
    session["role"] = "doctor"
    return render_template("doctor/patient_detail.html", patient=p, appointments=appts, notes=notes, reports=reps, title=f"Patient #{pid}")


# ---------------------------------------------------------------------------
# Doctor Registry API
# ---------------------------------------------------------------------------

@app.route("/api/doctors")
def api_get_doctors():
    return jsonify(data_store.get_all_doctors())


@app.route("/api/doctors/<did>")
def api_doctor_by_id(did):
    d = data_store.get_doctor_by_id(did)
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
    doc = data_store.register_doctor(
        name=name, specialty=specialty,
        phone=body.get("phone", ""), availability=body.get("availability", "Mon-Fri")
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
        report  = data_store.add_report(
            filename=file.filename,
            summary=summary,
            uploaded_by=request.form.get("uploaded_by", _current_role()),
            patient_name=request.form.get("patient_name", "George Smith"),
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



if __name__ == "__main__":
    # Using conditional debug so it stays safe for real deployments
    app.run(debug=app.config.get("DEBUG", False), port=5000)

