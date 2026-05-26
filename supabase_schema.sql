-- CareConnect Supabase Database Schema
-- This schema is optimized for Supabase PostgreSQL backend
-- All local database connections are removed and replaced with Supabase client

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- USERS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    full_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    email_norm VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL, -- 'patient', 'children', 'doctor', 'hospital-admin', 'diagnostic'
    email_role_key VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(500) NOT NULL,
    created_at VARCHAR(50) NOT NULL,
    ts DOUBLE PRECISION NOT NULL,
    active BOOLEAN DEFAULT true,
    
    -- Doctor specific fields
    specialty VARCHAR(100),
    phone VARCHAR(20),
    availability TEXT,
    medical_license_id VARCHAR(100),
    
    -- Patient specific fields
    age INTEGER,
    gender VARCHAR(20),
    blood_group VARCHAR(10),
    
    -- Child specific fields
    relationship VARCHAR(50),
    
    -- Hospital admin specific fields
    hospital_name VARCHAR(200),
    employee_id VARCHAR(100),
    
    -- Diagnostic specific fields
    lab_name VARCHAR(200),
    location VARCHAR(300),
    
    created_at_ts TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for users
CREATE INDEX idx_users_email_norm ON users(email_norm);
CREATE INDEX idx_users_email_role_key ON users(email_role_key);
CREATE INDEX idx_users_ts ON users(ts);
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_active ON users(active);

