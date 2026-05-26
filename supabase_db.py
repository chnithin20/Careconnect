"""Supabase Database Module - Replaces local database connections"""

import os
import logging
import hashlib
import time
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse

from dotenv import load_dotenv

# Import Supabase client
try:
    from supabase import create_client, Client
except ImportError:
    raise ImportError("supabase-py is required. Install with: pip install supabase")

logger = logging.getLogger(__name__)

# ============================================================================
# Supabase Client Initialization
# ============================================================================

load_dotenv()


def _load_supabase_config() -> tuple[str, str]:
    url = (os.environ.get('SUPABASE_URL') or '').strip()
    key = (os.environ.get('SUPABASE_SERVICE_KEY') or os.environ.get('SUPABASE_KEY') or '').strip()

    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY environment variables are required")

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(
            "SUPABASE_URL must be the Supabase API URL, e.g. "
            "https://your-project.supabase.co. Do not use the PostgreSQL connection string."
        )
    if "your_supabase_host" in url or "your-project" in parsed.netloc:
        raise ValueError("SUPABASE_URL still contains a placeholder host. Set it to your real Supabase API URL.")

    return url.rstrip("/"), key


def _raise_friendly_supabase_error(error: Exception, action: str) -> None:
    message = str(error)
    if "getaddrinfo failed" in message or "Errno 11001" in message:
        raise RuntimeError(
            f"Could not {action}: Supabase host could not be resolved. "
            "Check your internet/DNS connection and confirm SUPABASE_URL is the HTTPS project API URL."
        ) from error
    if "WinError 10013" in message:
        raise RuntimeError(
            f"Could not {action}: the connection to Supabase was blocked by the OS, firewall, or sandbox."
        ) from error
    raise error


# ---------------------------------------------------------------------------
# Lazy Supabase client — initialized on first use, not at import time.
# This prevents crashes on Vercel where env vars may not be available
# during the module import phase of a cold start.
# ---------------------------------------------------------------------------
_supabase_client: Optional["Client"] = None


def _get_supabase() -> "Client":
    """Return the Supabase client, creating it on first call."""
    global _supabase_client
    if _supabase_client is None:
        url, key = _load_supabase_config()
        _supabase_client = create_client(url, key)
        logger.info("Supabase client initialized successfully")
    return _supabase_client


# Convenience alias used throughout this module
def _sb() -> "Client":
    return _get_supabase()


