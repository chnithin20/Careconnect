"""CareConnect data store with PostgreSQL backend (Supabase) and in-memory fallback."""

import logging
import re
import time
from datetime import datetime
from werkzeug.security import check_password_hash, generate_password_hash

try:
    from database import (
        get_db, init_db, User, Patient, Doctor, Appointment, Message, 
        Notification, ConsultationNote, MedicineLog, SOSAlert, Report
    )
    _db_import_error = None
except Exception as exc:
    get_db = None
    init_db = None
    User = Patient = Doctor = Appointment = Message = None
    Notification = ConsultationNote = MedicineLog = SOSAlert = Report = None
    _db_import_error = exc

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------
def _now_str():
    return datetime.now().strftime("%I:%M %p")


def _ts():
    return time.time()


def format_date(date_str: str) -> str:
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        return d.strftime("%b %d, %Y")
    except Exception:
        return date_str


def _parse_appointment_datetime(date_str: str, time_str: str):
    if not date_str:
        return None
    clean_time = (time_str or "").strip()
    candidates = [f"{date_str} {clean_time}".strip()]
    if not clean_time:
        candidates.append(date_str)

    for candidate in candidates:
        for pattern in ("%Y-%m-%d %H:%M", "%Y-%m-%d %I:%M %p", "%Y-%m-%d"):
            try:
                return datetime.strptime(candidate, pattern)
            except Exception:
                continue
    return None


