import json
import base64
import pyaudio
import numpy as np
import cv2
import pyautogui as pg
import threading
import time
import re
from openai import OpenAI
import concurrent.futures

from server import LlamaServer
from voice_engine import VoiceEngine
import tools as t

import os
import sys

def get_base_path():
    # If running as a Nuitka onefile, this finds the temp extraction folder
    if hasattr(sys, "frozen"):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = get_base_path()

# Update your config to use relative paths
MODEL_PATH = os.path.join(BASE_DIR, "model", "google_gemma-4-E4B-it-Q4_K_M.gguf")
MM_PATH = os.path.join(BASE_DIR, "model", "mmproj-google_gemma-4-E4B-it-f16.gguf")
CHAT_PATH = os.path.join(BASE_DIR, "model", "chat_template.jinja")


try:
    from eyetrax import GazeEstimator, run_lissajous_calibration, run_9_point_calibration
except ImportError:
    GazeEstimator = None

pg.FAILSAFE = False

stop_event = threading.Event()
server = LlamaServer(MODEL_PATH, MM_PATH, CHAT_PATH)
voice = VoiceEngine()
client = OpenAI(base_url="http://127.0.0.1:8080/v1", api_key="ollama")
executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

# System message to enforce tool usage rules
messages = [{"role": "system", "content": (
    "You are a Windows AI assistant. When you use a tool, respond with a final answer after getting the result. "
    "Never call the same tool twice in a row. After a tool succeeds, say what you did and stop."
    "You have many tools to perform different actions. You are provided with capture_screen tool. "
    "Use it whenever you need to see the user's screen or current active window to answer a question."
)}]

current_mode = "assistant"
_transcribe_raw = []
_transcribe_timer = None


# ── HELPERS ───────────────────────────────────────────────────────────────────

