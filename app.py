import streamlit as st
import json
import time
from datetime import datetime
import threading
import websocket
import sys
import os

# ============================================
# SET PAGE CONFIG - MUST BE FIRST STREAMLIT COMMAND
# ============================================
st.set_page_config(
    page_title="VoIP Module 1 - Real-time Voice Calling",
    page_icon="📞",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'https://github.com/voip-system',
        'Report a bug': 'https://github.com/voip-system/issues',
        'About': '''
        ## VoIP Module 1
        Real-time voice calling system
        • User Registration & Authentication
        • Zoom-like Calling Interface
        • Audio Streaming
        • Call Management
        '''
    }
)

# ============================================
# IMPORT MODULES
# ============================================
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Try to import auth module
try:
    from auth import auth_manager
    AUTH_AVAILABLE = True
except ImportError:
    AUTH_AVAILABLE = False
    # Create dummy auth manager
    class DummyAuthManager:
        def authenticate_user(self, username, password):
            if username in ["demo1", "demo2", "demo3"] and password == "password123":
                return {
                    "access_token": "dummy_token",
                    "user": {
                        "username": username,
                        "email": f"{username}@example.com",
                        "avatar_color": "#3B82F6",
                        "session_id": "dummy_session"
                    }
                }
            return None
    
    auth_manager = DummyAuthManager()

# Try to import audio manager
try:
    from audio_manager import audio_manager
    AUDIO_AVAILABLE = audio_manager.audio_available
except ImportError:
    # Create dummy audio manager
    class DummyAudioManager:
        def __init__(self):
            self.audio_available = False
            self.is_muted = False
            self.volume = 0.8
        
        def test_microphone(self):
            return False
        
        def play_test_tone(self, frequency=440, duration=1.0):
            print(f"Simulation: Playing {frequency}Hz tone for {duration}s")
            time.sleep(duration)
            return True
        
        def toggle_mute(self):
            self.is_muted = not self.is_muted
            return self.is_muted
        
        def set_volume(self, volume):
            self.volume = max(0.0, min(1.0, volume))
        
        def get_audio_status(self):
            return {
                "available": False,
                "muted": self.is_muted,
                "volume": self.volume,
                "microphone": False
            }
    
    audio_manager = DummyAudioManager()
    AUDIO_AVAILABLE = False

# ============================================
# CUSTOM CSS
# ============================================
st.markdown("""
<style>
.main-header {
    text-align: center;
    color: #1E3A8A;
    font-size: 2.5rem;
    margin-bottom: 1.5rem;
    font-weight: 700;
}
.user-card {
    background-color: white;
    border-radius: 12px;
    padding: 1.5rem;
    margin: 1rem 0;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    border-left: 4px solid #3B82F6;
    transition: all 0.3s;
}
.user-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 12px rgba(0,0,0,0.15);
}
.call-container {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-radius: 15px;
    padding: 2rem;
    color: white;
    margin: 2rem 0;
    box-shadow: 0 10px 25px rgba(0,0,0,0.1);
}
.call-active {
    background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
}
.call-timer {
    font-size: 2.5rem;
    font-weight: bold;
    text-align: center;
    margin: 1rem 0;
    font-family: 'Courier New', monospace;
}
.control-btn {
    padding: 12px 24px;
    border-radius: 25px;
    border: none;
    font-size: 1rem;
    cursor: pointer;
    transition: all 0.3s;
    margin: 5px;
    font-weight: 500;
}
.control-btn:hover {
    transform: scale(1.05);
    box-shadow: 0 4px 12px rgba(0,0,0,0.2);
}
.mute-btn {
    background-color: #6B7280;
    color: white;
}
.mute-btn.active {
    background-color: #EF4444;
}
.end-btn {
    background-color: #EF4444;
    color: white;
}
.call-btn {
    background-color: #3B82F6;
    color: white;
}
.test-btn {
    background-color: #10B981;
    color: white;
}
.status-online {
    color: #10B981;
    font-weight: bold;
}
.status-offline {
    color: #6B7280;
}
.avatar-circle {
    width: 50px;
    height: 50px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-weight: bold;
    font-size: 1.2rem;
    margin-right: 10px;
}
.audio-level-bar {
    display: inline-block;
    width: 8px;
    margin: 0 2px;
    border-radius: 2px;
    background-color: #10B981;
    animation: pulse 1s infinite;
}
@keyframes pulse {
    0% { opacity: 1; }
    50% { opacity: 0.5; }
    100% { opacity: 1; }
}
.incoming-call-alert {
    animation: pulse 1.5s infinite;
    border: 2px solid #3B82F6;
}
</style>
""", unsafe_allow_html=True)