class InMemoryStore:
    """Fallback store when PostgreSQL is unavailable."""

    def __init__(self):
        self.notifications = []
        self.messages = [
            {
                "id": 1,
                "sender": "children",
                "sender_name": "Emily (Daughter)",
                "text": "Hi Dad! Did you take your medicine this morning?",
                "timestamp": "09:12 AM",
                "ts": _ts() - 3600,
            },
            {
                "id": 2,
                "sender": "patient",
                "sender_name": "Dad (Patient)",
                "text": "Yes! Logged it in the app. Feeling great today!",
                "timestamp": "09:15 AM",
                "ts": _ts() - 3540,
            },
            {
                "id": 3,
                "sender": "children",
                "sender_name": "Emily (Daughter)",
                "text": "Wonderful. I will call you this evening.",
                "timestamp": "09:16 AM",
                "ts": _ts() - 3480,
            },
        ]
        self.appointments = [
            {
                "id": 1,
                "patient_name": "George Smith",
                "doctor": "Dr. Sarah Jenkins",
                "department": "Cardiology",
                "date": "2026-04-07",
                "time": "10:00",
                "status": "Confirmed",
                "booked_by": "children",
                "created_at": "09:00 AM",
                "created_ts": _ts() - 7200,
            },
            {
                "id": 2,
                "patient_name": "George Smith",
                "doctor": "Dr. Michael Chen",
                "department": "Neurology",
                "date": "2026-04-11",
                "time": "14:30",
                "status": "Pending",
                "booked_by": "children",
                "created_at": "09:05 AM",
                "created_ts": _ts() - 6900,
            },
        ]
        self.medicine_log = []
        self.consultation_notes = []
        self.sos_alerts = []
        self.reports = []
        self.patients = [
            {
                "id": "CC001",
                "name": "George Smith",
                "age": 68,
                "gender": "Male",
                "blood_group": "B+",
                "phone": "+1-555-0101",
                "address": "Park Avenue, NY",
                "emergency_contact": "Emily Smith (+1-555-0111)",
                "conditions": ["Hypertension"],
                "allergies": ["Penicillin"],
                "registered_by": "children",
                "registered_at": _now_str(),
                "vitals": {
                    "heart_rate": 72,
                    "blood_pressure": "118/76",
                    "blood_sugar": 95,
                    "bmi": 21.5,
                },
            }
        ]
        self.doctors = [
            {
                "id": "DR001",
                "name": "Dr. Sarah Jenkins",
                "specialty": "Cardiology",
                "phone": "+1-555-2101",
                "availability": "Mon-Fri 09:00-16:00",
                "registered_at": _now_str(),
            },
            {
                "id": "DR002",
                "name": "Dr. Michael Chen",
                "specialty": "Neurology",
                "phone": "+1-555-2102",
                "availability": "Mon-Fri 10:00-17:00",
                "registered_at": _now_str(),
            },
        ]
        self.users = []

        self._next_notif_id = 1
        self._next_msg_id = 4
        self._next_appt_id = 3
        self._next_med_id = 1
        self._next_note_id = 1
        self._next_sos_id = 1
        self._next_report_id = 1
        self._next_patient_seq = 2
        self._next_doctor_seq = 3
        self._next_user_id = 1

    def add_notification(self, role: str, title: str, body: str, kind: str = "info"):
        doc = {
            "id": self._next_notif_id,
            "role": role,
            "title": title,
            "body": body,
            "kind": kind,
            "timestamp": _now_str(),
            "ts": _ts(),
            "read": False,
        }
        self.notifications.insert(0, doc)
        self._next_notif_id += 1
        return doc

    def get_notifications(self, role: str, since: float = 0):
        return [
            n
            for n in self.notifications
            if (n["role"] == role or n["role"] == "all") and n["ts"] > since
        ]

    def mark_read(self, notif_id):
        try:
            notif_id = int(notif_id)
        except Exception:
            return
        for n in self.notifications:
            if n["id"] == notif_id:
                n["read"] = True

    def add_message(self, sender: str, sender_name: str, text: str):
        clean_sender = (sender or "children").strip().lower()
        clean_name = (sender_name or "Unknown").strip()
        clean_text = (text or "").strip()
        msg = {
            "id": self._next_msg_id,
            "sender": clean_sender,
            "sender_name": clean_name,
            "text": clean_text,
            "timestamp": _now_str(),
            "ts": _ts(),
        }
        self.messages.append(msg)
        self._next_msg_id += 1

        if clean_sender in ("children", "patient"):
            other = "patient" if clean_sender == "children" else "children"
            preview = clean_text[:80] + ("..." if len(clean_text) > 80 else "")
            self.add_notification(other, f"New message from {clean_name}", preview, "info")
        return msg

    def get_messages_since(self, ts: float):
        return [m for m in self.messages if m["ts"] > ts]

    def get_all_messages(self):
        return list(self.messages)

    def add_appointment(self, patient_name, doctor, department, date, time_str, booked_by="children"):
        clean_patient = (patient_name or "Unknown Patient").strip()
        clean_doctor = (doctor or "Assigned Doctor").strip()
        clean_department = (department or "General").strip()
        clean_date = (date or "").strip()
        clean_time = (time_str or "").strip()
        clean_booked_by = (booked_by or "children").strip().lower()

        apt = {
            "id": self._next_appt_id,
            "patient_name": clean_patient,
            "doctor": clean_doctor,
            "department": clean_department,
            "date": clean_date,
            "time": clean_time,
            "status": "Pending",
            "booked_by": clean_booked_by,
            "created_at": _now_str(),
            "created_ts": _ts(),
        }
        self.appointments.append(apt)
        self._next_appt_id += 1

        date_str = format_date(clean_date)
        time_part = clean_time or "TBD"
        self.add_notification("patient", "New Appointment Booked", f"{clean_doctor} ({clean_department}) on {date_str} at {time_part}", "success")
        self.add_notification("doctor", "New Patient Appointment", f"Patient: {clean_patient} | Booked by: {clean_booked_by} | {clean_department} on {date_str} at {time_part}", "info")
        self.add_notification("admin", "Appointment Registered", f"{clean_patient} -> {clean_doctor} on {date_str} ({clean_booked_by})", "info")
        if clean_booked_by != "children":
            self.add_notification("children", "Parent Appointment Update", f"{clean_patient} booked with {clean_doctor} on {date_str} at {time_part}", "info")

        return apt

    def get_all_appointments(self, patient_name: str = None, doctor: str = None):
        result = list(self.appointments)

        if patient_name:
            expected = patient_name.strip().lower()
            result = [a for a in result if a.get("patient_name", "").strip().lower() == expected]

        if doctor:
            expected = doctor.strip().lower()
            result = [a for a in result if a.get("doctor", "").strip().lower() == expected]

        return sorted(
            result,
            key=lambda a: (
                _parse_appointment_datetime(a.get("date", ""), a.get("time", "")) or datetime.max,
                a.get("id", 0),
            ),
        )

    def log_medicine(self, medicine_name: str, taken_by: str = "patient"):
        clean_medicine = (medicine_name or "Medicine").strip()
        clean_taken_by = (taken_by or "patient").strip().lower()
        entry = {
            "id": self._next_med_id,
            "medicine": clean_medicine,
            "taken_by": clean_taken_by,
            "timestamp": _now_str(),
            "ts": _ts(),
        }
        self.medicine_log.append(entry)
        self._next_med_id += 1
        self.add_notification("children", "Medicine Taken", f"Your parent took: {clean_medicine} at {entry['timestamp']}", "success")
        return entry

    def get_medicine_log(self):
        return list(reversed(self.medicine_log))

    def get_doctor_by_name(self, name: str):
        if not name:
            return None
        target = name.strip().lower()
        for d in self.doctors:
            if d.get("name", "").strip().lower() == target:
                return d
        return None

    def add_consultation_note(self, patient_name: str, doctor_name: str, note: str):
        clean_patient = (patient_name or "Patient").strip()
        clean_doctor = (doctor_name or "Doctor").strip()
        clean_note = (note or "").strip()
        n = {
            "id": self._next_note_id,
            "patient_name": clean_patient,
            "doctor_name": clean_doctor,
            "note": clean_note,
            "timestamp": _now_str(),
            "ts": _ts(),
        }
        self.consultation_notes.insert(0, n)
        self._next_note_id += 1
        self.add_notification("patient", "Doctor's Note", f"{clean_doctor}: {clean_note[:80]}", "info")
        self.add_notification("children", "Doctor's Note for Parent", f"{clean_doctor} for {clean_patient}: {clean_note[:80]}", "info")
        return n

    def get_consultation_notes(self):
        return list(self.consultation_notes)

    def add_sos_alert(self, triggered_by: str, location: str = "Unknown"):
        clean_triggered_by = (triggered_by or "Patient").strip()
        clean_location = (location or "Unknown").strip()
        alert = {
            "id": self._next_sos_id,
            "triggered_by": clean_triggered_by,
            "location": clean_location,
            "timestamp": _now_str(),
            "ts": _ts(),
        }
        self.sos_alerts.insert(0, alert)
        self._next_sos_id += 1

        self.add_notification("admin", "SOS ALERT", f"SOS triggered by {clean_triggered_by}. Location: {clean_location}", "danger")
        self.add_notification("children", "SOS ALERT", f"Your parent triggered an emergency SOS at {alert['timestamp']}.", "danger")
        self.add_notification("doctor", "Patient SOS", f"Emergency triggered by {clean_triggered_by}.", "danger")
        return alert

    def get_sos_alerts(self):
        return list(self.sos_alerts)

    def add_report(self, filename: str, summary: str, uploaded_by: str = "children", patient_name: str = "George Smith"):
        clean_filename = (filename or "report.txt").strip()
        clean_summary = (summary or "").strip()
        clean_uploaded_by = (uploaded_by or "children").strip().lower()
        clean_patient = (patient_name or "Unknown Patient").strip()

        report = {
            "id": self._next_report_id,
            "filename": clean_filename,
            "patient_name": clean_patient,
            "summary": clean_summary,
            "uploaded_by": clean_uploaded_by,
            "status": "Analyzed",
            "timestamp": _now_str(),
            "ts": _ts(),
        }
        self.reports.insert(0, report)
        self._next_report_id += 1

        self.add_notification("patient", "New AI Report Summary", f"{clean_filename} analyzed and shared to your portal.", "info")
        self.add_notification("doctor", "New AI Report Summary", f"{clean_patient} report analyzed: {clean_filename}", "info")
        self.add_notification("admin", "Report Analysis Completed", f"{clean_filename} analyzed for {clean_patient}", "success")
        return report

    def get_reports(self, patient_name: str = None):
        result = list(self.reports)
        if patient_name:
            expected = patient_name.strip().lower()
            result = [r for r in result if r.get("patient_name", "").strip().lower() == expected]
        return result

    def get_report_by_id(self, report_id: int):
        for report in self.reports:
            if report.get("id") == report_id:
                return dict(report)
        return None

    def get_appointment_by_id(self, appt_id: int):
        for apt in self.appointments:
            if apt.get("id") == appt_id:
                return dict(apt)
        return None

    def get_note_by_id(self, note_id: int):
        for note in self.consultation_notes:
            if note.get("id") == note_id:
                return dict(note)
        return None

    def get_medicine_entry_by_id(self, med_id: int):
        for entry in self.medicine_log:
            if entry.get("id") == med_id:
                return dict(entry)
        return None

    def get_all_patients(self):
        return list(self.patients)

    def get_patient_by_id(self, pid: str):
        for patient in self.patients:
            if patient.get("id") == pid:
                return dict(patient)
        return None

    def register_patient(
        self,
        name: str,
        age: int,
        gender: str,
        blood_group: str,
        phone: str,
        address: str,
        emergency_contact: str,
        conditions=None,
        allergies=None,
        registered_by: str = "children",
    ):
        pid = f"CC{self._next_patient_seq:03d}"
        self._next_patient_seq += 1
        patient = {
            "id": pid,
            "name": name,
            "age": age,
            "gender": gender,
            "blood_group": blood_group,
            "phone": phone,
            "address": address,
            "emergency_contact": emergency_contact,
            "conditions": conditions or [],
            "allergies": allergies or [],
            "registered_by": registered_by,
            "registered_at": _now_str(),
            "vitals": {},
        }
        self.patients.append(patient)
        self.add_notification("doctor", "New Patient Registered", f"{name} ({pid}) added to registry.", "info")
        self.add_notification("admin", "Patient Registration", f"{name} ({pid}) registered by {registered_by}.", "success")
        return dict(patient)

    def update_patient_vitals(self, pid: str, vitals: dict):
        for patient in self.patients:
            if patient.get("id") == pid:
                patient.setdefault("vitals", {})
                patient["vitals"].update(vitals or {})
                patient["vitals_updated_at"] = _now_str()
                self.add_notification("children", "Vitals Updated", f"{patient.get('name')} vitals were updated.", "info")
                return dict(patient)
        return None

    def get_all_doctors(self):
        return list(self.doctors)

    def get_doctor_by_id(self, did: str):
        for doctor in self.doctors:
            if doctor.get("id") == did:
                return dict(doctor)
        return None

    def register_doctor(self, name: str, specialty: str, phone: str = "", availability: str = "Mon-Fri"):
        did = f"DR{self._next_doctor_seq:03d}"
        self._next_doctor_seq += 1
        doctor = {
            "id": did,
            "name": name,
            "specialty": specialty,
            "phone": phone,
            "availability": availability,
            "registered_at": _now_str(),
        }
        self.doctors.append(doctor)
        self.add_notification("admin", "Doctor Added", f"{name} ({specialty}) added to registry.", "success")
        return dict(doctor)

    def register_user(self, full_name: str, email: str, password: str, role: str, **kwargs):
        name = (full_name or "").strip()
        email_raw = (email or "").strip()
        role_raw = (role or "").strip().lower()
        email_norm = email_raw.lower()
        email_role_key = f"{email_norm}::{role_raw}"

        if any(u.get("email_role_key") == email_role_key for u in self.users):
            raise ValueError("An account already exists for this email in the selected role.")

        user = {
            "id": self._next_user_id,
            "full_name": name,
            "email": email_raw,
            "email_norm": email_norm,
            "role": role_raw,
            "email_role_key": email_role_key,
            "password_hash": generate_password_hash(password),
            "created_at": _now_str(),
            "ts": _ts(),
            "active": True,
            **kwargs,
        }
        self.users.append(user)
        self._next_user_id += 1

        if role_raw == "doctor":
            self.register_doctor(name=name, specialty=kwargs.get("specialty", "General"), phone=kwargs.get("phone", ""), availability=kwargs.get("availability", "Mon-Fri"))
        elif role_raw == "patient":
            if hasattr(self, 'register_patient'):
                self.register_patient(name=name, age=kwargs.get("age", 60), gender=kwargs.get("gender", "Other"), phone=kwargs.get("phone", ""))

        self.add_notification("admin", "New User Signup", f"{name} registered as {role_raw}.", "info")
        return {
            "id": user["id"],
            "full_name": user["full_name"],
            "email": user["email"],
            "role": user["role"],
            "created_at": user["created_at"],
        }

    def authenticate_user(self, email: str, password: str, role: str):
        email_norm = (email or "").strip().lower()
        role_raw = (role or "").strip().lower()
        email_role_key = f"{email_norm}::{role_raw}"
        user = next((u for u in self.users if u.get("email_role_key") == email_role_key), None)
        if not user:
            return None
        if not check_password_hash(user.get("password_hash", ""), password or ""):
            return None
        return {
            "id": user["id"],
            "full_name": user["full_name"],
            "email": user["email"],
            "role": user["role"],
            "created_at": user["created_at"],
        }