def capture_screen_b64() -> str:
    img = pg.screenshot()
    arr = np.array(img)
    bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    h, w = bgr.shape[:2]
    bgr = cv2.resize(bgr, (w // 2, h // 2))
    _, buf = cv2.imencode('.jpg', bgr, [cv2.IMWRITE_JPEG_QUALITY, 75])
    return base64.b64encode(buf).decode('utf-8')


def execute_tool(fn_name: str, args: dict) -> str:
    tool_map = {
        "open_path": lambda: t.open_path(args.get('path', '')),
        "open_any_app": lambda: t.open_any_app(args.get('app_name', '')),
        "set_volume": lambda: t.set_volume(args.get('level', 50)),
        "open_browser": lambda: t.open_browser(args.get('url_or_search', ''), args.get('search', False)),
        "calculate": lambda: t.calculate(args.get('expression', '')),
        "type_text": lambda: t.type_text(args.get('text', '')),
        "press_key": lambda: t.press_key(args.get('key_combo', '')),
        "scroll": lambda: t.scroll(args.get('direction', 'down'), args.get('amount', 3)),
        "take_screenshot": lambda: t.take_screenshot(args.get('save_path')),
        "get_system_info": lambda: t.get_system_info(),
        "list_processes": lambda: t.list_processes(args.get('filter_name')),
        "kill_process": lambda: t.kill_process(args.get('name_or_pid', '')),
        "get_time_date": lambda: t.get_time_date(),
        "get_clipboard": lambda: t.get_clipboard(),
        "set_clipboard": lambda: t.set_clipboard(args.get('text', '')),
        "search_files": lambda: t.search_files(args.get('query', ''), args.get('search_dir')),
        "move_mouse_to": lambda: t.move_mouse_to(args.get('x', 0), args.get('y', 0)),
        "click_at": lambda: t.click_at(args.get('x', 0), args.get('y', 0), args.get('button', 'left')),
        "write_file": lambda: t.write_file(args.get('path', ''), args.get('content', '')),
        "read_file": lambda: t.read_file(args.get('path', '')),
        "set_timer": lambda: t.set_timer(args.get('seconds', 0), args.get('label', 'Timer'), voice.speak),
        "run_command": lambda: t.run_command(args.get('command', '')),
    }
    handler = tool_map.get(fn_name)
    if handler:
        try:
            result = handler()
            return str(result) if result else "Success"
        except Exception as e:
            return f"Error: {str(e)}"
    return f"Unknown tool: {fn_name}"


def clean_response(text: str) -> str:
    if not text: return ""
    text = re.sub(r'call:\w+\{[^}]+\}', '', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text if len(text) > 2 else ""


def speak_text(text: str):
    """The GUI can override this function to capture output"""
    clean = clean_response(text)
    if clean:
        print(f"🤖 {clean}")
        threading.Thread(target=voice.speak, args=(clean,), daemon=True).start()


def run_ai_loop(user_text: str) -> bool:
    global current_mode, messages
    user_lower = user_text.lower()

    # 1. Standard Mode/Exit logic
    if any(cmd in user_lower for cmd in ["end assistant", "goodbye"]):
        speak_text("Goodbye!")
        stop_event.set()
        return False

    if "transcribe mode" in user_lower:
        current_mode = "transcribe";
        speak_text("Transcribe mode on.");
        return True
    if "assistant mode" in user_lower:
        current_mode = "assistant";
        speak_text("Assistant mode on.");
        return True
    if current_mode == "transcribe":
        add_transcription_chunk(user_text);
        return True

    # 2. Initial User Message (No regex vision here!)
    messages.append({"role": "user", "content": user_text})

    # 3. Recursive Chaining Loop
    for turn in range(6):
        try:
            response = client.chat.completions.create(
                model="Gemma4",
                messages=messages,
                tools=t.TOOL_SCHEMAS,
                temperature=0.1
            )
            msg = response.choices[0].message

            # --- Handle Thinking ---
            raw_content = msg.content or ""
            thought_match = re.search(r'<\|channel\|>thought(.*?)(?:<channel\|>|$)', raw_content, re.DOTALL)
            if thought_match:
                print(f"💭 Thought: {thought_match.group(1).strip()}")
                raw_content = re.sub(r'<\|channel\|>thought.*?<channel\|>', '', raw_content, flags=re.DOTALL).strip()

            # --- Handle Tool Calls ---
            if msg.tool_calls:
                messages.append(msg)  # Maintain history integrity

                for tool_call in msg.tool_calls:
                    fn_name = tool_call.function.name
                    fn_args = json.loads(tool_call.function.arguments) if isinstance(tool_call.function.arguments,
                                                                                     str) else tool_call.function.arguments

                    # SPECIAL CASE: Vision Tool
                    if fn_name == "capture_screen":
                        print("📸 Tool Triggered: Capturing Screen...")
                        b64_img = capture_screen_b64()

                        # We provide a text success to the tool role...
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": fn_name,
                            "content": "Screenshot captured. I can now see the screen in my context."
                        })

                        # ...AND we inject the actual image as a new system/user-assist context
                        # Most VLM servers prefer the image in the next message
                        messages.append({
                            "role": "user",
                            "content": [
                                {"type": "text",
                                 "text": "I have updated my visual perception with the screenshot below:"},
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}}
                            ]
                        })
                        print("👁️ Visual context updated.")

                    else:
                        # Normal Tool Execution
                        print(f"🛠️ Executing: {fn_name}")
                        result = execute_tool(fn_name, fn_args)
                        messages.append(
                            {"role": "tool", "tool_call_id": tool_call.id, "name": fn_name, "content": result})

                continue  # Re-query AI with the new tool results/images

            else:
                # --- Final Answer ---
                final_answer = clean_response(raw_content)
                if final_answer:
                    speak_text(final_answer)
                    messages.append({"role": "assistant", "content": final_answer})
                break

        except Exception as e:
            print(f"Loop Error: {e}")
            break

    if len(messages) > 25: messages = [messages[0]] + messages[-20:]
    return True
# ── TRANSCRIPTION ─────────────────────────────────────────────────────────────

