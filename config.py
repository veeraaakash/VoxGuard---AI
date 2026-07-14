import os
import sqlite3
from datetime import datetime, timedelta
from dotenv import load_dotenv
from contextlib import contextmanager
import json

load_dotenv()

class Config:
    # JWT Configuration
    SECRET_KEY = os.getenv("SECRET_KEY", "voip-module1-secret-key")
    ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60))
    
    # WebRTC Configuration - Using free STUN servers
    RTC_CONFIGURATION = {
        "iceServers": [
            {"urls": ["stun:stun.l.google.com:19302"]},
            {"urls": ["stun:stun1.l.google.com:19302"]},
            {"urls": ["stun:stun2.l.google.com:19302"]},
            {"urls": ["stun:stun3.l.google.com:19302"]},
            {"urls": ["stun:stun4.l.google.com:19302"]},
        ]
    }
    
    # Media Constraints
    MEDIA_CONSTRAINTS = {
        "audio": {
            "echoCancellation": True,
            "noiseSuppression": True,
            "autoGainControl": True
        },
        "video": False
    }
    
    # Signaling Server
    SIGNALING_SERVER_URL = f"ws://{os.getenv('SIGNALING_SERVER_HOST', 'localhost')}:{os.getenv('SIGNALING_SERVER_PORT', '8765')}"
    
    # Audio Settings
    AUDIO_SAMPLE_RATE = 48000
    AUDIO_CHANNELS = 1

# Initialize database
def init_database():
    """Initialize SQLite database for user storage."""
    conn = sqlite3.connect('voip_users.db')
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        hashed_password TEXT NOT NULL,
        full_name TEXT,
        avatar_color TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_login TIMESTAMP,
        is_active BOOLEAN DEFAULT 1
    )
    ''')
    
    # Call history table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS call_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        call_id TEXT UNIQUE NOT NULL,
        caller_username TEXT NOT NULL,
        receiver_username TEXT NOT NULL,
        status TEXT NOT NULL,
        start_time TIMESTAMP,
        end_time TIMESTAMP,
        duration INTEGER,
        call_type TEXT DEFAULT 'audio',
        FOREIGN KEY (caller_username) REFERENCES users(username),
        FOREIGN KEY (receiver_username) REFERENCES users(username)
    )
    ''')
    
    # Online users table (temporary)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS online_users (
        username TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        ip_address TEXT,
        user_agent TEXT,
        last_heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'available',
        FOREIGN KEY (username) REFERENCES users(username)
    )
    ''')
    
    # Create demo users if they don't exist
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    demo_users = [
        ("demo1", "demo1@voip.com", pwd_context.hash("password123"), "Demo User 1", "#3B82F6"),
        ("demo2", "demo2@voip.com", pwd_context.hash("password123"), "Demo User 2", "#10B981"),
        ("demo3", "demo3@voip.com", pwd_context.hash("password123"), "Demo User 3", "#8B5CF6"),
    ]
    
    for username, email, hashed_password, full_name, avatar_color in demo_users:
        cursor.execute('''
        INSERT OR IGNORE INTO users (username, email, hashed_password, full_name, avatar_color)
        VALUES (?, ?, ?, ?, ?)
        ''', (username, email, hashed_password, full_name, avatar_color))
    
    conn.commit()
    conn.close()

# Initialize database on import
init_database()

@contextmanager
def get_db_connection():
    """Get database connection with context manager."""
    conn = sqlite3.connect('voip_users.db')
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

config = Config()