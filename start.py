"""Start the dashboard with one command:  python start.py

Installs the Python packages it needs (first run only), starts the server and
opens the dashboard in your browser at http://localhost:8000. Press Ctrl+C to stop.
"""

import importlib.util
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PORT = 8000

if sys.version_info < (3, 10):
    sys.exit(f"Python 3.10 or newer is needed (you have {sys.version.split()[0]}). Get it from https://www.python.org/downloads/")

needed = ["fastapi", "uvicorn", "pandas", "pyarrow", "sklearn", "anthropic"]
if any(importlib.util.find_spec(m) is None for m in needed):
    print("Installing packages (first run only, takes a minute or two)...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(ROOT / "backend" / "requirements.txt")])

if not (ROOT / "frontend" / "dist" / "index.html").exists():
    sys.exit("frontend/dist is missing. Build it with `npm install && npm run build` in frontend/.")

url = f"http://localhost:{PORT}"
threading.Thread(target=lambda: (time.sleep(3), webbrowser.open(url)), daemon=True).start()
print(f"\nDashboard running at {url}  (press Ctrl+C to stop)\n")
subprocess.call([sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(PORT)], cwd=ROOT / "backend")
