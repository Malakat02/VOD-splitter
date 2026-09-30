"""One-time downloads only. All inference is local; no user media is uploaded."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from core import ROOT, MODELS, NO_WINDOW, ollama

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")
os.environ.setdefault("HF_HOME", str(MODELS / "huggingface-cache"))
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")


def say(text):
    print(text, flush=True)


def setup():
    say("1/4 — Installation de faster-whisper et Pillow…")
    subprocess.run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
                    "-r", str(ROOT / "requirements.txt")], check=True, creationflags=NO_WINDOW)
    say("2/4 — Téléchargement du modèle de transcription Whisper base (environ 150 Mo)…")
    from huggingface_hub import snapshot_download
    MODELS.mkdir(exist_ok=True)
    snapshot_download("Systran/faster-whisper-base", local_dir=MODELS / "whisper-base",
                      allow_patterns=["model.bin", "config.json", "tokenizer.json", "vocabulary.*", "preprocessor_config.json"])
    try:
        ollama()
    except Exception:
        exe = shutil.which("ollama")
        if not exe:
            exe = ROOT / "tools" / "ollama" / "ollama.exe"
            if not exe.exists():
                say("3/4 — Téléchargement d’Ollama portable (plusieurs Go, selon la version)…")
                dest = ROOT / "tools"
                dest.mkdir(exist_ok=True)
                archive = dest / "ollama.zip"
                # Official release asset; no system-wide install or admin rights.
                req = urllib.request.Request("https://api.github.com/repos/ollama/ollama/releases/latest", headers={"User-Agent": "VOD-Atelier"})
                with urllib.request.urlopen(req, timeout=60) as response:
                    release = json.load(response)
                asset = next(a for a in release["assets"] if a["name"] == "ollama-windows-amd64.zip")
                last = [-1]
                def report(count, size, total):
                    mb = count*size // (100*1024*1024)
                    if mb != last[0]:
                        last[0] = mb
                        say(f"Ollama : {count*size // (1024*1024)} Mo téléchargés…")
                urllib.request.urlretrieve(asset["browser_download_url"], archive, reporthook=report)
                say("Extraction d’Ollama…")
                target = (dest / "ollama").resolve()
                with zipfile.ZipFile(archive) as z:
                    for member in z.infolist():
                        path = (target / member.filename).resolve()
                        if not path.is_relative_to(target):
                            raise RuntimeError("Chemin invalide dans l’archive Ollama")
                    z.extractall(target)
                archive.unlink()
        env = os.environ.copy()
        env["OLLAMA_HOST"] = "127.0.0.1:11434"
        env["OLLAMA_MODELS"] = str(MODELS / "ollama")
        env["OLLAMA_NO_CLOUD"] = "1"
        with (ROOT / "ollama.log").open("a", encoding="utf-8") as logfile:
            subprocess.Popen([str(exe), "serve"], env=env, stdout=logfile, stderr=logfile,
                             creationflags=NO_WINDOW)
        for _ in range(90):
            try:
                ollama()
                break
            except Exception:
                time.sleep(1)
        else:
            raise RuntimeError("Ollama ne démarre pas. Voir ollama.log.")
    from model_config import TEXT_MODEL, VISION_MODEL
    for model in dict.fromkeys((VISION_MODEL, TEXT_MODEL)):
        say(f"4/4 — Préparation du modèle local {model}…")
        req = urllib.request.Request("http://127.0.0.1:11434/api/pull",
                                     data=json.dumps({"model": model, "stream": True}).encode(),
                                     headers={"Content-Type": "application/json"})
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        last = ""
        with opener.open(req, timeout=3600) as response:
            for line in response:
                item = json.loads(line)
                if "error" in item:
                    raise RuntimeError(item["error"])
                percent = int(100*item.get("completed", 0)/max(1, item.get("total", 1)))
                message = item.get("status", "") + f" {percent}%"
                if message != last:
                    say(message)
                    last = message
    say("Vérification du moteur de transcription…")
    from core import speech_model, ai_status
    speech_model()
    if not ai_status()["ready"]:
        raise RuntimeError("Les modèles ne sont pas tous disponibles.")
    say("IA locale prête. Aucun abonnement ni clé API nécessaire.")


if __name__ == "__main__":
    try:
        setup()
    except Exception as e:
        say("ERREUR : " + str(e))
        sys.exit(1)
