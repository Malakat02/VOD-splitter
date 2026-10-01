"""Shared startup for the desktop window and the optional browser fallback."""
import os
from pathlib import Path
import subprocess

from core import ROOT, MODELS, NO_WINDOW, ollama


def ensure_ollama():
    try:
        ollama()
        return
    except Exception:
        pass
    exe = ROOT / "tools" / "ollama" / "ollama.exe"
    if not exe.is_file():
        return
    env = os.environ.copy()
    env.update(OLLAMA_HOST="127.0.0.1:11434", OLLAMA_MODELS=str(MODELS / "ollama"), OLLAMA_NO_CLOUD="1")
    with (ROOT / "ollama.log").open("a", encoding="utf-8") as log:
        subprocess.Popen([str(exe), "serve"], cwd=ROOT, stdout=log, stderr=log,
                         env=env, creationflags=NO_WINDOW)
