import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'careconnect-dev-secret-key-12345'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEBUG = True
    TEMPLATES_AUTO_RELOAD = True
    
    # Supabase PostgreSQL Configuration
    SUPABASE_URL = os.environ.get('SUPABASE_URL', 'postgresql://user:password@localhost:5432/careconnect')
    DATABASE_URL = os.environ.get('DATABASE_URL', SUPABASE_URL)
    
    # Legacy MongoDB configuration (for fallback/migration purposes)
    MONGODB_URI = os.environ.get('MONGODB_URI', 'mongodb://127.0.0.1:27017')
    MONGODB_DB_NAME = os.environ.get('MONGODB_DB_NAME', 'careconnect')
    
    # Additional production-ready settings can go here