def flush_transcription():
    global _transcribe_raw, _transcribe_timer
    if not _transcribe_raw: return

    raw = " ".join(_transcribe_raw)
    _transcribe_raw = []
    _transcribe_timer = None

    try:
        response = client.chat.completions.create(
            model="Gemma4",
            messages=[{"role": "user",
                       "content": f"Clean this transcription for clarity, fix grammar, an"
                                  f"d return ONLY one option for the resulting text. In case of code, "
                                  f"fix the syntax and make it appropriate for the language. In case of "
                                  f"Mathematics, convert it to perfect LaTeX. No other words needed:\n\n{raw}"}]
        )
        cleaned = response.choices[0].message.content.strip()

        cleaned = cleaned.strip('"').strip("'")

        if cleaned:
            print(f"⌨️ Typing: {cleaned}")
            # We call type_text from our tools
            t.type_text(cleaned)
    except Exception as e:
        print(f"Transcription Error: {e}")


def add_transcription_chunk(raw: str):
    global _transcribe_timer
    _transcribe_raw.append(raw)
    if _transcribe_timer: _transcribe_timer.cancel()
    _transcribe_timer = threading.Timer(2.5, flush_transcription)
    _transcribe_timer.start()


# ── GAZE ──────────────────────────────────────────────────────────────────────

def gaze_control_loop():
    if not GazeEstimator:
        print("[Gaze] eyetrax module not found.")
        return
    try:
        est1 = GazeEstimator();
        run_lissajous_calibration(est1)
        est2 = GazeEstimator();
        run_9_point_calibration(est2)
        cap = cv2.VideoCapture(0)
        sw, sh = pg.size()
        last_click = 0
        blink = dbl = last_blink = 0
        while not stop_event.is_set():
            ret, frame = cap.read()
            if not ret: continue
            f1, b1 = est1.extract_features(frame)
            f2, b2 = est2.extract_features(frame)
            now = time.time()
            if b1 and b2:
                blink += 1
                if now - last_blink < 0.5: dbl += 1
                last_blink = now
            else:
                blink = 0
                if now - last_blink > 0.6: dbl = 0
            if dbl >= 8 and now - last_click > 0.8:
                pg.rightClick();
                last_click = now;
                dbl = blink = 0
            elif blink >= 3 and now - last_click > 0.8:
                pg.click();
                last_click = now;
                blink = 0
            if f1 is not None and f2 is not None and not (b1 and b2):
                x1, y1 = est1.predict([f1])[0]
                x2, y2 = est2.predict([f2])[0]
                pg.moveTo(max(0, min(sw - 1, int(x1 * 0.6 + x2 * 0.4))),
                          max(0, min(sh - 1, int(y1 * 0.6 + y2 * 0.4))))
            time.sleep(0.005)
        cap.release()
    except Exception as e:
        print(f"[Gaze] Error: {e}")


# ── MAIN ──────────────────────────────────────────────────────────────────────

def process_speech(audio_buffer):
    text = voice.transcribe(audio_buffer)
    if text and text.strip():
        print(f"\n🎤 User: {text}")
        run_ai_loop(text)


def main():
    server.start()
    threading.Thread(target=gaze_control_loop, daemon=True).start()
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000,
                    input=True, frames_per_buffer=512)
    audio_buffer, speaking, silent = [], False, 0
    print("🤖 System Ready.")
    try:
        while not stop_event.is_set():
            data = stream.read(512, exception_on_overflow=False)
            chunk = np.frombuffer(data, dtype=np.int16)
            prob = voice.get_speech_prob(chunk.astype(np.float32) / 32768.0)
            if not speaking:
                if prob > 0.55:
                    speaking = True;
                    audio_buffer = [chunk];
                    silent = 0
            else:
                audio_buffer.append(chunk)
                if prob < 0.55:
                    silent += 1
                    if silent > 35 and len(audio_buffer) > 12:
                        executor.submit(process_speech, audio_buffer.copy())
                        audio_buffer, speaking, silent = [], False, 0
                else:
                    silent = 0
    except KeyboardInterrupt:
        pass
    finally:
        stream.stop_stream();
        stream.close();
        p.terminate();
        server.stop()


if __name__ == "__main__":
    main()