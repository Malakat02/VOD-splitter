"""Windows double-click launcher, with reusable server and portable Ollama."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parent
FLAGS = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def browser_main():
    os.chdir(ROOT)
    python = ROOT / ".venv" / "Scripts" / "python.exe"
    if not python.exists():
        subprocess.run([sys.executable, "-m", "venv", "--system-site-packages", str(ROOT / ".venv")], check=True)
        subprocess.run([str(python), "-m", "pip", "install", "Pillow>=11,<13"], check=True)
    session = ROOT / ".session.json"
    if session.exists():
        try:
            url = json.loads(session.read_text(encoding="utf-8"))["url"]
            base, token = url.split("#token=")
            req = urllib.request.Request(base + "api/state", headers={"X-Vod-Token": token})
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(req, timeout=2) as r:
                assert r.status == 200
            webbrowser.open(url)
            return
        except Exception:
            pass
    exe = ROOT / "tools" / "ollama" / "ollama.exe"
    if exe.exists():
        env = os.environ.copy()
        env.update(OLLAMA_HOST="127.0.0.1:11434", OLLAMA_MODELS=str(ROOT / "models" / "ollama"), OLLAMA_NO_CLOUD="1")
        with (ROOT / "ollama.log").open("a", encoding="utf-8") as log:
            subprocess.Popen([str(exe), "serve"], stdout=log, stderr=log, env=env, creationflags=FLAGS)
    old = session.read_bytes() if session.exists() else b""
    with (ROOT / "application.log").open("a", encoding="utf-8") as log:
        p = subprocess.Popen([str(python), str(ROOT / "app.py"), "--no-browser"], cwd=ROOT,
                             stdout=log, stderr=log, creationflags=FLAGS)
    for _ in range(100):
        if session.exists() and session.read_bytes() != old:
            webbrowser.open(json.loads(session.read_text(encoding="utf-8"))["url"])
            return
        if p.poll() is not None:
            raise RuntimeError("Le serveur n’a pas démarré. Consulte application.log.")
        time.sleep(.1)
    raise RuntimeError("Le démarrage prend trop longtemps. Consulte application.log.")


def main():
    if '--browser' in sys.argv:
        browser_main()
        return
    exe = ROOT/'VOD Atelier.exe'
    if exe.is_file():
        subprocess.Popen([str(exe)],cwd=ROOT,creationflags=FLAGS)
    else:
        python = ROOT/'.venv'/'Scripts'/'pythonw.exe'
        if not python.is_file():
            raise RuntimeError('Lance Installation/Installer.cmd pour préparer la version bureau.')
        subprocess.Popen([str(python),str(ROOT/'desktop.py')],cwd=ROOT,creationflags=FLAGS)


if __name__ == "__main__":
    main()
