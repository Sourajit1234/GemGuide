import subprocess
import os
import requests
import time
import sys

def get_base_path():
    # If running as a Nuitka onefile, this finds the temp extraction folder
    if hasattr(sys, "frozen"):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = get_base_path()

class LlamaServer:
    def __init__(self, model_path, mmproj_path, chatpath, port=8080):
        self.model_path = model_path
        self.mmproj_path = mmproj_path
        self.chatpath = chatpath
        self.port = str(port)
        self.url = f"http://127.0.0.1:{self.port}"
        self.process = None

    def start(self):
        bin_dir = os.path.join(BASE_DIR, "llamacpp", "bin")
        executable = os.path.join(bin_dir, "llama-server.exe")

        if not os.path.exists(executable):
            raise FileNotFoundError(f"Could not find llama-server.exe at {executable}")

        command = [
            executable,
            "-m", self.model_path,
            "--mmproj", self.mmproj_path,
             "--chat-template-file", self.chatpath,  # NEW: enables interleaved thinking
            "--port", self.port,
            "--host", "127.0.0.1",
            "--parallel", "1",
            "--kv-unified",
            "--flash-attn", "on",
            "--cache-type-k", "q8_0",  # Added: 4-bit Key cache
            "--cache-type-v", "q8_0",
            "--no-warmup",
            "--context-shift",
            "-ngl", "99",
            "--temp", "0.0",          # CHANGED: 0.0 for precision
            "--top-p", "1.0",         # CHANGED: Disable top-p for greedy
            "--top-k", "0",           # CHANGED: Disable top-k for greedy
            "--repeat-penalty", "1.0", # Added: prevent box repetition
            "--image-min-tokens", "512",
            "--image-max-tokens", "2240",
            "--batch-size", "2048",   # Slightly lower for stability
            "--ubatch-size", "2048",
            "--log-disable",
            "--reasoning", "auto"
        ]

        print(f"🚀 Starting Server...")

        # We REMOVED --log-disable and added stdout/stderr capture to see why it fails
        self.process = subprocess.Popen(
            command,
            cwd=bin_dir,
            stdout=subprocess.DEVNULL,  # ← don't pass sys.stdout
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
        )

        # Wait until the health check passes
        for i in range(60):
            if self.process.poll() is not None:
                raise RuntimeError(f"Server process exited unexpectedly with code {self.process.returncode}")

            try:
                response = requests.get(f"{self.url}/health", timeout=1)
                if response.status_code == 200:
                    print("\n✅ Server is ready!")
                    return
            except requests.exceptions.ConnectionError:
                if i % 5 == 0:
                    print(f"⌛ Waiting for model to load... ({i}s)")

            time.sleep(1)

        raise RuntimeError("Server failed to start in 60 seconds.")

    def stop(self):
        if self.process:
            print("🛑 Shutting down server...")
            self.process.terminate()
            self.process.wait()