def _payload(data: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
    return {**(data or {}), **kwargs}


def _now() -> tuple[str, float]:
    value = datetime.utcnow()
    return value.isoformat(), value.timestamp()


def _public_id(prefix: str) -> str:
    return f"{prefix}{int(time.time() * 1000)}{uuid.uuid4().hex[:6].upper()}"


# ============================================================================
# User Operations
# ============================================================================

class UserRepository:
    """Handle all user-related database operations"""
    
    TABLE_NAME = "users"
    
    @staticmethod
    def _hash_password(password: str) -> str:
        """Hash password using scrypt with a fixed app-level salt.
        Significantly stronger than plain SHA-256 — resistant to rainbow tables
        and GPU brute-force attacks.
        """
        app_salt = (os.environ.get("SECRET_KEY") or "careconnect-salt").encode()
        dk = hashlib.scrypt(password.encode(), salt=app_salt, n=16384, r=8, p=1)
        return dk.hex()

    @staticmethod
    def _hash_password_legacy(password: str) -> str:
        """Legacy SHA-256 hash — kept only for migrating existing accounts."""
        return hashlib.sha256(password.encode()).hexdigest()

    @staticmethod
    def verify_password(password: str, stored_hash: str) -> bool:
        """Verify password against stored hash, supporting both scrypt and legacy SHA-256."""
        # Try scrypt first
        if UserRepository._hash_password(password) == stored_hash:
            return True
        # Fall back to legacy SHA-256 for old accounts
        return UserRepository._hash_password_legacy(password) == stored_hash
    
    @staticmethod
    def create_user(full_name: str, email: str, password: str, role: str, **kwargs) -> Dict[str, Any]:
        """Create a new user with password hashing and normalization"""
        try:
            # Normalize and prepare user data
            email_norm = email.lower().strip()
            email_role_key = f"{email_norm}_{role}"
            password_hash = UserRepository._hash_password(password)
            now = datetime.utcnow()
            ts = now.timestamp()
            
            user_data = {
                "full_name": full_name,
                "email": email,
                "email_norm": email_norm,
                "email_role_key": email_role_key,
                "password_hash": password_hash,
                "role": role,
                "created_at": now.isoformat(),
                "ts": ts,
                "active": True,
                **kwargs  # Include role-specific fields (specialty, phone, etc.)
            }
            
            response = _sb().table(UserRepository.TABLE_NAME).insert(user_data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            _raise_friendly_supabase_error(e, "create user")
    
    @staticmethod
    def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        try:
            response = _sb().table(UserRepository.TABLE_NAME).select("*").eq("id", user_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error fetching user by ID: {e}")
            return None
    
    @staticmethod
    def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
        """Get user by email"""
        try:
            email_norm = email.lower().strip()
            response = _sb().table(UserRepository.TABLE_NAME).select("*").eq("email_norm", email_norm).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error fetching user by email: {e}")
            return None
    
    @staticmethod
    def get_user_by_email_role(email: str, role: str, password: str = None) -> Optional[Dict[str, Any]]:
        """Get user by email and role, optionally verify password"""
        try:
            email_norm = email.lower().strip()
            email_role_key = f"{email_norm}_{role}"
            response = _sb().table(UserRepository.TABLE_NAME).select("*").eq("email_role_key", email_role_key).execute()
            user = response.data[0] if response.data else None

            # If password provided, verify using scrypt (with SHA-256 legacy fallback)
            if user and password:
                if not UserRepository.verify_password(password, user.get("password_hash", "")):
                    return None

            return user
        except Exception as e:
            logger.error(f"Error fetching user by email and role: {e}")
            return None
    
    @staticmethod
    def update_user(user_id: int, update_data: Dict[str, Any]) -> bool:
        """Update user information"""
        try:
            update_data['updated_at'] = datetime.utcnow().isoformat()
            response = _sb().table(UserRepository.TABLE_NAME).update(update_data).eq("id", user_id).execute()
            return bool(response.data)
        except Exception as e:
            logger.error(f"Error updating user: {e}")
            return False
    
    @staticmethod
    def list_users_by_role(role: str) -> List[Dict[str, Any]]:
        """Get all users with specific role"""
        try:
            response = _sb().table(UserRepository.TABLE_NAME).select("*").eq("role", role).execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Error listing users by role: {e}")
            return []
    
    @staticmethod
    def delete_user(user_id: int) -> bool:
        """Delete a user"""
        try:
            response = _sb().table(UserRepository.TABLE_NAME).delete().eq("id", user_id).execute()
            return True
        except Exception as e:
            logger.error(f"Error deleting user: {e}")
            return False


# ============================================================================
# Patient Operations
# ============================================================================

class PatientRepository:
    """Handle all patient-related database operations"""
    
    TABLE_NAME = "patients"
    
    @staticmethod
    def create_patient(patient_data: Dict[str, Any] = None, **kwargs) -> Dict[str, Any]:
        """Create a new patient"""
        try:
            data = _payload(patient_data, **kwargs)
            timestamp, _ = _now()
            patient = {
                "id": data.get("id") or _public_id("P"),
                "name": data.get("name") or data.get("full_name"),
                "age": int(data.get("age") or 0),
                "gender": data.get("gender") or "Other",
                "blood_group": data.get("blood_group") or data.get("blood_type") or "O+",
                "phone": data.get("phone") or "",
                "address": data.get("address") or "",
                "emergency_contact": data.get("emergency_contact") or "",
                "conditions": data.get("conditions") or [],
                "allergies": data.get("allergies") or [],
                "registered_by": data.get("registered_by") or "system",
                "registered_at": data.get("registered_at") or data.get("created_at") or timestamp,
                "vitals": data.get("vitals") or {},
                "vitals_updated_at": data.get("vitals_updated_at"),
            }
            response = _sb().table(PatientRepository.TABLE_NAME).insert(patient).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error creating patient: {e}")
            raise
    
    @staticmethod
    def get_patient_by_id(patient_id: str) -> Optional[Dict[str, Any]]:
        """Get patient by ID"""
        try:
            response = _sb().table(PatientRepository.TABLE_NAME).select("*").eq("id", patient_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error fetching patient: {e}")
            return None
    
    @staticmethod
    def search_patients(name: str) -> List[Dict[str, Any]]:
        """Search patients by name"""
        try:
            response = _sb().table(PatientRepository.TABLE_NAME).select("*").ilike("name", f"%{name}%").execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Error searching patients: {e}")
            return []
    
    @staticmethod
    def update_patient(patient_id: str, update_data: Dict[str, Any]) -> bool:
        """Update patient information"""
        try:
            update_data['updated_at'] = datetime.utcnow().isoformat()
            response = _sb().table(PatientRepository.TABLE_NAME).update(update_data).eq("id", patient_id).execute()
            return bool(response.data)
        except Exception as e:
            logger.error(f"Error updating patient: {e}")
            return False

    @staticmethod
    def update_patient_vitals(patient_id: str, vitals: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update patient vitals and return the updated patient."""
        try:
            response = (
                _sb().table(PatientRepository.TABLE_NAME)
                .update({"vitals": vitals, "vitals_updated_at": datetime.utcnow().isoformat()})
                .eq("id", patient_id)
                .execute()
            )
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error updating patient vitals: {e}")
            return None
    
    @staticmethod
    def get_all_patients(limit: int = 100) -> List[Dict[str, Any]]:
        """Get all patients with limit — use only for admin/registry views"""
        try:
            response = _sb().table(PatientRepository.TABLE_NAME).select("*").limit(limit).execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Error fetching all patients: {e}")
            return []

    @staticmethod
    def get_patient_names_only(limit: int = 100) -> List[Dict[str, Any]]:
        """Fetch only id + name — used for dropdowns. Much lighter than full rows."""
        try:
            response = _sb().table(PatientRepository.TABLE_NAME).select("id, name").limit(limit).execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Error fetching patient names: {e}")
            return []


# ============================================================================
# Doctor Operations
# ============================================================================

class DoctorRepository:
    """Handle all doctor-related database operations"""
    
    TABLE_NAME = "doctors"
    
    @staticmethod
    def create_doctor(doctor_data: Dict[str, Any] = None, **kwargs) -> Dict[str, Any]:
        """Create a new doctor"""
        try:
            data = _payload(doctor_data, **kwargs)
            timestamp, _ = _now()
            doctor = {
                "id": data.get("id") or _public_id("D"),
                "name": data.get("name") or data.get("full_name"),
                "specialty": data.get("specialty") or "General",
                "phone": data.get("phone") or "",
                "availability": data.get("availability") or "Mon-Fri",
                "registered_at": data.get("registered_at") or data.get("created_at") or timestamp,
            }
            response = _sb().table(DoctorRepository.TABLE_NAME).insert(doctor).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error creating doctor: {e}")
            raise
    
    @staticmethod
    def get_doctor_by_id(doctor_id: str) -> Optional[Dict[str, Any]]:
        """Get doctor by ID"""
        try:
            response = _sb().table(DoctorRepository.TABLE_NAME).select("*").eq("id", doctor_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error fetching doctor: {e}")
            return None
    
    @staticmethod
    def get_doctors_by_specialty(specialty: str) -> List[Dict[str, Any]]:
        """Get doctors by specialty"""
        try:
            response = _sb().table(DoctorRepository.TABLE_NAME).select("*").eq("specialty", specialty).execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Error fetching doctors by specialty: {e}")
            return []
    
    @staticmethod
    def search_doctors(name: str) -> List[Dict[str, Any]]:
        """Search doctors by name"""
        try:
            response = _sb().table(DoctorRepository.TABLE_NAME).select("*").ilike("name", f"%{name}%").execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Error searching doctors: {e}")
            return []
    
    @staticmethod
    def update_doctor(doctor_id: str, update_data: Dict[str, Any]) -> bool:
        """Update doctor information"""
        try:
            update_data['updated_at'] = datetime.utcnow().isoformat()
            response = _sb().table(DoctorRepository.TABLE_NAME).update(update_data).eq("id", doctor_id).execute()
            return bool(response.data)
        except Exception as e:
            logger.error(f"Error updating doctor: {e}")
            return False
    
    @staticmethod
    def get_all_doctors(limit: int = 100) -> List[Dict[str, Any]]:
        """Get all doctors with limit — use only for admin/registry views"""
        try:
            response = _sb().table(DoctorRepository.TABLE_NAME).select("*").limit(limit).execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Error fetching all doctors: {e}")
            return []

    @staticmethod
    def get_doctor_names_only(limit: int = 100) -> List[Dict[str, Any]]:
        """Fetch only id + name + specialty — used for dropdowns. Much lighter than full rows."""
        try:
            response = _sb().table(DoctorRepository.TABLE_NAME).select("id, name, specialty").limit(limit).execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Error fetching doctor names: {e}")
            return []


# ============================================================================
# Appointment Operations
# ============================================================================

class AppointmentRepository:
    """Handle all appointment-related database operations"""
    
    TABLE_NAME = "appointments"
    
    @staticmethod
    def create_appointment(appointment_data: Dict[str, Any] = None, **kwargs) -> Dict[str, Any]:
        """Create a new appointment"""
        try:
            data = _payload(appointment_data, **kwargs)
            timestamp, ts = _now()
            appointment = {
                "patient_name": data.get("patient_name") or "Unknown Patient",
                "doctor": data.get("doctor") or data.get("doctor_name") or "Assigned Doctor",
                "department": data.get("department") or "General",
                "date": data.get("date") or data.get("appointment_date") or "",
                "time": data.get("time") or data.get("appointment_time") or "",
                "status": data.get("status") or "Pending",
                "booked_by": data.get("booked_by") or "children",
                "created_at": data.get("created_at") or timestamp,
                "created_ts": float(data.get("created_ts") or data.get("ts") or ts),
            }
            response = _sb().table(AppointmentRepository.TABLE_NAME).insert(appointment).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error creating appointment: {e}")
            raise
    
    @staticmethod
    def get_appointment_by_id(appointment_id: int) -> Optional[Dict[str, Any]]:
        """Get appointment by ID"""
        try:
            response = _sb().table(AppointmentRepository.TABLE_NAME).select("*").eq("id", appointment_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error fetching appointment: {e}")
            return None
    
    @staticmethod
    def get_appointments_by_patient(patient_name: str) -> List[Dict[str, Any]]:
        """Get all appointments for a patient"""
        try:
            response = _sb().table(AppointmentRepository.TABLE_NAME).select("*").eq("patient_name", patient_name).execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Error fetching patient appointments: {e}")
            return []
    
    @staticmethod
    def get_appointments_by_doctor(doctor: str) -> List[Dict[str, Any]]:
        """Get all appointments for a doctor"""
        try:
            response = _sb().table(AppointmentRepository.TABLE_NAME).select("*").eq("doctor", doctor).execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Error fetching doctor appointments: {e}")
            return []
    
    @staticmethod
    def update_appointment(appointment_id: int, update_data: Dict[str, Any]) -> bool:
        """Update appointment"""
        try:
            update_data['updated_at'] = datetime.utcnow().isoformat()
            response = _sb().table(AppointmentRepository.TABLE_NAME).update(update_data).eq("id", appointment_id).execute()
            return bool(response.data)
        except Exception as e:
            logger.error(f"Error updating appointment: {e}")
            return False
    
    @staticmethod
    def delete_appointment(appointment_id: int) -> bool:
        """Delete appointment"""
        try:
            response = _sb().table(AppointmentRepository.TABLE_NAME).delete().eq("id", appointment_id).execute()
            return True
        except Exception as e:
            logger.error(f"Error deleting appointment: {e}")
            return False
    
    @staticmethod
    def get_all_appointments(limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent appointments — admin/fallback view only, hard-capped at 20"""
        try:
            response = _sb().table(AppointmentRepository.TABLE_NAME).select("*").limit(limit).order("created_at", desc=True).execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Error fetching all appointments: {e}")
            return []

    @staticmethod
    def get_confirmed_doctor_for_user(patient_name: str) -> Optional[str]:
        """Return only the doctor name from the most recent confirmed appointment
        for a specific patient — single targeted row, not a full table scan."""
        try:
            response = (
                _sb().table(AppointmentRepository.TABLE_NAME)
                .select("doctor")
                .eq("patient_name", patient_name)
                .eq("status", "Confirmed")
                .order("created_ts", desc=True)
                .limit(1)
                .execute()
            )
            if response.data:
                return response.data[0].get("doctor")
            return None
        except Exception as e:
            logger.error(f"Error fetching confirmed doctor for {patient_name}: {e}")
            return None


# ============================================================================
# Message Operations
# ============================================================================

class MessageRepository:
    """Handle all message-related database operations"""
    
    TABLE_NAME = "messages"
    
    @staticmethod
    def create_message(message_data: Dict[str, Any] = None, **kwargs) -> Dict[str, Any]:
        """Create a new message"""
        try:
            data = _payload(message_data, **kwargs)
            timestamp, ts = _now()
            message = {
                "sender": data.get("sender") or data.get("sender_id") or "children",
                "sender_name": data.get("sender_name") or "Unknown",
                "text": data.get("text") or data.get("message_text") or "",
                "timestamp": data.get("timestamp") or data.get("created_at") or timestamp,
                "ts": float(data.get("ts") or ts),
            }
            response = _sb().table(MessageRepository.TABLE_NAME).insert(message).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error creating message: {e}")
            raise
    
    @staticmethod
    def get_all_messages(limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent messages — initial chat load, hard-capped at 50"""
        try:
            response = _sb().table(MessageRepository.TABLE_NAME).select("*").limit(limit).order("ts", desc=True).execute()
            return list(reversed(response.data or []))
        except Exception as e:
            logger.error(f"Error fetching messages: {e}")
            return []

    @staticmethod
    def get_messages_since(since_ts: float, limit: int = 100) -> List[Dict[str, Any]]:
        """Get messages newer than the given unix timestamp"""
        try:
            response = (
                _sb().table(MessageRepository.TABLE_NAME)
                .select("*")
                .gt("ts", since_ts)
                .limit(limit)
                .order("ts", desc=False)
                .execute()
            )
            return response.data or []
        except Exception as e:
            logger.error(f"Error fetching messages since {since_ts}: {e}")
            return []


# ============================================================================
# Notification Operations
# ============================================================================

class NotificationRepository:
    """Handle all notification-related database operations"""
    
    TABLE_NAME = "notifications"

    @staticmethod
    def _decorate(notification: Dict[str, Any]) -> Dict[str, Any]:
        return dict(notification)
    
    @staticmethod
    def create_notification(notification_data: Dict[str, Any] = None, **kwargs) -> Dict[str, Any]:
        """Create a new notification"""
        try:
            data = _payload(notification_data, **kwargs)
            timestamp, ts = _now()
            priority = data.get("priority") or data.get("kind") or "info"
            kind = {"high": "warning", "critical": "error"}.get(priority, priority)
            notification = {
                "role": data.get("role") or data.get("recipient_role") or "children",
                "title": data.get("title") or "Notification",
                "body": data.get("body") or data.get("message") or "",
                "kind": kind,
                "timestamp": data.get("timestamp") or data.get("created_at") or timestamp,
                "ts": float(data.get("ts") or ts),
                "read": bool(data.get("read", False)),
            }
            response = _sb().table(NotificationRepository.TABLE_NAME).insert(notification).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error creating notification: {e}")
            raise
    
    @staticmethod
    def get_notifications_by_role(role: str, unread_only: bool = False, since_ts: float = 0) -> List[Dict[str, Any]]:
        """Get notifications for a role, optionally filtered by timestamp"""
        try:
            query = _sb().table(NotificationRepository.TABLE_NAME).select("*").eq("role", role)
            if unread_only:
                query = query.eq("read", False)
            if since_ts > 0:
                query = query.gt("ts", since_ts)
            response = query.order("ts", desc=True).limit(50).execute()
            return [NotificationRepository._decorate(item) for item in (response.data or [])]
        except Exception as e:
            logger.error(f"Error fetching notifications: {e}")
            return []
    
    @staticmethod
    def mark_notification_as_read(notification_id: int) -> bool:
        """Mark notification as read"""
        try:
            response = _sb().table(NotificationRepository.TABLE_NAME).update({"read": True}).eq("id", notification_id).execute()
            return bool(response.data)
        except Exception as e:
            logger.error(f"Error marking notification as read: {e}")
            return False


# ============================================================================
# Consultation Note Operations
# ============================================================================

class ConsultationNoteRepository:
    """Handle all consultation note-related database operations"""
    
    TABLE_NAME = "consultation_notes"
    
    @staticmethod
    def create_note(note_data: Dict[str, Any] = None, **kwargs) -> Dict[str, Any]:
        """Create a new consultation note"""
        try:
            data = _payload(note_data, **kwargs)
            timestamp, ts = _now()
            note = {
                "patient_name": data.get("patient_name") or "Patient",
                "doctor_name": data.get("doctor_name") or "Doctor",
                "note": data.get("note") or data.get("note_content") or "",
                "timestamp": data.get("timestamp") or data.get("created_at") or timestamp,
                "ts": float(data.get("ts") or ts),
            }
            response = _sb().table(ConsultationNoteRepository.TABLE_NAME).insert(note).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error creating consultation note: {e}")
            raise
    
    @staticmethod
    def get_notes_by_patient(patient_name: str) -> List[Dict[str, Any]]:
        """Get consultation notes filtered by patient name"""
        try:
            response = _sb().table(ConsultationNoteRepository.TABLE_NAME).select("*").eq("patient_name", patient_name).order("ts", desc=True).execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Error fetching consultation notes: {e}")
            return []

    @staticmethod
    def get_notes_by_doctor(doctor_name: str) -> List[Dict[str, Any]]:
        """Get consultation notes filtered by doctor name — never full table scan"""
        try:
            response = _sb().table(ConsultationNoteRepository.TABLE_NAME).select("*").eq("doctor_name", doctor_name).order("ts", desc=True).limit(50).execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Error fetching notes by doctor: {e}")
            return []
    
    @staticmethod
    def get_all_notes(limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent notes — admin view only, hard-capped at 50"""
        try:
            response = _sb().table(ConsultationNoteRepository.TABLE_NAME).select("*").limit(limit).order("ts", desc=True).execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Error fetching all consultation notes: {e}")
            return []
    
    @staticmethod
    def get_note_by_id(note_id: int) -> Optional[Dict[str, Any]]:
        """Get consultation note by ID"""
        try:
            response = _sb().table(ConsultationNoteRepository.TABLE_NAME).select("*").eq("id", note_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error fetching note by ID: {e}")
            return None


# ============================================================================
# Medicine Log Operations
# ============================================================================

class MedicineLogRepository:
    """Handle all medicine log-related database operations"""
    
    TABLE_NAME = "medicine_log"
    
    @staticmethod
    def create_log(log_data: Dict[str, Any] = None, **kwargs) -> Dict[str, Any]:
        """Create a new medicine log entry"""
        try:
            data = _payload(log_data, **kwargs)
            timestamp, ts = _now()
            log = {
                "medicine": data.get("medicine") or data.get("medicine_name") or "Medicine",
                "taken_by": data.get("taken_by") or data.get("user_id") or "patient",
                "timestamp": data.get("timestamp") or data.get("taken_at") or data.get("created_at") or timestamp,
                "ts": float(data.get("ts") or ts),
            }
            response = _sb().table(MedicineLogRepository.TABLE_NAME).insert(log).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error creating medicine log: {e}")
            raise
    
    @staticmethod
    def get_logs_by_user(user_name: str) -> List[Dict[str, Any]]:
        """Get all medicine logs for a user"""
        try:
            response = _sb().table(MedicineLogRepository.TABLE_NAME).select("*").eq("taken_by", user_name).order("ts", desc=True).execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Error fetching medicine logs: {e}")
            return []
    
    @staticmethod
    def get_all_logs(limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent medicine logs — admin view only, hard-capped at 50"""
        try:
            response = _sb().table(MedicineLogRepository.TABLE_NAME).select("*").limit(limit).order("ts", desc=True).execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Error fetching all medicine logs: {e}")
            return []
    
    @staticmethod
    def get_log_by_id(log_id: int) -> Optional[Dict[str, Any]]:
        """Get medicine log by ID"""
        try:
            response = _sb().table(MedicineLogRepository.TABLE_NAME).select("*").eq("id", log_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error fetching log by ID: {e}")
            return None


# ============================================================================
# SOS Alert Operations
# ============================================================================

class SOSAlertRepository:
    """Handle all SOS alert-related database operations"""
    
    TABLE_NAME = "sos_alerts"
    
    @staticmethod
    def create_alert(alert_data: Dict[str, Any] = None, **kwargs) -> Dict[str, Any]:
        """Create a new SOS alert"""
        try:
            data = _payload(alert_data, **kwargs)
            timestamp, ts = _now()
            alert = {
                "triggered_by": data.get("triggered_by") or "Patient",
                "location": data.get("location") or "Unknown",
                "timestamp": data.get("timestamp") or data.get("created_at") or timestamp,
                "ts": float(data.get("ts") or ts),
            }
            response = _sb().table(SOSAlertRepository.TABLE_NAME).insert(alert).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error creating SOS alert: {e}")
            raise
    
    @staticmethod
    def get_recent_alerts(limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent SOS alerts"""
        try:
            response = _sb().table(SOSAlertRepository.TABLE_NAME).select("*").limit(limit).order("ts", desc=True).execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Error fetching SOS alerts: {e}")
            return []
    
    @staticmethod
    def get_all_alerts(limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent SOS alerts — admin view only, hard-capped at 20"""
        try:
            response = _sb().table(SOSAlertRepository.TABLE_NAME).select("*").limit(limit).order("ts", desc=True).execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Error fetching all SOS alerts: {e}")
            return []


# ============================================================================
# Report Operations
# ============================================================================

class ReportRepository:
    """Handle all report-related database operations"""
    
    TABLE_NAME = "reports"
    
    @staticmethod
    def create_report(report_data: Dict[str, Any] = None, **kwargs) -> Dict[str, Any]:
        """Create a new report"""
        try:
            data = _payload(report_data, **kwargs)
            timestamp, ts = _now()
            report = {
                "filename": data.get("filename") or data.get("file_name") or f"report.{str(data.get('report_type') or 'txt').lower()}",
                "patient_name": data.get("patient_name") or "Patient",
                "summary": data.get("summary") or data.get("ai_analysis") or "",
                "uploaded_by": data.get("uploaded_by") or "children",
                "status": data.get("status") or "Analyzed",
                "timestamp": data.get("timestamp") or data.get("created_at") or timestamp,
                "ts": float(data.get("ts") or ts),
                "file_url": data.get("file_url"),
            }
            response = _sb().table(ReportRepository.TABLE_NAME).insert(report).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error creating report: {e}")
            raise
    
    @staticmethod
    def get_report_by_id(report_id: int) -> Optional[Dict[str, Any]]:
        """Get report by ID"""
        try:
            response = _sb().table(ReportRepository.TABLE_NAME).select("*").eq("id", report_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error fetching report: {e}")
            return None
    
    @staticmethod
    def get_reports_by_patient(patient_name: str) -> List[Dict[str, Any]]:
        """Get reports filtered by patient name — targeted query"""
        try:
            response = _sb().table(ReportRepository.TABLE_NAME).select("*").eq("patient_name", patient_name).order("ts", desc=True).execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Error fetching patient reports: {e}")
            return []

    @staticmethod
    def get_reports_by_uploader(uploaded_by: str) -> List[Dict[str, Any]]:
        """Get reports filtered by who uploaded them — targeted query, never full scan"""
        try:
            response = (
                _sb().table(ReportRepository.TABLE_NAME)
                .select("*")
                .eq("uploaded_by", uploaded_by)
                .order("ts", desc=True)
                .limit(50)
                .execute()
            )
            return response.data or []
        except Exception as e:
            logger.error(f"Error fetching reports by uploader: {e}")
            return []
    
    @staticmethod
    def update_report(report_id: int, update_data: Dict[str, Any]) -> bool:
        """Update report"""
        try:
            update_data['updated_at'] = datetime.utcnow().isoformat()
            response = _sb().table(ReportRepository.TABLE_NAME).update(update_data).eq("id", report_id).execute()
            return bool(response.data)
        except Exception as e:
            logger.error(f"Error updating report: {e}")
            return False
    
    @staticmethod
    def get_all_reports(limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent reports — admin view only, hard-capped at 50"""
        try:
            response = _sb().table(ReportRepository.TABLE_NAME).select("*").limit(limit).order("ts", desc=True).execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Error fetching all reports: {e}")
            return []


# ============================================================================
# Audit Log Operations
# ============================================================================

class AuditLogRepository:
    """Handle audit log operations"""
    
    TABLE_NAME = "audit_logs"
    
    @staticmethod
    def create_log(action: str, user_id: int, table_name: str, record_id: str, old_values: Dict = None, new_values: Dict = None) -> bool:
        """Create an audit log entry"""
        try:
            log_data = {
                "action": action,
                "user_id": user_id,
                "table_name": table_name,
                "record_id": record_id,
                "old_values": old_values or {},
                "new_values": new_values or {}
            }
            response = _sb().table(AuditLogRepository.TABLE_NAME).insert(log_data).execute()
            return bool(response.data)
        except Exception as e:
            logger.error(f"Error creating audit log: {e}")
            return False


# ============================================================================
# Session / JWT Token Operations
# ============================================================================

class SessionRepository:
    """Store and verify JWT session tokens in the database.

    Each login creates one row.  On logout (or token refresh) the row is
    revoked so the old token can never be replayed.
    """

    TABLE_NAME = "user_sessions"

    @staticmethod
    def create_session(
        user_id: int,
        jti: str,
        role: str,
        expires_at: str,
        user_agent: str = "",
        ip_address: str = "",
    ) -> Dict[str, Any]:
        """Persist a new JWT session record."""
        try:
            row = {
                "user_id": user_id,
                "jti": jti,
                "role": role,
                "issued_at": datetime.utcnow().isoformat(),
                "expires_at": expires_at,
                "revoked": False,
                "user_agent": user_agent or "",
                "ip_address": ip_address or "",
            }
            response = _sb().table(SessionRepository.TABLE_NAME).insert(row).execute()
            return response.data[0] if response.data else row
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            raise

    @staticmethod
    def get_session(jti: str) -> Optional[Dict[str, Any]]:
        """Fetch a session row by JWT ID claim."""
        try:
            response = (
                _sb().table(SessionRepository.TABLE_NAME)
                .select("*")
                .eq("jti", jti)
                .execute()
            )
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error fetching session: {e}")
            return None

    @staticmethod
    def is_valid(jti: str) -> bool:
        """Return True only if the session exists, is not revoked, and has not expired."""
        try:
            session = SessionRepository.get_session(jti)
            if not session:
                return False
            if session.get("revoked"):
                return False
            # expires_at is stored as ISO string; compare against UTC now
            expires_at_str = session.get("expires_at", "")
            if expires_at_str:
                from datetime import timezone
                expires_dt = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
                if expires_dt.tzinfo is None:
                    expires_dt = expires_dt.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) > expires_dt:
                    return False
            return True
        except Exception as e:
            logger.error(f"Error validating session: {e}")
            return False

    @staticmethod
    def revoke_session(jti: str) -> bool:
        """Mark a session as revoked (logout / token rotation)."""
        try:
            response = (
                _sb().table(SessionRepository.TABLE_NAME)
                .update({"revoked": True})
                .eq("jti", jti)
                .execute()
            )
            return bool(response.data)
        except Exception as e:
            logger.error(f"Error revoking session: {e}")
            return False

    @staticmethod
    def revoke_all_for_user(user_id: int) -> bool:
        """Revoke every active session for a user (force-logout all devices)."""
        try:
            response = (
                _sb().table(SessionRepository.TABLE_NAME)
                .update({"revoked": True})
                .eq("user_id", user_id)
                .eq("revoked", False)
                .execute()
            )
            return True
        except Exception as e:
            logger.error(f"Error revoking all sessions for user {user_id}: {e}")
            return False

    @staticmethod
    def cleanup_expired() -> int:
        """Delete expired session rows (call periodically to keep the table lean)."""
        try:
            from datetime import timezone
            now_iso = datetime.now(timezone.utc).isoformat()
            response = (
                _sb().table(SessionRepository.TABLE_NAME)
                .delete()
                .lt("expires_at", now_iso)
                .execute()
            )
            deleted = len(response.data) if response.data else 0
            logger.info(f"Cleaned up {deleted} expired sessions")
            return deleted
        except Exception as e:
            logger.error(f"Error cleaning up sessions: {e}")
            return 0