class PostgreSQLStore:
    """PostgreSQL-backed store using SQLAlchemy."""

    def __init__(self):
        if get_db is None:
            raise RuntimeError(f"Database dependencies unavailable: {_db_import_error}")

        # Initialize database
        if not init_db():
            raise RuntimeError("Failed to initialize database")

        self.db = get_db()
        self._seed_defaults_if_empty()

    def _public(self, obj):
        """Convert SQLAlchemy object to dict."""
        if not obj:
            return None
        if isinstance(obj, dict):
            return obj
        return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}

    def _seed_defaults_if_empty(self):
        """Seed default data if tables are empty."""
        try:
            # Check and seed messages
            if self.db.query(Message).count() == 0:
                now = _ts()
                messages = [
                    Message(sender="children", sender_name="Emily (Daughter)", text="Hi Dad! Did you take your medicine this morning?", timestamp="09:12 AM", ts=now - 3600),
                    Message(sender="patient", sender_name="Dad (Patient)", text="Yes! Logged it in the app. Feeling great today!", timestamp="09:15 AM", ts=now - 3540),
                    Message(sender="children", sender_name="Emily (Daughter)", text="Wonderful. I will call you this evening.", timestamp="09:16 AM", ts=now - 3480),
                ]
                self.db.add_all(messages)
                self.db.commit()

            # Check and seed appointments
            if self.db.query(Appointment).count() == 0:
                appointments = [
                    Appointment(patient_name="George Smith", doctor="Dr. Sarah Jenkins", department="Cardiology", date="2026-04-07", time="10:00", status="Confirmed", booked_by="children", created_at="09:00 AM", created_ts=_ts() - 7200),
                    Appointment(patient_name="George Smith", doctor="Dr. Michael Chen", department="Neurology", date="2026-04-11", time="14:30", status="Pending", booked_by="children", created_at="09:05 AM", created_ts=_ts() - 6900),
                ]
                self.db.add_all(appointments)
                self.db.commit()

            # Check and seed patients
            if self.db.query(Patient).count() == 0:
                patient = Patient(
                    id="CC001", name="George Smith", age=68, gender="Male", blood_group="B+",
                    phone="+1-555-0101", address="Park Avenue, NY", emergency_contact="Emily Smith (+1-555-0111)",
                    conditions=["Hypertension"], allergies=["Penicillin"], registered_by="children",
                    registered_at=_now_str(), vitals={"heart_rate": 72, "blood_pressure": "118/76", "blood_sugar": 95, "bmi": 21.5}
                )
                self.db.add(patient)
                self.db.commit()

            # Check and seed doctors
            if self.db.query(Doctor).count() == 0:
                doctors = [
                    Doctor(id="DR001", name="Dr. Sarah Jenkins", specialty="Cardiology", phone="+1-555-2101", availability="Mon-Fri 09:00-16:00", registered_at=_now_str()),
                    Doctor(id="DR002", name="Dr. Michael Chen", specialty="Neurology", phone="+1-555-2102", availability="Mon-Fri 10:00-17:00", registered_at=_now_str()),
                ]
                self.db.add_all(doctors)
                self.db.commit()
        except Exception as e:
            logger.error(f"Error seeding default data: {e}")
            self.db.rollback()

    def add_notification(self, role: str, title: str, body: str, kind: str = "info"):
        notif = Notification(role=role, title=title, body=body, kind=kind, timestamp=_now_str(), ts=_ts(), read=False)
        self.db.add(notif)
        self.db.commit()
        return self._public(notif)

    def get_notifications(self, role: str, since: float = 0):
        query = self.db.query(Notification).filter((Notification.role == role) | (Notification.role == "all"), Notification.ts > since).order_by(Notification.ts.desc())
        return [self._public(n) for n in query.all()]

    def mark_read(self, notif_id):
        try:
            notif_id = int(notif_id)
            notif = self.db.query(Notification).filter_by(id=notif_id).first()
            if notif:
                notif.read = True
                self.db.commit()
        except Exception:
            pass

    def add_message(self, sender: str, sender_name: str, text: str):
        clean_sender = (sender or "children").strip().lower()
        clean_name = (sender_name or "Unknown").strip()
        clean_text = (text or "").strip()

        msg = Message(sender=clean_sender, sender_name=clean_name, text=clean_text, timestamp=_now_str(), ts=_ts())
        self.db.add(msg)
        self.db.commit()

        if clean_sender in ("children", "patient"):
            other = "patient" if clean_sender == "children" else "children"
            preview = clean_text[:80] + ("..." if len(clean_text) > 80 else "")
            self.add_notification(other, f"New message from {clean_name}", preview, "info")

        return self._public(msg)

    def get_messages_since(self, ts: float):
        query = self.db.query(Message).filter(Message.ts > ts).order_by(Message.ts.asc())
        return [self._public(m) for m in query.all()]

    def get_all_messages(self):
        query = self.db.query(Message).order_by(Message.ts.asc())
        return [self._public(m) for m in query.all()]

    def add_appointment(self, patient_name, doctor, department, date, time_str, booked_by="children"):
        clean_patient = (patient_name or "Unknown Patient").strip()
        clean_doctor = (doctor or "Assigned Doctor").strip()
        clean_department = (department or "General").strip()
        clean_date = (date or "").strip()
        clean_time = (time_str or "").strip()
        clean_booked_by = (booked_by or "children").strip().lower()

        apt = Appointment(patient_name=clean_patient, doctor=clean_doctor, department=clean_department, date=clean_date, time=clean_time, status="Pending", booked_by=clean_booked_by, created_at=_now_str(), created_ts=_ts())
        self.db.add(apt)
        self.db.commit()

        date_str = format_date(clean_date)
        time_part = clean_time or "TBD"
        self.add_notification("patient", "New Appointment Booked", f"{clean_doctor} ({clean_department}) on {date_str} at {time_part}", "success")
        self.add_notification("doctor", "New Patient Appointment", f"Patient: {clean_patient} | Booked by: {clean_booked_by} | {clean_department} on {date_str} at {time_part}", "info")
        self.add_notification("admin", "Appointment Registered", f"{clean_patient} -> {clean_doctor} on {date_str} ({clean_booked_by})", "info")
        if clean_booked_by != "children":
            self.add_notification("children", "Parent Appointment Update", f"{clean_patient} booked with {clean_doctor} on {date_str} at {time_part}", "info")

        return self._public(apt)

    def get_all_appointments(self, patient_name: str = None, doctor: str = None):
        query = self.db.query(Appointment)
        if patient_name:
            query = query.filter(Appointment.patient_name.ilike(f"%{patient_name.strip()}%"))
        if doctor:
            query = query.filter(Appointment.doctor.ilike(f"%{doctor.strip()}%"))

        docs = [self._public(doc) for doc in query.all()]
        return sorted(docs, key=lambda a: (_parse_appointment_datetime(a.get("date", ""), a.get("time", "")) or datetime.max, a.get("id", 0)))

    def log_medicine(self, medicine_name: str, taken_by: str = "patient"):
        clean_medicine = (medicine_name or "Medicine").strip()
        clean_taken_by = (taken_by or "patient").strip().lower()
        entry = MedicineLog(medicine=clean_medicine, taken_by=clean_taken_by, timestamp=_now_str(), ts=_ts())
        self.db.add(entry)
        self.db.commit()
        self.add_notification("children", "Medicine Taken", f"Your parent took: {clean_medicine} at {entry.timestamp}", "success")
        return self._public(entry)

    def get_medicine_log(self):
        query = self.db.query(MedicineLog).order_by(MedicineLog.ts.desc())
        return [self._public(doc) for doc in query.all()]

    def add_consultation_note(self, patient_name: str, doctor_name: str, note: str):
        clean_patient = (patient_name or "Patient").strip()
        clean_doctor = (doctor_name or "Doctor").strip()
        clean_note = (note or "").strip()

        n = ConsultationNote(patient_name=clean_patient, doctor_name=clean_doctor, note=clean_note, timestamp=_now_str(), ts=_ts())
        self.db.add(n)
        self.db.commit()
        self.add_notification("patient", "Doctor's Note", f"{clean_doctor}: {clean_note[:80]}", "info")
        self.add_notification("children", "Doctor's Note for Parent", f"{clean_doctor} for {clean_patient}: {clean_note[:80]}", "info")
        return self._public(n)

    def get_consultation_notes(self):
        query = self.db.query(ConsultationNote).order_by(ConsultationNote.ts.desc())
        return [self._public(doc) for doc in query.all()]

    def add_sos_alert(self, triggered_by: str, location: str = "Unknown"):
        clean_triggered_by = (triggered_by or "Patient").strip()
        clean_location = (location or "Unknown").strip()
        alert = SOSAlert(triggered_by=clean_triggered_by, location=clean_location, timestamp=_now_str(), ts=_ts())
        self.db.add(alert)
        self.db.commit()

        self.add_notification("admin", "SOS ALERT", f"SOS triggered by {clean_triggered_by}. Location: {clean_location}", "danger")
        self.add_notification("children", "SOS ALERT", f"Your parent triggered an emergency SOS at {alert.timestamp}.", "danger")
        self.add_notification("doctor", "Patient SOS", f"Emergency triggered by {clean_triggered_by}.", "danger")
        return self._public(alert)

    def get_sos_alerts(self):
        query = self.db.query(SOSAlert).order_by(SOSAlert.ts.desc())
        return [self._public(doc) for doc in query.all()]

    def add_report(self, filename: str, summary: str, uploaded_by: str = "children", patient_name: str = "George Smith"):
        clean_filename = (filename or "report.txt").strip()
        clean_summary = (summary or "").strip()
        clean_uploaded_by = (uploaded_by or "children").strip().lower()
        clean_patient = (patient_name or "Unknown Patient").strip()

        report = Report(filename=clean_filename, patient_name=clean_patient, summary=clean_summary, uploaded_by=clean_uploaded_by, status="Analyzed", timestamp=_now_str(), ts=_ts())
        self.db.add(report)
        self.db.commit()

        self.add_notification("patient", "New AI Report Summary", f"{clean_filename} analyzed and shared to your portal.", "info")
        self.add_notification("doctor", "New AI Report Summary", f"{clean_patient} report analyzed: {clean_filename}", "info")
        self.add_notification("admin", "Report Analysis Completed", f"{clean_filename} analyzed for {clean_patient}", "success")
        return self._public(report)

    def get_reports(self, patient_name: str = None):
        query = self.db.query(Report)
        if patient_name:
            query = query.filter(Report.patient_name.ilike(f"%{patient_name.strip()}%"))
        return [self._public(doc) for doc in query.order_by(Report.ts.desc()).all()]

    def get_doctor_by_name(self, name: str):
        if not name:
            return None
        target = name.strip()
        doc = self.db.query(Doctor).filter(Doctor.name.ilike(f"%{target}%")).first()
        return self._public(doc) if doc else None

    def get_report_by_id(self, report_id: int):
        return self._public(self.db.query(Report).filter_by(id=int(report_id)).first())

    def get_appointment_by_id(self, appt_id: int):
        return self._public(self.db.query(Appointment).filter_by(id=int(appt_id)).first())

    def get_note_by_id(self, note_id: int):
        return self._public(self.db.query(ConsultationNote).filter_by(id=int(note_id)).first())

    def get_medicine_entry_by_id(self, med_id: int):
        return self._public(self.db.query(MedicineLog).filter_by(id=int(med_id)).first())

    def get_all_patients(self):
        query = self.db.query(Patient).order_by(Patient.id.asc())
        return [self._public(doc) for doc in query.all()]

    def get_patient_by_id(self, pid: str):
        return self._public(self.db.query(Patient).filter_by(id=pid).first())

    def register_patient(self, name: str, age: int, gender: str, blood_group: str, phone: str, address: str, emergency_contact: str, conditions=None, allergies=None, registered_by: str = "children"):
        # Generate next patient ID
        last_patient = self.db.query(Patient).order_by(Patient.id.desc()).first()
        if last_patient and last_patient.id.startswith("CC"):
            try:
                next_num = int(last_patient.id[2:]) + 1
            except:
                next_num = 2
        else:
            next_num = 2
        pid = f"CC{next_num:03d}"

        patient = Patient(id=pid, name=name, age=age, gender=gender, blood_group=blood_group, phone=phone, address=address, emergency_contact=emergency_contact, conditions=conditions or [], allergies=allergies or [], registered_by=registered_by, registered_at=_now_str(), vitals={})
        self.db.add(patient)
        self.db.commit()
        self.add_notification("doctor", "New Patient Registered", f"{name} ({pid}) added to registry.", "info")
        self.add_notification("admin", "Patient Registration", f"{name} ({pid}) registered by {registered_by}.", "success")
        return self._public(patient)

    def update_patient_vitals(self, pid: str, vitals: dict):
        patient = self.db.query(Patient).filter_by(id=pid).first()
        if not patient:
            return None
        patient.vitals = vitals or {}
        patient.vitals_updated_at = _now_str()
        self.db.commit()
        self.add_notification("children", "Vitals Updated", f"{patient.name} vitals were updated.", "info")
        return self._public(patient)

    def get_all_doctors(self):
        query = self.db.query(Doctor).order_by(Doctor.id.asc())
        return [self._public(doc) for doc in query.all()]

    def get_doctor_by_id(self, did: str):
        return self._public(self.db.query(Doctor).filter_by(id=did).first())

    def register_doctor(self, name: str, specialty: str, phone: str = "", availability: str = "Mon-Fri"):
        # Generate next doctor ID
        last_doctor = self.db.query(Doctor).order_by(Doctor.id.desc()).first()
        if last_doctor and last_doctor.id.startswith("DR"):
            try:
                next_num = int(last_doctor.id[2:]) + 1
            except:
                next_num = 3
        else:
            next_num = 3
        did = f"DR{next_num:03d}"

        doctor = Doctor(id=did, name=name, specialty=specialty, phone=phone, availability=availability, registered_at=_now_str())
        self.db.add(doctor)
        self.db.commit()
        self.add_notification("admin", "Doctor Added", f"{name} ({specialty}) added to registry.", "success")
        return self._public(doctor)

    def register_user(self, full_name: str, email: str, password: str, role: str, **kwargs):
        name = (full_name or "").strip()
        email_raw = (email or "").strip()
        role_raw = (role or "").strip().lower()
        email_norm = email_raw.lower()
        email_role_key = f"{email_norm}::{role_raw}"

        if self.db.query(User).filter_by(email_role_key=email_role_key).first():
            raise ValueError("An account already exists for this email in the selected role.")

        user = User(
            full_name=name, email=email_raw, email_norm=email_norm, role=role_raw, email_role_key=email_role_key,
            password_hash=generate_password_hash(password), created_at=_now_str(), ts=_ts(), active=True,
            specialty=kwargs.get("specialty"), phone=kwargs.get("phone"), availability=kwargs.get("availability"),
            age=kwargs.get("age"), gender=kwargs.get("gender"), blood_group=kwargs.get("blood_group"),
            medical_license_id=kwargs.get("medical_license_id"), relationship=kwargs.get("relationship"),
            hospital_name=kwargs.get("hospital_name"), employee_id=kwargs.get("employee_id"),
            lab_name=kwargs.get("lab_name"), location=kwargs.get("location")
        )
        self.db.add(user)
        self.db.commit()
        self.add_notification("admin", "New User Signup", f"{name} registered as {role_raw}.", "info")

        # Automatically link to role-specific registries
        if role_raw == "doctor":
            self.register_doctor(name=name, specialty=kwargs.get("specialty", "General"), phone=kwargs.get("phone", ""), availability=kwargs.get("availability", "Mon-Fri"))
        elif role_raw == "patient":
            self.register_patient(name=name, age=kwargs.get("age", 60), gender=kwargs.get("gender", "Other"), phone=kwargs.get("phone", ""), address=kwargs.get("address", ""), blood_group=kwargs.get("blood_group", ""), emergency_contact=kwargs.get("emergency_contact", ""))

        return {
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "role": user.role,
            "created_at": user.created_at,
        }

    def authenticate_user(self, email: str, password: str, role: str):
        email_norm = (email or "").strip().lower()
        role_raw = (role or "").strip().lower()
        email_role_key = f"{email_norm}::{role_raw}"
        user = self.db.query(User).filter_by(email_role_key=email_role_key).first()
        if not user:
            return None
        if not check_password_hash(user.password_hash or "", password or ""):
            return None
        return {
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "role": user.role,
            "created_at": user.created_at,
        }


