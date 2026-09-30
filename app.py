from __future__ import annotations
import ai_provider
import argparse
import copy
import json
import mimetypes
import os
from pathlib import Path
import secrets
import subprocess
import sys
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from core import ROOT, Runner, Cancelled, ai_status, first_speech, probe, process, thumbnail, write_json, NO_WINDOW
from pipeline import load_project, regenerate
from file_browser import browse

TOKEN = secrets.token_urlsafe(32)
LOCK = threading.RLock()
STATE = {"version": 5, "busy": False, "stage": "Prêt", "progress": 0, "logs": [], "clips": [], "output": ""}
CANCEL = threading.Event()
ALLOWED = set()


def update(values):
    with LOCK:
        STATE.update(copy.deepcopy(values))
        for item in values.get("clips", []):
            ALLOWED.add(Path(item["directory"]).resolve())


def log(message):
    with LOCK:
        STATE["logs"] = (STATE["logs"] + [str(message)])[-150:]


def task(kind, data):
    r = Runner(log, CANCEL)
    provider_token = None
    try:
        provider_token = ai_provider.configure(data)
        if kind == "detect":
            result = first_speech(data["source"], r)
            update({"detected": result, "stage": "Début proposé — à vérifier", "progress": 100})
        elif kind == "install":
            log("Préparation locale : téléchargement des dépendances et modèles. Plusieurs Go, à faire une seule fois.")
            p = subprocess.Popen([sys.executable, "-u", str(ROOT / "setup_ai.py")], stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                                 creationflags=NO_WINDOW)
            # Setup has streaming progress; cancellation handled by terminating the process tree.
            def kill_setup():
                while p.poll() is None:
                    if CANCEL.wait(.5):
                        subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True, creationflags=NO_WINDOW)
                        return
            threading.Thread(target=kill_setup, daemon=True).start()
            for line in p.stdout:
                log(line.strip())
            code = p.wait()
            r.check()
            if code:
                raise RuntimeError("La préparation a échoué. Consulte le journal puis réessaie ; les téléchargements terminés sont conservés.")
            update({"stage": "IA locale prête", "progress": 100})
        elif kind == "regenerate":
            regenerate(data, r, update)
        else:
            process(data, r, update)
    except Cancelled as e:
        update({"stage": "Arrêté", "error": str(e)})
        log(str(e))
    except Exception as e:
        update({"stage": "À vérifier", "error": str(e)})
        log(str(e))
    finally:
        if provider_token is not None:
            ai_provider.SETTINGS.reset(provider_token)
        update({"busy": False})




