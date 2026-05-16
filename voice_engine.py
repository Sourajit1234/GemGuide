import io
import numpy as np
import sounddevice as sd
import onnx_asr
import webrtcvad
import os
import sys
import threading

# ── THE BULLETPROOF FIX FOR KOKORO-ONNX ──
# We patch the EspeakWrapper BEFORE importing kokoro_onnx
try:
    from phonemizer.backend.espeak.wrapper import EspeakWrapper
    if not hasattr(EspeakWrapper, 'set_data_path'):
        def set_data_path(path): pass
        EspeakWrapper.set_data_path = staticmethod(set_data_path)
        print("✅ Patched EspeakWrapper for EXE compatibility")
except Exception as e:
    print(f"⚠️ Patch failed: {e}")

# NOW we can safely import Kokoro
from kokoro_onnx import Kokoro


class DummyStream(io.StringIO):
    def write(self, s): pass
    def flush(self): pass
    def isatty(self): return False

if sys.stdout is None or not hasattr(sys.stdout, "write"):
    sys.stdout = DummyStream()
if sys.stderr is None or not hasattr(sys.stderr, "write"):
    sys.stderr = DummyStream()

# Loguru and other libraries often check these original "dunder" streams
sys.__stdout__ = sys.stdout
sys.__stderr__ = sys.stderr

def get_base_path():
    if hasattr(sys, "frozen"):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

class VoiceEngine:
    def __init__(self):
        print(f"🎙️ TTS: CPU (ONNX) | STT: CPU (ONNX INT8) | VAD: WebRTC")

        base_dir = get_base_path()
        model_path = os.path.join(base_dir, "model", "kokoro.onnx")
        voices_path = os.path.join(base_dir, "model", "voices-v1.0.bin")

        # Initialize Kokoro ONNX
        self.kokoro = Kokoro(model_path, voices_path)

        # ── STT: onnx_asr INT8 ───────────────────────────────────────────
        self.stt_model = onnx_asr.load_model(
            "nemo-parakeet-tdt-0.6b-v3",
            quantization="int8",
            providers=["CPUExecutionProvider"],
        )

        # ── VAD: WebRTC (replaces Silero/torch — no internet, no GPU needed) ──
        self.vad = webrtcvad.Vad(2)  # aggressiveness 0-3, 2 is balanced
        self.vad_sample_size = 512
        self.sample_rate = 16000

    # ── TTS ──────────────────────────────────────────────────────────────────

    def speak(self, text):
        if not text.strip(): return

        def _run():
            # Generate audio using ONNX (faster and no espeak needed)
            samples, sample_rate = self.kokoro.create(text, voice="af_bella", speed=1.1)
            sd.play(samples, sample_rate)
            sd.wait()

        threading.Thread(target=_run, daemon=True).start()

    # ── VAD & STT ────────────────────────────────────────────────────────────

    def get_speech_prob(self, audio_float: np.ndarray) -> float:
        # webrtcvad needs 16-bit PCM, exactly 20ms = 320 samples at 16000Hz
        audio_int16 = (audio_float * 32768).astype(np.int16)
        frame_size = 320  # 20ms at 16000Hz
        if len(audio_int16) >= frame_size:
            frame = audio_int16[:frame_size]
        else:
            frame = np.zeros(frame_size, dtype=np.int16)
            frame[-len(audio_int16):] = audio_int16
        try:
            is_speech = self.vad.is_speech(frame.tobytes(), self.sample_rate)
            return 1.0 if is_speech else 0.0
        except Exception:
            return 0.0

    def transcribe(self, audio_buffer: list) -> str:
        full = np.concatenate(audio_buffer).astype(np.float32) / 32768.0
        try:
            return str(self.stt_model.recognize(full)).strip()
        except Exception as e:
            print(f"STT Error: {e}")
            return ""