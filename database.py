"""CareConnect database initialization and models using SQLAlchemy + PostgreSQL."""

import logging
import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, JSON, Text, ForeignKey, Sequence
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = os.environ.get('DATABASE_URL') or os.environ.get('SUPABASE_URL') or 'postgresql://user:password@localhost:5432/careconnect'

# Ensure we use psycopg2 driver
if DATABASE_URL and not DATABASE_URL.startswith('postgresql://') and not DATABASE_URL.startswith('postgresql+psycopg2://'):
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql+psycopg2://', 1)
    else:
        DATABASE_URL = 'postgresql+psycopg2://' + DATABASE_URL.split('://', 1)[1] if '://' in DATABASE_URL else 'postgresql+psycopg2://' + DATABASE_URL

try:
    engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True, connect_args={"connect_timeout": 10})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base = declarative_base()
except Exception as e:
    logger.error(f"Failed to initialize database connection: {e}")
    engine = None
    SessionLocal = None
    Base = declarative_base()


# ============================================================================
# SQLAlchemy Models
# ============================================================================

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, Sequence('user_id_seq'), primary_key=True)
    full_name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    email_norm = Column(String, nullable=False, index=True)
    role = Column(String, nullable=False)
    email_role_key = Column(String, nullable=False, unique=True, index=True)
    password_hash = Column(String, nullable=False)
    created_at = Column(String, nullable=False)
    ts = Column(Float, nullable=False, index=True)
    active = Column(Boolean, default=True)
    specialty = Column(String, nullable=True)  # For doctors
    phone = Column(String, nullable=True)
    availability = Column(String, nullable=True)  # For doctors
    age = Column(Integer, nullable=True)  # For patients
    gender = Column(String, nullable=True)  # For patients
    blood_group = Column(String, nullable=True)  # For patients
    medical_license_id = Column(String, nullable=True)  # For doctors
    relationship = Column(String, nullable=True)  # For children role
    hospital_name = Column(String, nullable=True)  # For hospital admin
    employee_id = Column(String, nullable=True)  # For hospital admin
    lab_name = Column(String, nullable=True)  # For diagnostic
    location = Column(String, nullable=True)  # For diagnostic


class Patient(Base):
    __tablename__ = "patients"
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False, index=True)
    age = Column(Integer, nullable=False)
    gender = Column(String, nullable=False)
    blood_group = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    address = Column(String, nullable=False)
    emergency_contact = Column(String, nullable=False)
    conditions = Column(JSON, default=[])  # List of conditions
    allergies = Column(JSON, default=[])  # List of allergies
    registered_by = Column(String, nullable=False)
    registered_at = Column(String, nullable=False)
    vitals = Column(JSON, default={})  # Dict with heart_rate, blood_pressure, etc.
    vitals_updated_at = Column(String, nullable=True)


class Doctor(Base):
    __tablename__ = "doctors"
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False, index=True)
    specialty = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    availability = Column(String, nullable=False)
    registered_at = Column(String, nullable=False)


class Appointment(Base):
    __tablename__ = "appointments"
    
    id = Column(Integer, Sequence('appointment_id_seq'), primary_key=True)
    patient_name = Column(String, nullable=False, index=True)
    doctor = Column(String, nullable=False)
    department = Column(String, nullable=False)
    date = Column(String, nullable=False, index=True)
    time = Column(String, nullable=False)
    status = Column(String, default='Pending')
    booked_by = Column(String, nullable=False)
    created_at = Column(String, nullable=False)
    created_ts = Column(Float, nullable=False, index=True)


class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, Sequence('message_id_seq'), primary_key=True)
    sender = Column(String, nullable=False, index=True)
    sender_name = Column(String, nullable=False)
    text = Column(Text, nullable=False)
    timestamp = Column(String, nullable=False)
    ts = Column(Float, nullable=False, index=True)


class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(Integer, Sequence('notification_id_seq'), primary_key=True)
    role = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    kind = Column(String, default='info')
    timestamp = Column(String, nullable=False)
    ts = Column(Float, nullable=False, index=True)
    read = Column(Boolean, default=False)


class ConsultationNote(Base):
    __tablename__ = "consultation_notes"
    
    id = Column(Integer, Sequence('consultation_note_id_seq'), primary_key=True)
    patient_name = Column(String, nullable=False, index=True)
    doctor_name = Column(String, nullable=False)
    note = Column(Text, nullable=False)
    timestamp = Column(String, nullable=False)
    ts = Column(Float, nullable=False, index=True)


class MedicineLog(Base):
    __tablename__ = "medicine_log"
    
    id = Column(Integer, Sequence('medicine_log_id_seq'), primary_key=True)
    medicine = Column(String, nullable=False)
    taken_by = Column(String, nullable=False)
    timestamp = Column(String, nullable=False)
    ts = Column(Float, nullable=False, index=True)


class SOSAlert(Base):
    __tablename__ = "sos_alerts"
    
    id = Column(Integer, Sequence('sos_alert_id_seq'), primary_key=True)
    triggered_by = Column(String, nullable=False)
    location = Column(String, nullable=False)
    timestamp = Column(String, nullable=False)
    ts = Column(Float, nullable=False, index=True)


class Report(Base):
    __tablename__ = "reports"
    
    id = Column(Integer, Sequence('report_id_seq'), primary_key=True)
    filename = Column(String, nullable=False)
    patient_name = Column(String, nullable=False, index=True)
    summary = Column(Text, nullable=False)
    uploaded_by = Column(String, nullable=False)
    status = Column(String, default='Analyzed')
    timestamp = Column(String, nullable=False)
    ts = Column(Float, nullable=False, index=True)


# ============================================================================
# Database initialization and management
# ============================================================================

def init_db():
    """Initialize database tables."""
    if engine is None:
        logger.error("Database engine not initialized")
        return False
    
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize database tables: {e}")
        return False


def get_db() -> Session:
    """Get a database session."""
    if SessionLocal is None:
        raise RuntimeError("Database session factory not initialized")
    return SessionLocal()


def get_database():
    """Legacy function for backward compatibility with data_store.py."""
    return get_db()


def ensure_indexes(db=None):
    """Legacy function for backward compatibility. Indexes are auto-created by SQLAlchemy."""
    logger.info("Indexes ensured by SQLAlchemy")
    return True
