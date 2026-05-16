import subprocess
import webbrowser
import threading
import time
import datetime
import pyautogui
import json
import shutil
import psutil
import os
from rapidfuzz import process, fuzz

# ── Basic Tools ───────────────────────────────────────────────────────────────




def open_path(path):
    """
    Search for the best fuzzy match of a filename in the User directory
    and open it using the default Windows handler.
    """
    try:
        # 1. Define the search area (e.g., the User's home directory)
        # Searching the entire C:\ drive is possible but very slow for real-time use.
        search_root = os.path.expanduser("~")

        file_map = {}
        # 2. Gather all files (filenames as keys, full paths as values)
        # Note: This list can be cached or indexed for better performance.
        for root, dirs, files in os.walk(search_root):
            for name in files:
                # Store the filename for matching, mapping it to its full path
                file_map[name] = os.path.join(root, name)

            # Optional: Limit depth or skip hidden folders for speed
            if len(file_map) > 10000:  # Safety break for performance
                break

        # 3. Use RapidFuzz to find the best match among filenames
        # scorer=fuzz.WRatio is good for handling typos and partial names
        match = process.extractOne(path, file_map.keys(), scorer=fuzz.WRatio)

        if match:
            best_filename, score, _ = match
            # Only open if the match is confident enough (e.g., > 60% similarity)
            if score > 60:
                full_match_path = file_map[best_filename]
                os.startfile(full_match_path)
                return f"Opened '{best_filename}' (Confidence: {score:.1f}%) at {full_match_path}"
            else:
                return f"No confident match found for '{path}'. Best guess was '{best_filename}' ({score:.1f}%)."

        return "No files found to match."

    except Exception as e:
        return f"Failed to open path: {str(e)}"


# Example Usage:
# print(open_path("resum"))  # Might find "My_Resume_2024.pdf"

def open_browser(url_or_search, search=False):
    url = f"https://www.google.com/search?q={url_or_search}" if search else \
          (url_or_search if url_or_search.startswith("http") else f"https://{url_or_search}")
    webbrowser.open(url)
    return f"Opened {url}"

def set_timer(seconds, label="Timer", callback_fn=None):
    def timer_done():
        time.sleep(seconds)
        if callback_fn: callback_fn(f"Timer {label} is finished!")
    threading.Thread(target=timer_done, daemon=True).start()
    return f"Timer set for {seconds} seconds."

def set_alarm(time_str, label="Alarm", callback_fn=None):
    def alarm_loop():
        while True:
            if datetime.datetime.now().strftime("%H:%M") == time_str:
                if callback_fn: callback_fn(f"Alarm {label} is going off!")
                break
            time.sleep(30)
    threading.Thread(target=alarm_loop, daemon=True).start()
    return f"Alarm set for {time_str}."

def calculate(expression):
    try:
        if all(c in "0123456789+-*/(). %**" for c in expression):
            return f"Result: {eval(expression)}"
        return "Invalid characters."
    except: return "Math error."

def type_text(text):
    time.sleep(2)
    pyautogui.write(text, interval=0.01)
    return "Finished typing."

def open_any_app(app_name):
    cmd = f'powershell -Command "Get-StartApps | Where-Object {{ $_.Name -like \'*{app_name}*\' }} | Select-Object -First 1 | ForEach-Object {{ Start-Process shell:AppsFolder\\$($_.AppID) }}"'
    subprocess.run(cmd, shell=True)
    return f"Launched {app_name}"

def set_volume(level):
    level = max(0, min(100, level))
    cmd = f'powershell -Command "$w = New-Object -ComObject WScript.Shell; for($i=0; $i -lt 50; $i++) {{ $w.SendKeys([char]174) }}; for($i=0; $i -lt ({level}/2); $i++) {{ $w.SendKeys([char]175) }}"'
    subprocess.run(cmd, shell=True)
    return f"Volume set to {level}%"


# ── New Tools ─────────────────────────────────────────────────────────────────