def _build_store():
    if get_db is None:
        if _db_import_error:
            logger.warning("PostgreSQL backend unavailable (%s). Falling back to in-memory store.", _db_import_error)
        else:
            logger.warning("PostgreSQL backend unavailable. Falling back to in-memory store.")
        return InMemoryStore(), "memory"

    try:
        store = PostgreSQLStore()
        logger.info("Using PostgreSQL backend (Supabase) for data persistence.")
        return store, "postgres"
    except Exception as exc:
        logger.warning("Failed to initialize PostgreSQL backend (%s). Falling back to in-memory store.", exc)
        return InMemoryStore(), "memory"


_STORE, BACKEND = _build_store()


# ---------------------------------------------------------------------------
# Public module API used by app.py
# ---------------------------------------------------------------------------
def backend_name() -> str:
    return BACKEND


def add_notification(role: str, title: str, body: str, kind: str = "info"):
    return _STORE.add_notification(role, title, body, kind)


def get_notifications(role: str, since: float = 0):
    return _STORE.get_notifications(role, since)


def mark_read(notif_id):
    return _STORE.mark_read(notif_id)


def add_message(sender: str, sender_name: str, text: str):
    return _STORE.add_message(sender, sender_name, text)


def get_messages_since(ts: float):
    return _STORE.get_messages_since(ts)


