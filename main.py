import sys
import io
import os

if hasattr(sys, "frozen"):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class DummyStream(io.StringIO):
    def write(self, s): pass
    def flush(self): pass
    def isatty(self): return False

if sys.stdout is None or not hasattr(sys.stdout, "write"):
    sys.stdout = DummyStream()
if sys.stderr is None or not hasattr(sys.stderr, "write"):
    sys.stderr = DummyStream()

sys.__stdout__ = sys.stdout
sys.__stderr__ = sys.stderr

os.environ['PHONEMIZER_ESPEAK_LIBRARY'] = os.path.join(BASE_DIR, "libespeak-ng.dll")
os.environ['ESPEAK_DATA_PATH'] = os.path.join(BASE_DIR, "_internal", "espeakng_loader", "espeak-ng-data")

try:
    from phonemizer.backend.espeak.wrapper import EspeakWrapper
    if not hasattr(EspeakWrapper, 'set_data_path'):
        def dummy_set_data_path(path): pass
        EspeakWrapper.set_data_path = staticmethod(dummy_set_data_path)
except:
    pass

import threading
import time
import queue
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
from PIL import Image, ImageTk
import base64

import ai_full as ai

# --- THEME SETUP ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Windows AI Assistant - Vision & Gaze Control")
        self.geometry("1100x700")

        self.is_running = False
        self.log_queue = queue.Queue()

        # --- LAYOUT ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        self.logo_label = ctk.CTkLabel(self.sidebar, text="AI CORE", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        self.start_btn = ctk.CTkButton(self.sidebar, text="START SYSTEM", fg_color="green", hover_color="#006400",
                                       command=self.toggle_system)
        self.start_btn.grid(row=1, column=0, padx=20, pady=10)

        self.mode_switch = ctk.CTkSwitch(self.sidebar, text="Assistant Mode", command=self.toggle_mode)
        self.mode_switch.select()
        self.mode_switch.grid(row=2, column=0, padx=20, pady=10)

        self.gaze_btn = ctk.CTkButton(self.sidebar, text="Calibrate Eye Tracking", command=self.run_calibration)
        self.gaze_btn.grid(row=3, column=0, padx=20, pady=10)

        self.status_label = ctk.CTkLabel(self.sidebar, text="Status: Offline", text_color="gray")
        self.status_label.grid(row=5, column=0, padx=20, pady=(100, 10))

        # Main Chat Area
        self.chat_frame = ctk.CTkFrame(self, corner_radius=10)
        self.chat_frame.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        self.chat_frame.grid_columnconfigure(0, weight=1)
        self.chat_frame.grid_rowconfigure(0, weight=1)

        self.log_box = ctk.CTkTextbox(self.chat_frame, font=("Consolas", 13))
        self.log_box.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        # Vision Preview
        self.preview_label = ctk.CTkLabel(self.sidebar, text="Vision Preview")
        self.preview_label.grid(row=6, column=0, pady=(20, 0))
        self.img_label = ctk.CTkLabel(self.sidebar, text="", width=180, height=120, fg_color="black")
        self.img_label.grid(row=7, column=0, padx=10, pady=10)

        ai.speak_text = self.gui_speak_text
        self.check_queue()

    # Logging

    def update_status(self, text, color="white"):
        self.status_label.configure(text=f"Status: {text}", text_color=color)

    def write_log(self, message):
        self.log_queue.put(message)

    def check_queue(self):
        while not self.log_queue.empty():
            msg = self.log_queue.get()
            self.log_box.insert("end", f"{msg}\n")
            self.log_box.see("end")
        self.after(100, self.check_queue)

    # AI

    def gui_speak_text(self, text):
        clean = ai.clean_response(text)
        if clean:
            self.write_log(f"🤖 AI: {clean}")
            threading.Thread(target=ai.voice.speak, args=(clean,), daemon=True).start()

    def toggle_mode(self):
        if self.mode_switch.get() == 1:
            ai.current_mode = "assistant"
            self.write_log("System: Switched to ASSISTANT mode")
        else:
            ai.current_mode = "transcribe"
            self.write_log("System: Switched to TRANSCRIBE mode")

    # Eye Tracking

    def run_calibration(self):
        if not self.is_running:
            messagebox.showwarning("System Offline", "Start the system first.")
            return
        try:
            from eyetrax import GazeEstimator
        except ImportError:
            self.write_log("Error: eyetrax module not found.")
            return
        self.write_log("System: Starting Eye Tracking Calibration...")
        self.gaze_btn.configure(state="disabled")
        # Minimize GUI so the OpenCV calibration window is not blocked
        self.iconify()
        # Small delay to let minimize animation finish before cv2 opens a window
        self.after(300, self._do_calibration)

    def _do_calibration(self):
        """Must run on the main thread — OpenCV imshow requires it."""
        try:
            from eyetrax import GazeEstimator, run_lissajous_calibration, run_9_point_calibration
            est1 = GazeEstimator()
            run_lissajous_calibration(est1)
            est2 = GazeEstimator()
            run_9_point_calibration(est2)
            self.write_log("System: Calibration complete. Starting gaze tracking...")
            # Gaze tracking loop is pure math — safe on a background thread
            threading.Thread(target=self._run_gaze_loop, args=(est1, est2), daemon=True).start()
        except Exception as e:
            self.write_log(f"Calibration Error: {e}")
        finally:
            self.deiconify()
            self.gaze_btn.configure(state="normal")

    def _run_gaze_loop(self, est1, est2):
        """Background thread — no cv2 windows, just math and mouse control."""
        import cv2
        import pyautogui as pg
        cap = cv2.VideoCapture(0)
        sw, sh = pg.size()
        last_click = 0
        blink = dbl = last_blink = 0
        while not ai.stop_event.is_set():
            ret, frame = cap.read()
            if not ret:
                continue
            f1, b1 = est1.extract_features(frame)
            f2, b2 = est2.extract_features(frame)
            now = time.time()
            if b1 and b2:
                blink += 1
                if now - last_blink < 0.5:
                    dbl += 1
                last_blink = now
            else:
                blink = 0
                if now - last_blink > 0.6:
                    dbl = 0
            if dbl >= 8 and now - last_click > 0.8:
                pg.rightClick()
                last_click = now
                dbl = blink = 0
            elif blink >= 3 and now - last_click > 0.8:
                pg.click()
                last_click = now
                blink = 0
            if f1 is not None and f2 is not None and not (b1 and b2):
                x1, y1 = est1.predict([f1])[0]
                x2, y2 = est2.predict([f2])[0]
                pg.moveTo(
                    max(0, min(sw - 1, int(x1 * 0.6 + x2 * 0.4))),
                    max(0, min(sh - 1, int(y1 * 0.6 + y2 * 0.4)))
                )
            time.sleep(0.005)
        cap.release()

    # System Start / Stop

    def toggle_system(self):
        if not self.is_running:
            ai.stop_event.clear()
            self.start_btn.configure(text="STOP SYSTEM", fg_color="red")
            self.is_running = True
            self.update_status("Loading Server...", "yellow")
            threading.Thread(target=self.core_logic_thread, daemon=True).start()
        else:
            ai.stop_event.set()
            self.is_running = False
            self.start_btn.configure(text="START SYSTEM", fg_color="green")
            self.update_status("Offline", "gray")

    def core_logic_thread(self):
        try:
            self.write_log("System: Starting Llama Server...")
            ai.server.start()
            self.update_status("Online", "green")
            self.write_log("System: Initializing Voice Engine...")
            self.audio_listener()
        except Exception as e:
            self.write_log(f"Error: {e}")
            self.is_running = False
            ai.stop_event.set()
            self.after(0, lambda: self.start_btn.configure(text="START SYSTEM", fg_color="green"))
            self.after(0, lambda: self.update_status("Error - see log", "red"))

    # Audio Loop

    def audio_listener(self):
        import pyaudio
        import numpy as np

        p = pyaudio.PyAudio()
        stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000,
                        input=True, frames_per_buffer=512)

        audio_buffer = []
        speaking = False
        silent = 0

        self.write_log("System: Listening for speech...")

        while not ai.stop_event.is_set():
            try:
                data = stream.read(512, exception_on_overflow=False)
                chunk = np.frombuffer(data, dtype=np.int16)
                prob = ai.voice.get_speech_prob(chunk.astype(np.float32) / 32768.0)

                if not speaking:
                    if prob > 0.55:
                        speaking = True
                        audio_buffer = [chunk]
                        silent = 0
                else:
                    audio_buffer.append(chunk)
                    if prob < 0.55:
                        silent += 1
                        if silent > 35 and len(audio_buffer) > 12:
                            text = ai.voice.transcribe(audio_buffer)
                            if text.strip():
                                self.write_log(f"🎤 User: {text}")
                                if any(kw in text.lower() for kw in ["see", "look", "screen"]):
                                    self.after(0, self.update_preview)
                                ai.run_ai_loop(text)
                            audio_buffer = []
                            speaking = False
                            silent = 0
                    else:
                        silent = 0
            except Exception:
                continue

        stream.stop_stream()
        stream.close()
        p.terminate()
        ai.server.stop()

    # Vision Preview

    def update_preview(self):
        """Must be called on the main thread via self.after(0, self.update_preview)."""
        try:
            img_b64 = ai.capture_screen_b64()
            img_data = base64.b64decode(img_b64)
            img = Image.open(io.BytesIO(img_data))
            img.thumbnail((180, 120))
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(180, 120))
            self.img_label.configure(image=ctk_img, text="")
        except Exception:
            pass


if __name__ == "__main__":
    app = App()
    app.mainloop()