def get_clipboard():
    """Read current clipboard text."""
    try:
        import pyperclip
        return pyperclip.paste() or "(empty)"
    except: return "pyperclip not installed."

def set_clipboard(text):
    """Write text to clipboard."""
    try:
        import pyperclip
        pyperclip.copy(text)
        return f"Copied to clipboard: {text[:60]}"
    except: return "pyperclip not installed."

def press_key(key_combo):
    """
    Press a key or key combo. Examples: 'ctrl+c', 'win+d', 'alt+f4', 'enter', 'esc'.
    """
    keys = [k.strip() for k in key_combo.lower().split("+")]
    if len(keys) == 1:
        pyautogui.press(keys[0])
    else:
        pyautogui.hotkey(*keys)
    return f"Pressed: {key_combo}"

def scroll(direction, amount=3):
    """Scroll up or down at current mouse position."""
    clicks = amount if direction == "up" else -amount
    pyautogui.scroll(clicks)
    return f"Scrolled {direction} by {amount}"

def take_screenshot(save_path=None):
    """Take screenshot, save to Desktop if no path given. Returns path."""
    if not save_path:
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        save_path = os.path.join(desktop, f"screenshot_{int(time.time())}.png")
    img = pyautogui.screenshot()
    img.save(save_path)
    return save_path

def get_system_info():
    """Return CPU, RAM, disk usage as a short string."""
    cpu = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage('C:\\')
    return (f"CPU: {cpu}% | RAM: {ram.percent}% used ({ram.available // 1024**3}GB free) | "
            f"Disk C: {disk.percent}% used ({disk.free // 1024**3}GB free)")

def list_processes(filter_name=None):
    """List running processes, optionally filtered by name."""
    procs = []
    for p in psutil.process_iter(['pid', 'name', 'cpu_percent']):
        try:
            if filter_name is None or filter_name.lower() in p.info['name'].lower():
                procs.append(f"{p.info['name']} (PID {p.info['pid']})")
        except: pass
    return ", ".join(procs[:20]) if procs else "No matching processes."

def kill_process(name_or_pid):
    """Kill a process by name or PID."""
    killed = []
    for p in psutil.process_iter(['pid', 'name']):
        try:
            match = (str(p.info['pid']) == str(name_or_pid) or
                     name_or_pid.lower() in p.info['name'].lower())
            if match:
                p.kill()
                killed.append(p.info['name'])
        except: pass
    return f"Killed: {', '.join(killed)}" if killed else "No matching process found."

def run_command(command):
    """Run a shell command and return stdout (max 500 chars)."""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=10)
        out = (result.stdout + result.stderr).strip()
        return out[:500] if out else "(no output)"
    except subprocess.TimeoutExpired:
        return "Command timed out."
    except Exception as e:
        return f"Error: {e}"

def get_time_date():
    """Return current date and time."""
    now = datetime.datetime.now()
    return now.strftime("It is %A, %B %d %Y, %I:%M %p")

def search_files(query, search_dir=None):
    """Search for files matching query in a directory (default: Desktop + Documents)."""
    if not search_dir:
        home = os.path.expanduser("~")
        dirs = [os.path.join(home, "Desktop"), os.path.join(home, "Documents")]
    else:
        dirs = [search_dir]

    matches = []
    for d in dirs:
        if not os.path.exists(d): continue
        for root, _, files in os.walk(d):
            for f in files:
                if query.lower() in f.lower():
                    matches.append(os.path.join(root, f))
                if len(matches) >= 10:
                    break

    return ", ".join(matches) if matches else "No files found."

def move_mouse_to(x, y):
    """Move mouse to absolute screen coordinates."""
    pyautogui.moveTo(x, y, duration=0.15)
    return f"Mouse moved to ({x}, {y})"

def click_at(x, y, button="left"):
    """Click at absolute screen coordinates."""
    pyautogui.click(x, y, button=button)
    return f"{button.capitalize()} clicked at ({x}, {y})"

def write_file(path, content):
    """Write text content to a file."""
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    return f"Written to {path}"

