import sqlite3
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
import streamlit as st
from config import Config, get_db_connection
import uuid

config = Config()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AuthenticationManager:
    def __init__(self):
        self.config = config
    
    def hash_password(self, password: str) -> str:
        return pwd_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)
    
    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None):
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, config.SECRET_KEY, algorithm=config.ALGORITHM)
        return encoded_jwt
    
    def verify_token(self, token: str) -> Optional[Dict]:
        try:
            payload = jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
            return payload
        except JWTError:
            return None
    
    def register_user(self, username: str, email: str, password: str, full_name: str = "") -> Dict[str, Any]:
        """Register a new user with database storage."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Check if username exists
            cursor.execute("SELECT username FROM users WHERE username = ?", (username,))
            if cursor.fetchone():
                return {"success": False, "message": "Username already exists"}
            
            # Check if email exists
            cursor.execute("SELECT email FROM users WHERE email = ?", (email,))
            if cursor.fetchone():
                return {"success": False, "message": "Email already registered"}
            
            # Hash password
            hashed_password = self.hash_password(password)
            
            # Generate avatar color
            import random
            colors = ["#3B82F6", "#10B981", "#8B5CF6", "#F59E0B", "#EF4444"]
            avatar_color = random.choice(colors)
            
            # Insert user
            cursor.execute('''
            INSERT INTO users (username, email, hashed_password, full_name, avatar_color)
            VALUES (?, ?, ?, ?, ?)
            ''', (username, email, hashed_password, full_name, avatar_color))
            
            conn.commit()
            
            # Create session
            session_id = str(uuid.uuid4())
            cursor.execute('''
            INSERT INTO online_users (username, session_id, status)
            VALUES (?, ?, ?)
            ''', (username, session_id, "online"))
            
            conn.commit()
            
            # Create JWT token
            access_token = self.create_access_token(
                data={"sub": username, "email": email, "session_id": session_id}
            )
            
            return {
                "success": True,
                "message": "Registration successful",
                "access_token": access_token,
                "token_type": "bearer",
                "user": {
                    "username": username,
                    "email": email,
                    "full_name": full_name,
                    "avatar_color": avatar_color,
                    "session_id": session_id
                }
            }
    
    def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate user and return token."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Get user
            cursor.execute('''
            SELECT username, email, hashed_password, full_name, avatar_color 
            FROM users WHERE username = ? AND is_active = 1
            ''', (username,))
            
            user_row = cursor.fetchone()
            if not user_row:
                return None
            
            user = dict(user_row)
            
            # Verify password
            if not self.verify_password(password, user["hashed_password"]):
                return None
            
            # Update last login
            cursor.execute('''
            UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE username = ?
            ''', (username,))
            
            # Create new session
            session_id = str(uuid.uuid4())
            cursor.execute('''
            INSERT OR REPLACE INTO online_users (username, session_id, status)
            VALUES (?, ?, ?)
            ''', (username, session_id, "online"))
            
            conn.commit()
            
            # Create JWT token
            access_token = self.create_access_token(
                data={"sub": username, "email": user["email"], "session_id": session_id}
            )
            
            return {
                "access_token": access_token,
                "token_type": "bearer",
                "user": {
                    "username": username,
                    "email": user["email"],
                    "full_name": user["full_name"],
                    "avatar_color": user["avatar_color"],
                    "session_id": session_id
                }
            }
    
    def logout_user(self, username: str, session_id: str):
        """Logout user by removing session."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM online_users WHERE username = ? AND session_id = ?", 
                         (username, session_id))
            conn.commit()
    
    def get_online_users(self, exclude_username: str = None) -> list:
        """Get list of online users."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            if exclude_username:
                cursor.execute('''
                SELECT u.username, u.email, u.full_name, u.avatar_color, o.status, o.last_heartbeat
                FROM online_users o
                JOIN users u ON o.username = u.username
                WHERE o.username != ? AND u.is_active = 1
                ORDER BY o.last_heartbeat DESC
                ''', (exclude_username,))
            else:
                cursor.execute('''
                SELECT u.username, u.email, u.full_name, u.avatar_color, o.status, o.last_heartbeat
                FROM online_users o
                JOIN users u ON o.username = u.username
                WHERE u.is_active = 1
                ORDER BY o.last_heartbeat DESC
                ''')
            
            return [dict(row) for row in cursor.fetchall()]
    
    def update_user_heartbeat(self, username: str, session_id: str):
        """Update user's last heartbeat."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
            UPDATE online_users 
            SET last_heartbeat = CURRENT_TIMESTAMP 
            WHERE username = ? AND session_id = ?
            ''', (username, session_id))
            conn.commit()
    
    def get_current_user_from_session(self):
        """Get current user from Streamlit session state."""
        if "token" in st.session_state and "user" in st.session_state:
            payload = self.verify_token(st.session_state.token)
            if payload and payload.get("sub") == st.session_state.user.get("username"):
                # Update heartbeat
                self.update_user_heartbeat(
                    st.session_state.user["username"],
                    st.session_state.user["session_id"]
                )
                return st.session_state.user
        return None

# Global instance
auth_manager = AuthenticationManager()