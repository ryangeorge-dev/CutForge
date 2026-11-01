"""Start both local servers; no global packages or shell-specific commands."""
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    python = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    problems = []
    if not python.exists():
        problems.append("Create the environment: python -m venv .venv; then install backend/requirements.txt with its Python.")
    else:
        check = subprocess.run([str(python), "-c", "import fastapi, uvicorn, multipart, lxml"], capture_output=True)
        if check.returncode:
            problems.append(f"Install backend dependencies: {python} -m pip install -r backend/requirements.txt")
    for executable in ("node", "npm", "ffmpeg", "ffprobe"):
        if not shutil.which(executable):
            problems.append(f"{executable} is missing from PATH. See README.md setup instructions.")
    vite = ROOT / "frontend/node_modules/vite/bin/vite.js"
    if not vite.exists():
        problems.append("Install frontend dependencies: npm --prefix frontend ci")
    for port in (8000, 5173):
        try:
            with socket.socket() as sock:
                # Match the servers' Unix socket behavior: a recently closed
                # connection in TIME_WAIT must not look like a live listener.
                if os.name != "nt":
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind(("127.0.0.1", port))
        except PermissionError:
            problems.append(f"Permission denied binding 127.0.0.1:{port}. Allow local server access in your execution environment.")
        except OSError:
            problems.append(f"Port {port} is unavailable. Stop the other server before starting CutForge.")
    if problems:
        print("CutForge cannot start:\n" + "\n".join(f"- {problem}" for problem in problems), file=sys.stderr)
        return 1
    children = []
    kwargs = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
    try:
        children.append(subprocess.Popen([str(python), "-m", "uvicorn", "cutforge.api:create_app", "--factory", "--app-dir", "backend", "--host", "127.0.0.1", "--port", "8000"], cwd=ROOT, **kwargs))
        children.append(subprocess.Popen([shutil.which("node"), str(vite)], cwd=ROOT / "frontend", **kwargs))
        print("\nCutForge: http://127.0.0.1:5173\nPress Ctrl+C once to stop safely. Active media jobs finish before the backend exits.\n", flush=True)
        while all(child.poll() is None for child in children):
            time.sleep(.3)
        print("A server stopped. Shutting down the other server.", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Stopping CutForge. Waiting for active jobs; imported media and decisions remain on disk.", flush=True)
        return 0
    finally:
        for child in children:
            if child.poll() is None:
                if os.name == "nt":
                    child.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    os.killpg(child.pid, signal.SIGTERM)
        for child in children:
            child.wait()


if __name__ == "__main__":
    raise SystemExit(main())