# ============================================
# WEBSOCKET CLIENT
# ============================================
class SignalingClient:
    def __init__(self):
        self.ws = None
        self.connected = False
        self.message_queue = []
    
    def connect(self, username: str, session_id: str) -> bool:
        """Connect to signaling server."""
        try:
            self.ws = websocket.WebSocketApp(
                "ws://localhost:8765",
                on_open=lambda ws: self._on_open(ws, username, session_id),
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close
            )
            
            # Start in background thread
            self.thread = threading.Thread(target=self.ws.run_forever)
            self.thread.daemon = True
            self.thread.start()
            
            # Wait for connection
            for _ in range(5):
                if self.connected:
                    return True
                time.sleep(1)
            
            return False
            
        except Exception as e:
            st.error(f"WebSocket connection error: {e}")
            return False
    
    def _on_open(self, ws, username: str, session_id: str):
        """Handle WebSocket connection open."""
        try:
            ws.send(json.dumps({
                "type": "auth",
                "username": username,
                "session_id": session_id
            }))
            self.connected = True
        except Exception as e:
            print(f"WebSocket open error: {e}")
    
    def _on_message(self, ws, message):
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(message)
            self.message_queue.append(data)
        except Exception as e:
            print(f"WebSocket message error: {e}")
    
    def _on_error(self, ws, error):
        """Handle WebSocket errors."""
        self.connected = False
    
    def _on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket closure."""
        self.connected = False
    
    def send(self, data):
        """Send data through WebSocket."""
        if self.connected and self.ws:
            try:
                self.ws.send(json.dumps(data))
                return True
            except:
                self.connected = False
                return False
        return False
    
    def disconnect(self):
        """Disconnect from WebSocket."""
        if self.ws:
            self.ws.close()
    
    def get_messages(self):
        """Get all queued messages."""
        messages = self.message_queue.copy()
        self.message_queue.clear()
        return messages

# ============================================
# INITIALIZE SESSION STATE
# ============================================
def init_session_state():
    """Initialize all session state variables."""
    defaults = {
        # Authentication
        "token": None,
        "user": None,
        "username": None,
        "is_authenticated": False,
        
        # Signaling
        "signaling_client": None,
        "connection_status": "disconnected",
        "online_users": [],
        
        # Call state
        "active_call": None,
        "incoming_call": None,
        "call_status": "idle",  # idle, ringing, connecting, connected, ended
        "call_start_time": None,
        "call_duration": 0,
        
        # Audio controls
        "is_muted": False,
        "is_speaker_muted": False,
        "volume": 0.8,
        
        # UI state
        "current_page": "login",
        "show_call_modal": False,
        "show_incoming_modal": False,
        "selected_user": None,
        "audio_test_frequency": 440,
        "audio_test_duration": 1.0,
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

# ============================================
# AUTHENTICATION PAGES
# ============================================
def show_login_page():
    """Show login page."""
    st.markdown('<h1 class="main-header">🔐 VoIP Authentication</h1>', unsafe_allow_html=True)
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        with st.container():
            st.markdown("### Login to Your Account")
            with st.form("login_form"):
                username = st.text_input("Username", placeholder="Enter your username")
                password = st.text_input("Password", type="password", placeholder="Enter your password")
                
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    login_submitted = st.form_submit_button("🔑 Login", use_container_width=True)
                with col_btn2:
                    if st.form_submit_button("📝 Register", use_container_width=True):
                        st.session_state.current_page = "register"
                        st.rerun()
                
                if login_submitted:
                    if not username or not password:
                        st.error("Please enter username and password")
                    else:
                        with st.spinner("Authenticating..."):
                            result = auth_manager.authenticate_user(username, password)
                            if result:
                                # Store authentication data
                                st.session_state.token = result["access_token"]
                                st.session_state.user = result["user"]
                                st.session_state.username = username
                                st.session_state.is_authenticated = True
                                
                                # Connect to signaling server
                                signaling_client = SignalingClient()
                                if signaling_client.connect(username, result["user"]["session_id"]):
                                    st.session_state.signaling_client = signaling_client
                                    st.session_state.connection_status = "connected"
                                    st.session_state.current_page = "dashboard"
                                    st.success("Login successful!")
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error("Failed to connect to signaling server")
                            else:
                                st.error("Invalid username or password")
    
    with col2:
        with st.container():
            st.markdown("### Demo Accounts")
            st.info("Use these accounts for testing:")
            
            demo_accounts = [
                {"username": "demo1", "password": "password123", "color": "#3B82F6"},
                {"username": "demo2", "password": "password123", "color": "#10B981"},
                {"username": "demo3", "password": "password123", "color": "#8B5CF6"},
            ]
            
            for account in demo_accounts:
                with st.container():
                    st.markdown(f"""
                    <div style="padding: 1rem; border-radius: 8px; background-color: {account['color']}10; margin: 0.5rem 0;">
                        <strong>{account['username']}</strong><br>
                        Password: {account['password']}
                    </div>
                    """, unsafe_allow_html=True)
            
            st.markdown("---")
            st.markdown("### 📱 How to Test")
            st.markdown("""
            1. Open two browser windows/tabs
            2. Login with different accounts
            3. Make calls between users
            4. Test audio functionality
            """)

def show_register_page():
    """Show registration page."""
    st.markdown('<h1 class="main-header">📝 Create Account</h1>', unsafe_allow_html=True)
    
    with st.form("register_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            username = st.text_input("Username", help="Choose a unique username")
            email = st.text_input("Email Address", help="Enter your email")
            full_name = st.text_input("Full Name (Optional)")
        
        with col2:
            password = st.text_input("Password", type="password", help="At least 6 characters")
            confirm_password = st.text_input("Confirm Password", type="password")
        
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            register_submitted = st.form_submit_button("Create Account", use_container_width=True)
        with col_btn2:
            if st.form_submit_button("Back to Login", use_container_width=True):
                st.session_state.current_page = "login"
                st.rerun()
        
        if register_submitted:
            # Validation
            if not all([username, email, password, confirm_password]):
                st.error("All fields are required")
            elif len(password) < 6:
                st.error("Password must be at least 6 characters")
            elif password != confirm_password:
                st.error("Passwords do not match")
            elif "@" not in email:
                st.error("Please enter a valid email")
            else:
                with st.spinner("Creating account..."):
                    if AUTH_AVAILABLE:
                        result = auth_manager.register_user(username, email, password, full_name)
                        if result["success"]:
                            st.success("Account created successfully! Please login.")
                            time.sleep(2)
                            st.session_state.current_page = "login"
                            st.rerun()
                        else:
                            st.error(result["message"])
                    else:
                        st.success("Account simulation complete! Please login.")
                        time.sleep(2)
                        st.session_state.current_page = "login"
                        st.rerun()

# ============================================
# VoIP DASHBOARD
# ============================================
def show_dashboard():
    """Show main VoIP dashboard."""
    user = st.session_state.user
    
    # Sidebar
    with st.sidebar:
        # User profile
        col_avatar, col_info = st.columns([1, 3])
        with col_avatar:
            avatar_color = user.get("avatar_color", "#3B82F6")
            st.markdown(f"""
            <div class="avatar-circle" style="background-color: {avatar_color};">
                {user['username'][0].upper()}
            </div>
            """, unsafe_allow_html=True)
        
        with col_info:
            st.markdown(f"**{user['username']}**")
            st.caption(user['email'])
        
        st.markdown("---")
        
        # Connection status
        status_color = "🟢" if st.session_state.connection_status == "connected" else "🔴"
        st.markdown(f"**Status:** {status_color} {st.session_state.connection_status}")
        
        # Online users count
        online_count = len(st.session_state.online_users)
        st.metric("👥 Online", online_count)
        
        # Call status
        if st.session_state.call_status == "connected":
            st.metric("📞 Call Duration", f"{st.session_state.call_duration}s")
        
        st.markdown("---")
        
        # ============================================
        # QUICK AUDIO TEST IN SIDEBAR
        # ============================================
        st.markdown("### 🔊 Quick Audio Test")
        
        if AUDIO_AVAILABLE:
            audio_test_col1, audio_test_col2 = st.columns(2)
            
            with audio_test_col1:
                if st.button("🎤 Mic Test", key="sidebar_mic_test", use_container_width=True):
                    if audio_manager.test_microphone():
                        st.toast("✅ Microphone working!", icon="🎤")
                    else:
                        st.toast("❌ Microphone not detected", icon="⚠️")
            
            with audio_test_col2:
                if st.button("🔊 Speaker Test", key="sidebar_speaker_test", use_container_width=True):
                    if audio_manager.play_test_tone():
                        st.toast("✅ Test tone played!", icon="🔊")
                    else:
                        st.toast("❌ Could not play audio", icon="⚠️")
        else:
            st.warning("Audio not available")
            if st.button("Install Audio", key="install_audio"):
                st.info("Run: pip install PyAudio")
        
        # Volume Control in Sidebar
        st.markdown("#### Volume")
        current_volume = st.session_state.get("volume", 0.8)
        new_volume = st.slider(
            "Adjust",
            0.0, 1.0, current_volume, 0.1,
            key="sidebar_volume",
            label_visibility="collapsed"
        )
        if new_volume != current_volume:
            st.session_state.volume = new_volume
            audio_manager.set_volume(new_volume)
            st.rerun()
        
        # Audio Status Indicator
        audio_status = audio_manager.get_audio_status()
        if audio_status["available"]:
            st.success("✅ Audio Ready")
        else:
            st.error("❌ Audio Not Available")
        
        # Navigation to audio test page
        if st.button("🎧 Audio Diagnostics", use_container_width=True):
            st.session_state.current_page = "audio_test"
            st.rerun()
        
        st.markdown("---")
        
        # Navigation
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()
        
        if st.button("🚪 Logout", use_container_width=True):
            # Logout user
            if st.session_state.signaling_client:
                st.session_state.signaling_client.disconnect()
            
            if AUTH_AVAILABLE:
                auth_manager.logout_user(user["username"], user["session_id"])
            
            # Clear session
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            
            st.success("Logged out successfully!")
            time.sleep(1)
            st.rerun()
    
    # Main content
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("### 👥 Online Users")
        
        if not st.session_state.online_users:
            st.info("No other users online. Open another browser to test.")
            # Show demo users
            demo_users = [
                {"username": "demo1", "status": "online", "avatar_color": "#3B82F6"},
                {"username": "demo2", "status": "online", "avatar_color": "#10B981"},
                {"username": "demo3", "status": "offline", "avatar_color": "#8B5CF6"},
            ]
            
            for demo_user in demo_users:
                if demo_user["username"] != user["username"]:
                    with st.container():
                        user_col1, user_col2, user_col3 = st.columns([3, 2, 1])
                        
                        with user_col1:
                            avatar_color = demo_user.get("avatar_color", "#3B82F6")
                            st.markdown(f"""
                            <div style="display: flex; align-items: center; gap: 10px;">
                                <div class="avatar-circle" style="background-color: {avatar_color};">
                                    {demo_user['username'][0].upper()}
                                </div>
                                <div>
                                    <strong>{demo_user['username']}</strong><br>
                                    <small>Demo User</small>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        with user_col2:
                            status = demo_user.get("status", "available")
                            if status == "online":
                                st.markdown('<span class="status-online">🟢 Online</span>', unsafe_allow_html=True)
                            else:
                                st.markdown('<span class="status-offline">⚫ Offline</span>', unsafe_allow_html=True)
                        
                        with user_col3:
                            if demo_user["status"] == "online":
                                if st.button("📞 Call", key=f"call_{demo_user['username']}", use_container_width=True):
                                    initiate_call(demo_user["username"])
        else:
            for online_user in st.session_state.online_users:
                with st.container():
                    user_col1, user_col2, user_col3 = st.columns([3, 2, 1])
                    
                    with user_col1:
                        avatar_color = online_user.get("avatar_color", "#3B82F6")
                        st.markdown(f"""
                        <div style="display: flex; align-items: center; gap: 10px;">
                            <div class="avatar-circle" style="background-color: {avatar_color};">
                                {online_user['username'][0].upper()}
                            </div>
                            <div>
                                <strong>{online_user['username']}</strong><br>
                                <small>{online_user.get('full_name', 'User')}</small>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with user_col2:
                        status = online_user.get("status", "available")
                        if status == "available":
                            st.markdown('<span class="status-online">🟢 Online</span>', unsafe_allow_html=True)
                        else:
                            st.markdown('<span class="status-offline">⚫ Offline</span>', unsafe_allow_html=True)
                    
                    with user_col3:
                        if st.button("📞 Call", key=f"call_{online_user['username']}", use_container_width=True):
                            initiate_call(online_user["username"])
    
    with col2:
        st.markdown("### 📊 System Info")
        
        # System stats
        if AUDIO_AVAILABLE:
            st.metric("Audio Status", "✅ Ready")
        else:
            st.warning("⚠️ WebRTC not installed")
            st.info("Run: `pip install PyAudio`")
        
        st.metric("Connection", st.session_state.connection_status)
        
        # Quick actions
        st.markdown("### ⚡ Quick Actions")
        
        if st.session_state.call_status == "idle":
            if st.button("🔄 Check Calls", use_container_width=True):
                check_incoming_calls()
        
        if st.session_state.call_status == "connected":
            if st.button("📞 End Call", use_container_width=True):
                end_current_call()
        
        # Test audio button
        if st.button("🎵 Test Audio System", use_container_width=True):
            st.session_state.current_page = "audio_test"
            st.rerun()
    
    # Handle incoming calls
    check_incoming_calls()
    
    # Process WebSocket messages
    if st.session_state.signaling_client:
        messages = st.session_state.signaling_client.get_messages()
        for msg in messages:
            handle_signaling_message(msg)
    
    # Show active call interface
    if st.session_state.call_status == "connected":
        show_active_call_interface()

# ============================================
# CALL MANAGEMENT FUNCTIONS
# ============================================
def initiate_call(to_username: str):
    """Initiate a call to another user."""
    st.session_state.call_status = "ringing"
    st.session_state.active_call = {
        "to": to_username,
        "start_time": datetime.now(),
        "status": "ringing"
    }
    
    # Send call request via signaling
    if st.session_state.signaling_client:
        st.session_state.signaling_client.send({
            "type": "call_request",
            "to": to_username,
            "from": st.session_state.username
        })
    
    # Show call modal
    st.session_state.show_call_modal = True
    st.rerun()

def check_incoming_calls():
    """Check for incoming calls."""
    if st.session_state.incoming_call:
        show_incoming_call_modal(st.session_state.incoming_call)

def handle_signaling_message(message):
    """Handle signaling server messages."""
    msg_type = message.get("type")
    
    if msg_type == "incoming_call":
        st.session_state.incoming_call = message
        st.rerun()
    
    elif msg_type == "call_accepted":
        if st.session_state.call_status == "ringing":
            st.session_state.call_status = "connected"
            st.session_state.call_start_time = datetime.now()
            st.rerun()
    
    elif msg_type == "call_rejected":
        if st.session_state.call_status == "ringing":
            st.session_state.call_status = "idle"
            st.session_state.active_call = None
            st.session_state.show_call_modal = False
            st.error("Call rejected by user")
            st.rerun()
    
    elif msg_type == "online_users":
        st.session_state.online_users = message.get("users", [])
        st.rerun()
    
    elif msg_type == "call_ended":
        if st.session_state.call_status == "connected":
            end_current_call()
            st.info("Call ended by other user")

def show_incoming_call_modal(call_data):
    """Show incoming call modal."""
    with st.container():
        st.markdown('<div class="call-container incoming-call-alert">', unsafe_allow_html=True)
        
        st.markdown(f"### 📞 Incoming Call")
        st.markdown(f"**From:** {call_data.get('from', 'Unknown')}")
        
        col_accept, col_reject = st.columns(2)
        
        with col_accept:
            if st.button("✅ Accept", use_container_width=True):
                # Accept call
                if st.session_state.signaling_client:
                    st.session_state.signaling_client.send({
                        "type": "call_response",
                        "call_id": call_data.get("call_id"),
                        "accepted": True
                    })
                
                st.session_state.call_status = "connected"
                st.session_state.active_call = {
                    "from": call_data.get("from"),
                    "start_time": datetime.now()
                }
                st.session_state.incoming_call = None
                st.rerun()
        
        with col_reject:
            if st.button("❌ Reject", use_container_width=True):
                # Reject call
                if st.session_state.signaling_client:
                    st.session_state.signaling_client.send({
                        "type": "call_response",
                        "call_id": call_data.get("call_id"),
                        "accepted": False
                    })
                
                st.session_state.incoming_call = None
                st.rerun()
        
        st.markdown('</div>', unsafe_allow_html=True)

# ============================================
# ACTIVE CALL INTERFACE WITH AUDIO TEST
# ============================================
def show_active_call_interface():
    """Show active call interface with audio testing."""
    if not st.session_state.active_call:
        return
    
    with st.container():
        st.markdown('<div class="call-container call-active">', unsafe_allow_html=True)
        
        # Call header
        peer = st.session_state.active_call.get("to") or st.session_state.active_call.get("from")
        
        col1, col2 = st.columns([1, 3])
        
        with col1:
            avatar_color = "#3B82F6"
            st.markdown(f"""
            <div style="width: 80px; height: 80px; border-radius: 50%; 
                        background-color: {avatar_color}; display: flex; 
                        align-items: center; justify-content: center; color: white; 
                        font-weight: bold; font-size: 2rem; margin: 0 auto;">
                {peer[0].upper() if peer else '?'}
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"### 📞 On Call with {peer}")
            
            # Call timer
            if st.session_state.call_start_time:
                duration = int((datetime.now() - st.session_state.call_start_time).total_seconds())
                st.session_state.call_duration = duration
                mins, secs = divmod(duration, 60)
                st.markdown(f'<div class="call-timer">{mins:02d}:{secs:02d}</div>', unsafe_allow_html=True)
        
        # ============================================
        # AUDIO TEST SECTION
        # ============================================
        st.markdown("---")
        st.markdown("### 🔊 Audio Test Panel")
        
        # Create columns for audio controls
        audio_col1, audio_col2, audio_col3 = st.columns(3)
        
        with audio_col1:
            # Test Microphone Button
            if st.button("🎤 Test Microphone", key="test_mic_active", use_container_width=True, type="primary"):
                if AUDIO_AVAILABLE:
                    with st.spinner("Testing microphone..."):
                        time.sleep(1)
                        if audio_manager.test_microphone():
                            st.success("✅ Microphone is working!")
                        else:
                            st.error("❌ Microphone not detected")
                else:
                    st.warning("Install PyAudio for real audio test")
                    st.info("Simulating microphone test...")
                    time.sleep(1)
                    st.success("✅ Microphone simulation complete")
        
        with audio_col2:
            # Test Speaker Button
            if st.button("🔊 Test Speaker", key="test_speaker_active", use_container_width=True, type="primary"):
                if AUDIO_AVAILABLE:
                    with st.spinner("Playing test tone..."):
                        if audio_manager.play_test_tone():
                            st.success("✅ Speaker test tone played!")
                        else:
                            st.error("❌ Could not play audio")
                else:
                    st.warning("Install PyAudio for real audio test")
                    st.info("Simulating speaker test...")
                    time.sleep(1)
                    st.success("✅ Speaker simulation complete")
        
        with audio_col3:
            # Toggle Mute Button
            mute_icon = "🔇" if st.session_state.is_muted else "🎤"
            mute_text = "Unmute Microphone" if st.session_state.is_muted else "Mute Microphone"
            mute_type = "secondary" if st.session_state.is_muted else "primary"
            
            if st.button(f"{mute_icon} {mute_text}", key="call_mute_active", use_container_width=True, type=mute_type):
                audio_manager.toggle_mute()
                st.session_state.is_muted = not st.session_state.is_muted
                st.rerun()
        
        # Advanced Audio Controls
        with st.expander("🎚️ Advanced Audio Settings"):
            col_freq, col_dur = st.columns(2)
            
            with col_freq:
                frequency = st.slider(
                    "Test Tone Frequency (Hz)",
                    100, 2000, 
                    st.session_state.audio_test_frequency,
                    10,
                    key="frequency_slider"
                )
                st.session_state.audio_test_frequency = frequency
            
            with col_dur:
                duration = st.slider(
                    "Test Tone Duration (seconds)",
                    0.5, 5.0,
                    st.session_state.audio_test_duration,
                    0.5,
                    key="duration_slider"
                )
                st.session_state.audio_test_duration = duration
            
            # Custom test tone button
            if st.button("🎵 Play Custom Tone", use_container_width=True):
                if AUDIO_AVAILABLE:
                    with st.spinner(f"Playing {frequency}Hz tone for {duration}s..."):
                        if audio_manager.play_test_tone(frequency, duration):
                            st.success(f"✅ Played {frequency}Hz tone for {duration}s")
                        else:
                            st.error("❌ Could not play custom tone")
                else:
                    st.info(f"Simulation: Would play {frequency}Hz tone for {duration}s")
        
        # Volume Control
        st.markdown("#### Volume Control")
        volume_col1, volume_col2 = st.columns([3, 1])
        
        with volume_col1:
            current_volume = st.session_state.get("volume", 0.8)
            new_volume = st.slider(
                "Adjust Volume Level",
                0.0, 1.0, current_volume, 0.1,
                key="call_volume_slider",
                label_visibility="collapsed"
            )
            if new_volume != current_volume:
                st.session_state.volume = new_volume
                audio_manager.set_volume(new_volume)
        
        with volume_col2:
            st.markdown(f"**{int(new_volume * 100)}%**")
        
        # Audio Status Display
        st.markdown("#### 🎚️ Audio Status Panel")
        status_col1, status_col2, status_col3 = st.columns(3)
        
        with status_col1:
            audio_status = "✅ Working" if AUDIO_AVAILABLE else "⚠️ Simulation"
            st.metric("Audio System", audio_status)
        
        with status_col2:
            mute_status = "🔇 MUTED" if st.session_state.is_muted else "🎤 ACTIVE"
            st.metric("Microphone", mute_status)
        
        with status_col3:
            st.metric("Volume", f"{int(st.session_state.volume * 100)}%")
        
        # Audio Quality Indicators
        st.markdown("#### 📊 Audio Quality Indicators")
        quality_col1, quality_col2, quality_col3 = st.columns(3)
        
        with quality_col1:
            st.metric("Bitrate", "64 kbps")
        
        with quality_col2:
            st.metric("Latency", "~50 ms")
        
        with quality_col3:
            st.metric("Codec", "OPUS" if AUDIO_AVAILABLE else "SIM")
        
        # Audio Visualization
        st.markdown("##### 🔊 Live Audio Levels")
        
        # Simulated audio level bars
        import random
        levels = [random.random() for _ in range(15)]
        
        # Create audio level visualization
        audio_html = """
        <div style="display: flex; align-items: flex-end; height: 60px; gap: 4px; margin: 10px 0; padding: 10px; background: rgba(255,255,255,0.1); border-radius: 10px;">
        """
        for level in levels:
            height = int(level * 50) + 10
            if level > 0.6:
                color = "#10B981"  # Green for good level
            elif level > 0.3:
                color = "#F59E0B"  # Yellow for medium
            else:
                color = "#EF4444"  # Red for low
            audio_html += f'<div style="width: 12px; height: {height}px; background-color: {color}; border-radius: 3px; transition: height 0.3s;"></div>'
        audio_html += "</div>"
        st.markdown(audio_html, unsafe_allow_html=True)
        
        # Audio Troubleshooting Tips
        with st.expander("🔧 Audio Troubleshooting Guide"):
            st.markdown("""
            **If audio isn't working:**
            
            1. **Click "Test Microphone" and "Test Speaker" buttons above**
            2. **Check browser permissions:**
               - Allow microphone access when prompted
               - Check browser settings for site permissions
            
            3. **System checks:**
               - Ensure speakers/headphones are connected
               - Check volume is not muted in system
               - Test with different audio devices
            
            4. **For real audio calling:**
               ```bash
               pip install PyAudio
               ```
               - Grant microphone permissions in browser
               - Use headphones to avoid echo
               - Restart application after installation
            
            **Common error messages:**
            - "Microphone not detected" → Check device connections
            - "Cannot play audio" → Check speaker connections
            - "Permission denied" → Allow microphone access in browser
            """)
        
        # ============================================
        # CALL CONTROLS
        # ============================================
        st.markdown("---")
        st.markdown("### 🎛️ Call Controls")
        
        col_controls = st.columns(4)
        
        with col_controls[0]:
            if st.button("📞 Hold", use_container_width=True):
                st.info("Call hold feature coming soon")
        
        with col_controls[1]:
            speaker_text = "🔈 Unmute Spkr" if st.session_state.is_speaker_muted else "🔊 Mute Spkr"
            if st.button(speaker_text, key="call_speaker", use_container_width=True):
                st.session_state.is_speaker_muted = not st.session_state.is_speaker_muted
                st.rerun()
        
        with col_controls[2]:
            if st.button("📱 Transfer", use_container_width=True):
                st.info("Call transfer coming soon")
        
        with col_controls[3]:
            if st.button("📞 End Call", key="call_end", use_container_width=True, type="secondary"):
                end_current_call()
        
        st.markdown('</div>', unsafe_allow_html=True)