def get_all_messages():
    return _STORE.get_all_messages()


def add_appointment(patient_name, doctor, department, date, time_str, booked_by="children"):
    return _STORE.add_appointment(patient_name, doctor, department, date, time_str, booked_by)


def get_all_appointments(patient_name: str = None, doctor: str = None):
    return _STORE.get_all_appointments(patient_name, doctor)


def log_medicine(medicine_name: str, taken_by: str = "patient"):
    return _STORE.log_medicine(medicine_name, taken_by)


def get_medicine_log():
    return _STORE.get_medicine_log()


def add_consultation_note(patient_name: str, doctor_name: str, note: str):
    return _STORE.add_consultation_note(patient_name, doctor_name, note)


def get_consultation_notes():
    return _STORE.get_consultation_notes()


def add_sos_alert(triggered_by: str, location: str = "Unknown"):
    return _STORE.add_sos_alert(triggered_by, location)


def get_sos_alerts():
    return _STORE.get_sos_alerts()


def add_report(filename: str, summary: str, uploaded_by: str = "children", patient_name: str = "George Smith"):
    return _STORE.add_report(filename, summary, uploaded_by, patient_name)


def get_reports(patient_name: str = None):
    return _STORE.get_reports(patient_name)


def get_report_by_id(report_id: int):
    return _STORE.get_report_by_id(report_id)