-- ============================================================================
-- PATIENTS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS patients (
    id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    age INTEGER NOT NULL,
    gender VARCHAR(20) NOT NULL,
    blood_group VARCHAR(10) NOT NULL,
    phone VARCHAR(20) NOT NULL,
    address TEXT NOT NULL,
    emergency_contact VARCHAR(255) NOT NULL,
    conditions JSONB DEFAULT '[]'::jsonb, -- JSON array of medical conditions
    allergies JSONB DEFAULT '[]'::jsonb, -- JSON array of allergies
    registered_by VARCHAR(255) NOT NULL,
    registered_at VARCHAR(50) NOT NULL,
    vitals JSONB DEFAULT '{}'::jsonb, -- JSON object with heart_rate, blood_pressure, etc.
    vitals_updated_at VARCHAR(50),
    
    created_at_ts TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for patients
CREATE INDEX idx_patients_name ON patients(name);
CREATE INDEX idx_patients_phone ON patients(phone);
CREATE INDEX idx_patients_registered_by ON patients(registered_by);

-- ============================================================================
-- DOCTORS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS doctors (
    id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    specialty VARCHAR(100) NOT NULL,
    phone VARCHAR(20),
    availability TEXT NOT NULL,
    registered_at VARCHAR(50) NOT NULL,
    
    created_at_ts TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for doctors
CREATE INDEX idx_doctors_name ON doctors(name);
CREATE INDEX idx_doctors_specialty ON doctors(specialty);

-- ============================================================================
-- APPOINTMENTS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS appointments (
    id BIGSERIAL PRIMARY KEY,
    patient_name VARCHAR(255) NOT NULL,
    doctor VARCHAR(255) NOT NULL,
    department VARCHAR(100) NOT NULL,
    date VARCHAR(50) NOT NULL,
    time VARCHAR(20) NOT NULL,
    status VARCHAR(50) DEFAULT 'Pending', -- 'Pending', 'Confirmed', 'Cancelled', 'Completed'
    booked_by VARCHAR(255) NOT NULL,
    created_at VARCHAR(50) NOT NULL,
    created_ts DOUBLE PRECISION NOT NULL,
    
    created_at_ts TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for appointments
CREATE INDEX idx_appointments_patient_name ON appointments(patient_name);
CREATE INDEX idx_appointments_doctor ON appointments(doctor);
CREATE INDEX idx_appointments_date ON appointments(date);
CREATE INDEX idx_appointments_created_ts ON appointments(created_ts);
CREATE INDEX idx_appointments_status ON appointments(status);

-- ============================================================================
-- MESSAGES TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS messages (
    id BIGSERIAL PRIMARY KEY,
    room_id VARCHAR(255) NOT NULL DEFAULT 'global', -- scopes chat to a specific user pair
    sender VARCHAR(255) NOT NULL,
    sender_name VARCHAR(255) NOT NULL,
    text TEXT NOT NULL,
    timestamp VARCHAR(50) NOT NULL,
    ts DOUBLE PRECISION NOT NULL,
    
    created_at_ts TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for messages
CREATE INDEX idx_messages_room_id ON messages(room_id);
CREATE INDEX idx_messages_sender ON messages(sender);
CREATE INDEX idx_messages_ts ON messages(ts);
CREATE INDEX idx_messages_timestamp ON messages(timestamp);

-- ============================================================================
-- NOTIFICATIONS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS notifications (
    id BIGSERIAL PRIMARY KEY,
    role VARCHAR(50) NOT NULL, -- 'patient', 'doctor', 'admin', etc.
    title VARCHAR(255) NOT NULL,
    body TEXT NOT NULL,
    kind VARCHAR(50) DEFAULT 'info', -- 'info', 'warning', 'error', 'success'
    timestamp VARCHAR(50) NOT NULL,
    ts DOUBLE PRECISION NOT NULL,
    read BOOLEAN DEFAULT false,
    
    created_at_ts TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for notifications
CREATE INDEX idx_notifications_role ON notifications(role);
CREATE INDEX idx_notifications_ts ON notifications(ts);
CREATE INDEX idx_notifications_read ON notifications(read);
CREATE INDEX idx_notifications_timestamp ON notifications(timestamp);

-- ============================================================================
-- CONSULTATION_NOTES TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS consultation_notes (
    id BIGSERIAL PRIMARY KEY,
    patient_name VARCHAR(255) NOT NULL,
    doctor_name VARCHAR(255) NOT NULL,
    note TEXT NOT NULL,
    timestamp VARCHAR(50) NOT NULL,
    ts DOUBLE PRECISION NOT NULL,
    
    created_at_ts TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for consultation_notes
CREATE INDEX idx_consultation_notes_patient_name ON consultation_notes(patient_name);
CREATE INDEX idx_consultation_notes_doctor_name ON consultation_notes(doctor_name);
CREATE INDEX idx_consultation_notes_ts ON consultation_notes(ts);

-- ============================================================================
-- MEDICINE_LOG TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS medicine_log (
    id BIGSERIAL PRIMARY KEY,
    medicine VARCHAR(255) NOT NULL,
    taken_by VARCHAR(255) NOT NULL,
    timestamp VARCHAR(50) NOT NULL,
    ts DOUBLE PRECISION NOT NULL,
    
    created_at_ts TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for medicine_log
CREATE INDEX idx_medicine_log_taken_by ON medicine_log(taken_by);
CREATE INDEX idx_medicine_log_ts ON medicine_log(ts);

-- ============================================================================
-- SOS_ALERTS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS sos_alerts (
    id BIGSERIAL PRIMARY KEY,
    triggered_by VARCHAR(255) NOT NULL,
    location VARCHAR(500) NOT NULL,
    timestamp VARCHAR(50) NOT NULL,
    ts DOUBLE PRECISION NOT NULL,
    
    created_at_ts TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for sos_alerts
CREATE INDEX idx_sos_alerts_triggered_by ON sos_alerts(triggered_by);
CREATE INDEX idx_sos_alerts_ts ON sos_alerts(ts);

-- ============================================================================
-- REPORTS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS reports (
    id BIGSERIAL PRIMARY KEY,
    filename VARCHAR(500) NOT NULL,
    patient_name VARCHAR(255) NOT NULL,
    summary TEXT NOT NULL,
    uploaded_by VARCHAR(255) NOT NULL,
    status VARCHAR(50) DEFAULT 'Analyzed', -- 'Pending', 'Analyzed', 'Rejected'
    timestamp VARCHAR(50) NOT NULL,
    ts DOUBLE PRECISION NOT NULL,
    file_url TEXT, -- Supabase Storage URL
    
    created_at_ts TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for reports
CREATE INDEX idx_reports_patient_name ON reports(patient_name);
CREATE INDEX idx_reports_uploaded_by ON reports(uploaded_by);
CREATE INDEX idx_reports_ts ON reports(ts);
CREATE INDEX idx_reports_status ON reports(status);

-- ============================================================================
-- USER_SESSIONS TABLE  (JWT token store — one row per active session)
-- ============================================================================
CREATE TABLE IF NOT EXISTS user_sessions (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    jti VARCHAR(64) NOT NULL UNIQUE,          -- JWT ID claim (uuid4 hex)
    role VARCHAR(50) NOT NULL,
    issued_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    revoked BOOLEAN NOT NULL DEFAULT false,
    user_agent TEXT,
    ip_address VARCHAR(64)
);

CREATE INDEX idx_user_sessions_jti ON user_sessions(jti);
CREATE INDEX idx_user_sessions_user_id ON user_sessions(user_id);
CREATE INDEX idx_user_sessions_expires_at ON user_sessions(expires_at);
CREATE INDEX idx_user_sessions_revoked ON user_sessions(revoked);

-- RLS for user_sessions
ALTER TABLE user_sessions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS careconnect_public_select ON user_sessions;
DROP POLICY IF EXISTS careconnect_public_insert ON user_sessions;
DROP POLICY IF EXISTS careconnect_public_update ON user_sessions;
CREATE POLICY careconnect_public_select ON user_sessions FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY careconnect_public_insert ON user_sessions FOR INSERT TO anon, authenticated WITH CHECK (true);
CREATE POLICY careconnect_public_update ON user_sessions FOR UPDATE TO anon, authenticated USING (true) WITH CHECK (true);

-- ============================================================================
-- Audit Log Table (Optional but recommended)
-- ============================================================================
CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGSERIAL PRIMARY KEY,
    action VARCHAR(255) NOT NULL,
    user_id BIGINT,
    table_name VARCHAR(100),
    record_id VARCHAR(255),
    old_values JSONB,
    new_values JSONB,
    created_at_ts TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for audit_logs
CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_table_name ON audit_logs(table_name);
CREATE INDEX idx_audit_logs_created_at_ts ON audit_logs(created_at_ts);

-- ============================================================================
-- Enable Row Level Security (RLS) - Recommended for Supabase
-- ============================================================================
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE patients ENABLE ROW LEVEL SECURITY;
ALTER TABLE doctors ENABLE ROW LEVEL SECURITY;
ALTER TABLE appointments ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE consultation_notes ENABLE ROW LEVEL SECURITY;
ALTER TABLE medicine_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE sos_alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

-- Demo/development access policies.
-- These allow the Flask server using the anon/publishable key to persist page actions.
-- For production, replace these with user-specific authenticated policies or set
-- SUPABASE_SERVICE_KEY on the server and keep it out of browsers.
DO $$
DECLARE
    table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'users',
        'patients',
        'doctors',
        'appointments',
        'messages',
        'notifications',
        'consultation_notes',
        'medicine_log',
        'sos_alerts',
        'reports',
        'audit_logs'
    ]
    LOOP
        EXECUTE format('DROP POLICY IF EXISTS careconnect_public_select ON %I', table_name);
        EXECUTE format('DROP POLICY IF EXISTS careconnect_public_insert ON %I', table_name);
        EXECUTE format('DROP POLICY IF EXISTS careconnect_public_update ON %I', table_name);
        EXECUTE format('CREATE POLICY careconnect_public_select ON %I FOR SELECT TO anon, authenticated USING (true)', table_name);
        EXECUTE format('CREATE POLICY careconnect_public_insert ON %I FOR INSERT TO anon, authenticated WITH CHECK (true)', table_name);
        EXECUTE format('CREATE POLICY careconnect_public_update ON %I FOR UPDATE TO anon, authenticated USING (true) WITH CHECK (true)', table_name);
    END LOOP;
END $$;

-- ============================================================================
-- TRIGGER FUNCTIONS
-- ============================================================================

-- Function 1: Auto-update updated_at timestamp on any record change
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Function 2: Create audit log entry for every data change
CREATE OR REPLACE FUNCTION audit_log_changes()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO audit_logs (action, table_name, record_id, old_values, new_values)
    VALUES (
        TG_OP,
        TG_TABLE_NAME,
        COALESCE(NEW.id::VARCHAR, OLD.id::VARCHAR),
        to_jsonb(OLD),
        to_jsonb(NEW)
    );
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- Function 3: Auto-create notification for appointment changes
CREATE OR REPLACE FUNCTION notify_appointment_change()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        -- Notify patient when appointment status changes
        IF NEW.status IS DISTINCT FROM OLD.status THEN
            INSERT INTO notifications (role, title, body, kind, timestamp, ts, read)
            VALUES (
                'patient',
                'Appointment Status Updated',
                'Your appointment on ' || NEW.date || ' at ' || NEW.time || ' is now ' || NEW.status,
                CASE 
                    WHEN NEW.status = 'Confirmed' THEN 'success'
                    WHEN NEW.status = 'Cancelled' THEN 'warning'
                    ELSE 'info'
                END,
                NOW()::VARCHAR,
                EXTRACT(EPOCH FROM NOW())::DOUBLE PRECISION,
                FALSE
            );
        END IF;
    ELSIF TG_OP = 'INSERT' THEN
        -- Notify doctor of new appointment
        INSERT INTO notifications (role, title, body, kind, timestamp, ts, read)
        VALUES (
            'doctor',
            'New Appointment Booking',
            'Patient ' || NEW.patient_name || ' booked an appointment on ' || NEW.date || ' at ' || NEW.time,
            'info',
            NOW()::VARCHAR,
            EXTRACT(EPOCH FROM NOW())::DOUBLE PRECISION,
            FALSE
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Function 4: Auto-create notification for SOS alerts
CREATE OR REPLACE FUNCTION notify_sos_alert()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO notifications (role, title, body, kind, timestamp, ts, read)
    VALUES (
        'doctor',
        'SOS Emergency Alert',
        'Emergency alert triggered at location: ' || NEW.location,
        'error',
        NOW()::VARCHAR,
        EXTRACT(EPOCH FROM NOW())::DOUBLE PRECISION,
        FALSE
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Function 5: Validate patient data before insert/update
CREATE OR REPLACE FUNCTION validate_patient_data()
RETURNS TRIGGER AS $$
BEGIN
    -- Validate age
    IF NEW.age < 0 OR NEW.age > 150 THEN
        RAISE EXCEPTION 'Invalid age: %', NEW.age;
    END IF;
    
    -- Validate blood group
    IF NEW.blood_group NOT IN ('A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-') THEN
        RAISE EXCEPTION 'Invalid blood group: %', NEW.blood_group;
    END IF;
    
    -- Validate gender
    IF NEW.gender NOT IN ('Male', 'Female', 'Other') THEN
        RAISE EXCEPTION 'Invalid gender: %', NEW.gender;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Function 6: Validate appointment data
CREATE OR REPLACE FUNCTION validate_appointment_data()
RETURNS TRIGGER AS $$
BEGIN
    -- Validate status
    IF NEW.status NOT IN ('Pending', 'Confirmed', 'Cancelled', 'Completed') THEN
        RAISE EXCEPTION 'Invalid appointment status: %', NEW.status;
    END IF;
    
    -- Validate date format (basic check for YYYY-MM-DD)
    IF NEW.date !~ '^\d{4}-\d{2}-\d{2}$' THEN
        RAISE EXCEPTION 'Invalid date format. Use YYYY-MM-DD';
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Function 7: Validate user data
CREATE OR REPLACE FUNCTION validate_user_data()
RETURNS TRIGGER AS $$
BEGIN
    -- Validate role
    IF NEW.role NOT IN ('patient', 'children', 'doctor', 'hospital-admin', 'diagnostic') THEN
        RAISE EXCEPTION 'Invalid user role: %', NEW.role;
    END IF;
    
    -- Email must not be empty
    IF NEW.email IS NULL OR NEW.email = '' THEN
        RAISE EXCEPTION 'Email cannot be empty';
    END IF;
    
    -- Email normalization
    NEW.email_norm = LOWER(TRIM(NEW.email));
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- ATTACH TRIGGERS TO TABLES
-- ============================================================================

-- Trigger: Auto-update timestamps for all tables
CREATE TRIGGER update_users_timestamp BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_patients_timestamp BEFORE UPDATE ON patients
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_doctors_timestamp BEFORE UPDATE ON doctors
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_appointments_timestamp BEFORE UPDATE ON appointments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_consultation_notes_timestamp BEFORE UPDATE ON consultation_notes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_reports_timestamp BEFORE UPDATE ON reports
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Trigger: Audit logging for critical tables
CREATE TRIGGER audit_users_changes AFTER INSERT OR UPDATE OR DELETE ON users
    FOR EACH ROW EXECUTE FUNCTION audit_log_changes();

CREATE TRIGGER audit_patients_changes AFTER INSERT OR UPDATE OR DELETE ON patients
    FOR EACH ROW EXECUTE FUNCTION audit_log_changes();

CREATE TRIGGER audit_appointments_changes AFTER INSERT OR UPDATE OR DELETE ON appointments
    FOR EACH ROW EXECUTE FUNCTION audit_log_changes();

CREATE TRIGGER audit_consultation_notes_changes AFTER INSERT OR UPDATE OR DELETE ON consultation_notes
    FOR EACH ROW EXECUTE FUNCTION audit_log_changes();

-- Trigger: Auto-notifications for appointment changes
CREATE TRIGGER appointment_notification AFTER INSERT OR UPDATE ON appointments
    FOR EACH ROW EXECUTE FUNCTION notify_appointment_change();

-- Trigger: Auto-notifications for SOS alerts
CREATE TRIGGER sos_alert_notification AFTER INSERT ON sos_alerts
    FOR EACH ROW EXECUTE FUNCTION notify_sos_alert();

-- Trigger: Validate patient data before insert/update
CREATE TRIGGER validate_patient BEFORE INSERT OR UPDATE ON patients
    FOR EACH ROW EXECUTE FUNCTION validate_patient_data();

-- Trigger: Validate appointment data
CREATE TRIGGER validate_appointment BEFORE INSERT OR UPDATE ON appointments
    FOR EACH ROW EXECUTE FUNCTION validate_appointment_data();

-- Trigger: Validate user data
CREATE TRIGGER validate_user BEFORE INSERT OR UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION validate_user_data();
