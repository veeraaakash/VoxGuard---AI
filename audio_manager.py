import time
import numpy as np

class AudioManager:
    """Simple audio manager for VoIP calls."""
    
    def __init__(self):
        self.is_muted = False
        self.volume = 0.8
        self.sample_rate = 44100
        
        # Try to import PyAudio
        try:
            import pyaudio
            self.pyaudio = pyaudio
            self.p = pyaudio.PyAudio()
            self.audio_available = True
            print("✅ PyAudio loaded successfully")
        except ImportError:
            print("⚠️ PyAudio not installed. Running in simulation mode.")
            print("   Install with: pip install PyAudio")
            self.audio_available = False
            self.p = None
    
    def test_microphone(self):
        """Test if microphone is working."""
        if not self.audio_available:
            return False
        
        try:
            stream = self.p.open(
                format=self.pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=1024
            )
            stream.close()
            return True
        except Exception as e:
            print(f"Microphone test error: {e}")
            return False
    
    def play_test_tone(self, frequency=440, duration=1.0):
        """Play a test tone through speakers."""
        if not self.audio_available:
            # Simulate for demo
            print(f"Simulation: Playing {frequency}Hz tone for {duration}s")
            time.sleep(duration)
            return True
        
        try:
            # Generate sine wave
            samples = np.sin(2 * np.pi * np.arange(self.sample_rate * duration) * frequency / self.sample_rate)
            samples = (samples * 32767 * self.volume).astype(np.int16)
            
            # Play audio
            stream = self.p.open(
                format=self.pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                output=True
            )
            
            stream.write(samples.tobytes())
            stream.stop_stream()
            stream.close()
            return True
        except Exception as e:
            print(f"Audio playback error: {e}")
            return False
    
    def toggle_mute(self):
        """Toggle mute state."""
        self.is_muted = not self.is_muted
        return self.is_muted
    
    def set_volume(self, volume):
        """Set volume level (0.0 to 1.0)."""
        self.volume = max(0.0, min(1.0, volume))
    
    def get_audio_status(self):
        """Get audio system status."""
        return {
            "available": self.audio_available,
            "muted": self.is_muted,
            "volume": self.volume,
            "microphone": self.test_microphone() if self.audio_available else False
        }

# Create global instance
audio_manager = AudioManager()