def read_file(path):
    """Read text file contents (first 1000 chars)."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read(1000)
    except Exception as e:
        return f"Error: {e}"


# ── Tool Schemas ──────────────────────────────────────────────────────────────
def _fn(name, desc, props, required):
    return {"type": "function", "function": {
        "name": name, "description": desc,
        "parameters": {"type": "object", "properties": props, "required": required}
    }}

TOOL_SCHEMAS = [
    _fn("open_any_app", "Launch any installed Windows application.",
        {"app_name": {"type": "string", "description": "App name to search and launch"}}, ["app_name"]),

    _fn("open_path", "Open a specific file, folder, or drive path on the computer.",
        {"path": {"type": "string",
                  "description": "Full path to the file or folder (e.g., 'C:\\Users', 'D:\\Projects')"}}, ["path"]),

    _fn("set_volume", "Set system volume 0–100.",
        {"level": {"type": "integer"}}, ["level"]),

    _fn("open_browser", "Open a URL or perform a Google search.",
        {"url_or_search": {"type": "string"}, "search": {"type": "boolean", "description": "True to search, False for direct URL"}},
        ["url_or_search", "search"]),

    _fn("set_timer", "Set a countdown timer.",
        {"seconds": {"type": "integer"}, "label": {"type": "string"}}, ["seconds"]),

    _fn("set_alarm", "Set an alarm at a specific time (HH:MM 24h).",
        {"time_str": {"type": "string"}, "label": {"type": "string"}}, ["time_str"]),

    _fn("calculate", "Evaluate a math expression.",
        {"expression": {"type": "string"}}, ["expression"]),

    _fn("type_text", "Type text at the current cursor position.",
        {"text": {"type": "string"}}, ["text"]),

    _fn("press_key", "Press a key or hotkey combo like 'ctrl+c', 'win+d', 'alt+f4'.",
        {"key_combo": {"type": "string"}}, ["key_combo"]),

    _fn("scroll", "Scroll the page up or down.",
        {"direction": {"type": "string", "enum": ["up", "down"]},
         "amount": {"type": "integer", "description": "Number of scroll clicks (default 3)"}},
        ["direction"]),

    _fn("take_screenshot", "Take a screenshot. Optionally specify save path.",
        {"save_path": {"type": "string", "description": "Optional file path to save the screenshot"}}, []),

    _fn("get_system_info", "Get CPU, RAM, and disk usage.", {}, []),

    _fn("list_processes", "List running processes, optionally filtered by name.",
        {"filter_name": {"type": "string", "description": "Optional name filter"}}, []),

    _fn("kill_process", "Kill a process by name or PID.",
        {"name_or_pid": {"type": "string"}}, ["name_or_pid"]),

    _fn("run_command", "Run a shell/PowerShell command and return output.",
        {"command": {"type": "string"}}, ["command"]),

    _fn("get_time_date", "Get the current date and time.", {}, []),

    _fn("get_clipboard", "Read current clipboard text.", {}, []),

    _fn("set_clipboard", "Copy text to clipboard.",
        {"text": {"type": "string"}}, ["text"]),

    _fn("search_files", "Search for files on Desktop/Documents.",
        {"query": {"type": "string"}, "search_dir": {"type": "string", "description": "Optional directory to search"}},
        ["query"]),

    _fn("move_mouse_to", "Move mouse to absolute screen coordinates.",
        {"x": {"type": "integer"}, "y": {"type": "integer"}}, ["x", "y"]),

    _fn("click_at", "Click at absolute screen coordinates.",
        {"x": {"type": "integer"}, "y": {"type": "integer"},
         "button": {"type": "string", "enum": ["left", "right", "middle"]}},
        ["x", "y"]),

    _fn("write_file", "Write content to a text file.",
        {"path": {"type": "string"}, "content": {"type": "string"}}, ["path", "content"]),

    _fn("read_file", "Read content from a text file.",
        {"path": {"type": "string"}}, ["path"]),
_fn("capture_screen", "Take a real-time screenshot of the current screen so you can 'see' what the user is talking about.", {}, []),
]