def get_appointment_by_id(appt_id: int):
    return _STORE.get_appointment_by_id(appt_id)


def get_note_by_id(note_id: int):
    return _STORE.get_note_by_id(note_id)


def get_medicine_entry_by_id(med_id: int):
    return _STORE.get_medicine_entry_by_id(med_id)


def get_all_patients():
    return _STORE.get_all_patients()


def get_patient_by_id(pid: str):
    return _STORE.get_patient_by_id(pid)


def register_patient(name: str, age: int, gender: str, blood_group: str, phone: str, address: str, emergency_contact: str, conditions=None, allergies=None, registered_by: str = "children"):
    return _STORE.register_patient(name, age, gender, blood_group, phone, address, emergency_contact, conditions, allergies, registered_by)


def update_patient_vitals(pid: str, vitals: dict):
    return _STORE.update_patient_vitals(pid, vitals)


def get_all_doctors():
    return _STORE.get_all_doctors()


def get_doctor_by_id(did: str):
    return _STORE.get_doctor_by_id(did)


def get_doctor_by_name(name: str):
    return _STORE.get_doctor_by_name(name)


def register_doctor(name: str, specialty: str, phone: str = "", availability: str = "Mon-Fri"):
    return _STORE.register_doctor(name, specialty, phone, availability)


def register_user(full_name: str, email: str, password: str, role: str, **kwargs):
    return _STORE.register_user(full_name, email, password, role, **kwargs)


def authenticate_user(email: str, password: str, role: str):
    return _STORE.authenticate_user(email, password, role)
