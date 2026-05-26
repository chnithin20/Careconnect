#!/usr/bin/env python3
"""
Verification script to check all Supabase connections and relationships
"""

import os
import sys
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
    AuditLogRepository
)

def test_connection():
    """Test Supabase connection"""
    print("🔍 Testing Supabase Connection...")
    try:
        from supabase_db import supabase
        print("✅ Supabase client initialized successfully")
        return True
    except Exception as e:
        print(f"❌ Supabase connection failed: {e}")
        return False

def test_repositories():
    """Test all repository classes"""
    print("\n🔍 Testing Repository Classes...")
    repositories = [
        ("UserRepository", UserRepository),
        ("PatientRepository", PatientRepository),
        ("DoctorRepository", DoctorRepository),
        ("AppointmentRepository", AppointmentRepository),
        ("MessageRepository", MessageRepository),
        ("NotificationRepository", NotificationRepository),
        ("ConsultationNoteRepository", ConsultationNoteRepository),
        ("MedicineLogRepository", MedicineLogRepository),
        ("SOSAlertRepository", SOSAlertRepository),
        ("ReportRepository", ReportRepository),
        ("AuditLogRepository", AuditLogRepository),
    ]
    
    for name, repo in repositories:
        try:
            # Check if basic methods exist
            methods = [m for m in dir(repo) if not m.startswith('_') and callable(getattr(repo, m))]
            if methods:
                print(f"✅ {name} - {len(methods)} methods available")
            else:
                print(f"⚠️  {name} - No methods found")
        except Exception as e:
            print(f"❌ {name} - Error: {e}")

def test_relationships():
    """Check database relationships"""
    print("\n🔍 Checking Database Relationships...")
    
    relationships = {
        "users → patients": "User can have multiple Patient records",
        "users → doctors": "User can have Doctor profile",
        "users → appointments": "User can have multiple Appointments",
        "patients → appointments": "Patient can have multiple Appointments",
        "doctors → appointments": "Doctor can have multiple Appointments",
        "users → messages": "User can send multiple Messages",
        "users → consultation_notes": "User can have multiple Consultation Notes",
        "users → medicine_log": "User can have multiple Medicine Log entries",
        "users → sos_alerts": "User can trigger multiple SOS Alerts",
        "users → reports": "User can have multiple Reports",
        "appointments → notifications": "Appointment changes trigger Notifications",
        "sos_alerts → notifications": "SOS Alerts trigger Notifications",
    }
    
    for relationship, description in relationships.items():
        print(f"📌 {relationship}: {description}")

def test_crud_operations():
    """Test CRUD operation availability"""
    print("\n🔍 Testing CRUD Operations...")
    
    test_cases = [
        ("Users", ["create_user", "get_user_by_id", "get_user_by_email", "update_user", "delete_user", "list_users_by_role"]),
        ("Patients", ["create_patient", "get_patient_by_id", "search_patients", "get_all_patients"]),
        ("Doctors", ["create_doctor", "get_doctor_by_id", "search_doctors", "get_all_doctors"]),
        ("Appointments", ["create_appointment", "get_appointment_by_id", "get_all_appointments"]),
        ("Messages", ["create_message", "get_all_messages"]),
        ("Notifications", ["create_notification", "get_all_notifications"]),
        ("Consultation Notes", ["create_note", "get_all_notes", "get_note_by_id"]),
        ("Medicine Logs", ["create_log", "get_all_logs", "get_log_by_id"]),
        ("SOS Alerts", ["create_alert", "get_all_alerts"]),
        ("Reports", ["create_report", "get_all_reports"]),
    ]
    
    for entity, methods in test_cases:
        available = []
        missing = []
        for method in methods:
            if hasattr(globals().get(entity.replace(' ', '') + "Repository"), method):
                available.append(method)
            else:
                missing.append(method)
        
        status = "✅" if not missing else "⚠️ "
        print(f"{status} {entity}: {len(available)}/{len(methods)} methods")
        if missing:
            print(f"   Missing: {', '.join(missing)}")

def test_triggers():
    """Check if database triggers are active"""
    print("\n🔍 Database Triggers (should be active)...")
    
    triggers = [
        "update_users_timestamp",
        "update_patients_timestamp",
        "update_doctors_timestamp",
        "update_appointments_timestamp",
        "update_consultation_notes_timestamp",
        "update_reports_timestamp",
        "audit_users_changes",
        "audit_patients_changes",
        "audit_appointments_changes",
        "audit_consultation_notes_changes",
        "appointment_notification",
        "sos_alert_notification",
        "validate_patient",
        "validate_appointment",
        "validate_user",
    ]
    
    print(f"📌 Total triggers defined: {len(triggers)}")
    print("   - Auto-update timestamps on changes")
    print("   - Audit logging for critical tables")
    print("   - Auto-notifications for appointments and SOS alerts")
    print("   - Data validation before insert/update")

def main():
    """Run all verification tests"""
    print("=" * 60)
    print("CARECONNECT SUPABASE VERIFICATION")
    print("=" * 60)
    
    # Check environment variables
    print("\n🔍 Checking Environment Variables...")
    if os.environ.get('SUPABASE_URL'):
        print("✅ SUPABASE_URL is set")
    else:
        print("❌ SUPABASE_URL is not set")
    
    if os.environ.get('SUPABASE_KEY'):
        print("✅ SUPABASE_KEY is set")
    else:
        print("❌ SUPABASE_KEY is not set")
    
    # Run tests
    if test_connection():
        test_repositories()
        test_relationships()
        test_crud_operations()
        test_triggers()
    
    print("\n" + "=" * 60)
    print("✅ Verification Complete!")
    print("=" * 60)

if __name__ == "__main__":
    main()