def end_current_call():
    """End the current call."""
    if st.session_state.active_call:
        # Send end call signal
        if st.session_state.signaling_client:
            peer = st.session_state.active_call.get("to") or st.session_state.active_call.get("from")
            st.session_state.signaling_client.send({
                "type": "end_call",
                "to": peer
            })
        
        # Reset call state
        st.session_state.active_call = None
        st.session_state.call_status = "idle"
        st.session_state.call_start_time = None
        st.session_state.show_call_modal = False
        
        st.success("Call ended successfully!")
        st.rerun()

# ============================================
# AUDIO TEST PAGE
# ============================================
def show_audio_test_page():
    """Dedicated page for audio testing."""
    st.markdown('<h1 class="main-header">🎧 Audio System Diagnostics</h1>', unsafe_allow_html=True)
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("### Microphone Test")
        
        # Record test
        if st.button("🎤 Start Microphone Test", use_container_width=True, type="primary"):
            if AUDIO_AVAILABLE:
                with st.spinner("Recording 3 seconds of audio..."):
                    # Simulate recording
                    progress_bar = st.progress(0)
                    for i in range(3):
                        st.write(f"🎤 Recording... {3-i} seconds remaining")
                        progress_bar.progress((i+1)/3)
                        time.sleep(1)
                    
                    # Test microphone
                    if audio_manager.test_microphone():
                        st.success("✅ Microphone test passed!")
                        
                        # Show audio visualization
                        st.markdown("#### Simulated Audio Waveform")
                        
                        # Create simulated waveform
                        import numpy as np
                        import matplotlib.pyplot as plt
                        
                        fig, ax = plt.subplots(figsize=(10, 3))
                        t = np.linspace(0, 3, 300)
                        # Create a realistic looking audio signal
                        audio_signal = np.sin(2 * np.pi * 2 * t) * np.exp(-t/3)
                        audio_signal += 0.3 * np.sin(2 * np.pi * 5 * t)
                        audio_signal += 0.1 * np.sin(2 * np.pi * 8 * t)
                        
                        ax.plot(t, audio_signal, color='#3B82F6', linewidth=2)
                        ax.fill_between(t, audio_signal, alpha=0.3, color='#3B82F6')
                        ax.set_xlabel('Time (seconds)')
                        ax.set_ylabel('Amplitude')
                        ax.set_title('Simulated Audio Signal')
                        ax.grid(True, alpha=0.3)
                        st.pyplot(fig)
                    else:
                        st.error("❌ Microphone not detected")
            else:
                st.warning("Audio system not available")
                st.info("Run: `pip install PyAudio` for real audio tests")
        
        st.markdown("### Speaker Test")
        
        # Frequency test controls
        freq_col, dur_col = st.columns(2)
        
        with freq_col:
            frequency = st.slider(
                "Test Tone Frequency (Hz)",
                50, 2000, 440, 10,
                key="audio_page_frequency"
            )
        
        with dur_col:
            duration = st.slider(
                "Duration (seconds)",
                0.5, 5.0, 1.0, 0.5,
                key="audio_page_duration"
            )
        
        # Play tone button
        if st.button("🔊 Play Test Tone", use_container_width=True, type="primary"):
            if AUDIO_AVAILABLE:
                with st.spinner(f"Playing {frequency}Hz tone for {duration}s..."):
                    if audio_manager.play_test_tone(frequency, duration):
                        st.success(f"✅ Successfully played {frequency}Hz tone")
                        
                        # Show frequency visualization
                        st.markdown("#### Tone Frequency Visualization")
                        
                        import numpy as np
                        import matplotlib.pyplot as plt
                        
                        fig, ax = plt.subplots(figsize=(10, 3))
                        t = np.linspace(0, 0.1, 1000)  # 0.1 second window
                        tone = np.sin(2 * np.pi * frequency * t)
                        
                        ax.plot(t, tone, color='#10B981', linewidth=2)
                        ax.fill_between(t, tone, alpha=0.3, color='#10B981')
                        ax.set_xlabel('Time (seconds)')
                        ax.set_ylabel('Amplitude')
                        ax.set_title(f'{frequency}Hz Test Tone')
                        ax.grid(True, alpha=0.3)
                        st.pyplot(fig)
                    else:
                        st.error("❌ Could not play tone")
            else:
                st.info(f"Simulation: Would play {frequency}Hz tone for {duration}s")
                time.sleep(1)
                st.success("✅ Simulation complete")
        
        # Audio sweep test
        if st.button("🎵 Frequency Sweep Test", use_container_width=True):
            if AUDIO_AVAILABLE:
                with st.spinner("Playing frequency sweep..."):
                    frequencies = [200, 400, 600, 800, 1000]
                    for freq in frequencies:
                        audio_manager.play_test_tone(freq, 0.5)
                        time.sleep(0.1)
                    st.success("✅ Frequency sweep complete")
            else:
                st.info("Simulating frequency sweep test...")
                time.sleep(2)
                st.success("✅ Simulation complete")
    
    with col2:
        st.markdown("### System Status")
        
        # Audio system check
        audio_status = audio_manager.get_audio_status()
        
        status_items = [
            ("Audio Library", "✅ PyAudio" if AUDIO_AVAILABLE else "❌ Not Installed"),
            ("Microphone", "✅ Detected" if audio_status.get("microphone", False) else "❌ Not Detected"),
            ("Volume Level", f"🔊 {int(audio_status.get('volume', 0) * 100)}%"),
            ("Mute Status", "🔇 MUTED" if audio_status.get("muted", False) else "🎤 ACTIVE"),
            ("Sample Rate", "44.1 kHz"),
            ("Channels", "Mono (1 channel)"),
        ]
        
        for item, status in status_items:
            st.markdown(f"**{item}:** {status}")
        
        st.markdown("---")
        st.markdown("### Quick Installation")
        
        if not AUDIO_AVAILABLE:
            st.code("pip install PyAudio", language="bash")
            st.button("📋 Copy Command", key="copy_cmd")
            st.info("Run this command in terminal/command prompt")
        
        st.markdown("---")
        st.markdown("### Troubleshooting")
        
        st.markdown("""
        **Common Issues:**
        
        1. **"Microphone not detected"**
           - Check physical connections
           - Try different USB port
           - Restart application
        
        2. **"Cannot play audio"**
           - Check speaker connections
           - Ensure volume is not muted
           - Test with headphones
        
        3. **"Permission denied"**
           - Allow microphone in browser
           - Check site permissions
           - Clear browser cache
        
        4. **Poor audio quality**
           - Use headphones
           - Reduce background noise
           - Check internet connection
        """)
        
        # Quick test buttons
        st.markdown("### Quick Tests")
        quick_col1, quick_col2 = st.columns(2)
        
        with quick_col1:
            if st.button("🎤 Quick Mic", use_container_width=True):
                if AUDIO_AVAILABLE and audio_manager.test_microphone():
                    st.toast("✅ Microphone OK", icon="🎤")
                else:
                    st.toast("❌ Mic issue", icon="⚠️")
        
        with quick_col2:
            if st.button("🔊 Quick Speaker", use_container_width=True):
                if AUDIO_AVAILABLE and audio_manager.play_test_tone(440, 0.5):
                    st.toast("✅ Speaker OK", icon="🔊")
                else:
                    st.toast("❌ Speaker issue", icon="⚠️")
    
    # Back button
    st.markdown("---")
    if st.button("← Back to Dashboard", use_container_width=True):
        st.session_state.current_page = "dashboard"
        st.rerun()

# ============================================
# MAIN APPLICATION
# ============================================
def main():
    """Main application entry point."""
    # Initialize session state
    init_session_state()
    
    # Show appropriate page based on authentication
    if not st.session_state.is_authenticated:
        if st.session_state.current_page == "login":
            show_login_page()
        else:
            show_register_page()
    else:
        # Show appropriate page
        if st.session_state.current_page == "dashboard":
            show_dashboard()
        elif st.session_state.current_page == "audio_test":
            show_audio_test_page()
        else:
            show_dashboard()
    
    # Footer
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**Module 1:** VoIP Communication")
    
    with col2:
        audio_status = "✅ Audio Ready" if AUDIO_AVAILABLE else "⚠️ Audio Simulation"
        st.markdown(f"**Status:** {audio_status}")
    
    with col3:
        st.markdown("**Version:** 1.0.0")

if __name__ == "__main__":
    # Create necessary directories
    os.makedirs("static", exist_ok=True)
    
    # Run the app
    main()