class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def send(self, data, status=200, content_type="application/json; charset=utf-8"):
        if not isinstance(data, bytes):
            data = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(data)

    def valid_host(self):
        return self.headers.get("Host") == f"127.0.0.1:{self.server.server_port}"

    def authorized(self):
        return self.valid_host() and secrets.compare_digest(self.headers.get("X-Vod-Token", ""), TOKEN)

    def do_GET(self):
        if not self.valid_host():
            return self.send({"error": "Hôte refusé"}, 403)
        url = urllib.parse.urlparse(self.path)
        if url.path == "/":
            return self.send((ROOT / "web" / "index.html").read_bytes(), content_type="text/html; charset=utf-8")
        if url.path in ("/app.js", "/style.css"):
            path = ROOT / "web" / url.path[1:]
            return self.send(path.read_bytes(), content_type="text/javascript; charset=utf-8" if path.suffix == ".js" else "text/css; charset=utf-8")
        if url.path == "/api/state" and self.authorized():
            with LOCK:
                return self.send(copy.deepcopy(STATE))
        if url.path == "/api/models" and self.authorized():
            return self.send({"models": ai_provider.MODEL_CATALOG, "default": ai_provider.OPENAI_MODEL, "pricing_date": "2026-09-30"})
        if url.path == "/api/status" and self.authorized():
            return self.send(ai_status())
        if url.path == "/image":
            query = urllib.parse.parse_qs(url.query)
            if not secrets.compare_digest(query.get("token", [""])[0], TOKEN):
                return self.send({"error": "Accès refusé"}, 403)
            path = Path(query.get("path", [""])[0]).resolve()
            if path.parent in ALLOWED and path.suffix == ".jpg" and path.is_file():
                return self.send(path.read_bytes(), content_type="image/jpeg")
        return self.send({"error": "Introuvable"}, 404)

    def do_POST(self):
        if not self.authorized():
            return self.send({"error": "Accès refusé. Ouvre l’application avec son lanceur."}, 403)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 100000:
                raise ValueError("Requête trop longue")
            data = json.loads(self.rfile.read(length) or b"{}")
            action = self.path.removeprefix("/api/")
            if action == "check_openai":
                provider_token = ai_provider.configure({"provider": "openai", "ai": True, "api_key": data.pop("api_key", ""), "openai_model": data.get("openai_model", ai_provider.OPENAI_MODEL)})
                try:
                    ai_provider.request("models/" + urllib.parse.quote(ai_provider.selected_model(), safe=""))
                    return self.send({"ok": True, "message": f"Clé reconnue, {ai_provider.selected_model()} accessible. Aucun contenu envoyé. Les crédits et droits de génération seront vérifiés au lancement."})
                finally:
                    ai_provider.SETTINGS.reset(provider_token)
            if action == "browse":
                return self.send(browse(data.get("path") or ROOT, data.get("mode", "video")))
            if action == "load_project":
                with LOCK:
                    if STATE["busy"]:
                        raise ValueError("Attends la fin du traitement avant d’ouvrir un projet.")
                    directory, manifest = load_project(data["project"])
                    update({"output": str(directory), "project": str(directory / "projet.json"),
                            "clips": manifest["clips"], "game_context": manifest.get("game_context", {}),
                            "stage": "Projet chargé — vidéos déjà découpées", "progress": 100, "error": ""})
                return self.send({"project": str(directory / "projet.json"), "game": manifest.get("game", ""),
                                  "first_episode": manifest.get("first_episode", 1), "clips": len(manifest["clips"])})
            if action == "probe":
                return self.send(probe(Path(data["source"]).resolve()))
            if action == "cancel":
                CANCEL.set()
                log("Arrêt demandé. L’inférence IA en cours peut prendre un moment avant de rendre la main.")
                return self.send({"ok": True})
            if action == "open":
                with LOCK:
                    path = STATE["output"]
                if path and Path(path).is_dir():
                    os.startfile(path)
                return self.send({"ok": True})
            if action == "thumbnail":
                with LOCK:
                    if STATE["busy"]:
                        raise ValueError("Attends la fin du traitement avant de modifier une miniature.")
                    item = STATE["clips"][int(data["index"])].copy()
                    n = int(data["frame"])
                    if not 1 <= n <= 8:
                        raise ValueError("Image invalide")
                    folder = Path(item["directory"])
                    item["frame"] = n
                    item["thumbnail_text"] = str(data["text"])[:90]
                    thumbnail(folder / f"image_{n:02}.jpg", item["thumbnail_text"], folder / "miniature.jpg", item["number"])
                    write_json(folder / "infos.json", item)
                    STATE["clips"][int(data["index"])] = item
                    manifest_path = Path(STATE["output"]) / "projet.json"
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    manifest["clips"] = STATE["clips"]
                    write_json(manifest_path, manifest)
                return self.send({"ok": True})
            if action in ("start", "detect", "install", "regenerate"):
                with LOCK:
                    if STATE["busy"]:
                        raise ValueError("Un traitement est déjà en cours.")
                    CANCEL.clear()
                    STATE.update({"busy": True, "error": "", "detected": None,
                                  "stage": "Préparation…", "progress": 0, "logs": []})
                    if action == "start":
                        STATE.update({"clips": [], "output": "", "game_context": {}, "project": ""})
                threading.Thread(target=task, args=(action, data), daemon=True).start()
                return self.send({"ok": True})
            self.send({"error": "Action inconnue"}, 404)
        except Exception as e:
            self.send({"error": str(e)}, 400)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{server.server_port}/#token={TOKEN}"
    (ROOT / ".session.json").write_text(json.dumps({"url": url, "pid": os.getpid()}), encoding="utf-8")
    print("VOD Atelier démarré : " + url, flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        CANCEL.set()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
