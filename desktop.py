"""Windows desktop window; the existing app runs inside it, without a browser."""
import argparse
import json
import os
from pathlib import Path
import sys
import threading
import time
from http.server import ThreadingHTTPServer

from core import ROOT
import app
from local_runtime import ensure_ollama


class DesktopSession:
    def __init__(self, reuse_port=True):
        # Reuse an available port to retain the model/game preferences in localStorage.
        config = ROOT/'cache'/'desktop-port.json'
        try:
            port = json.loads(config.read_text(encoding='utf-8'))['port']
            if type(port) is not int or not 1024 <= port <= 65535:
                port = 0
        except (OSError,ValueError,KeyError,TypeError):
            port = 0
        if not reuse_port:
            port = 0
        try:
            self.server = ThreadingHTTPServer(("127.0.0.1", port), app.Handler)
        except OSError:
            self.server = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        if reuse_port:
            config.parent.mkdir(parents=True,exist_ok=True)
            config.write_text(json.dumps({'port':self.server.server_port}),encoding='utf-8')
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.url = f"http://127.0.0.1:{self.server.server_port}/#token={app.TOKEN}"

    def start(self):
        self.thread.start()

    def stop(self):
        app.CANCEL.set()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


class DesktopApi:
    def __init__(self):
        self._window = None

    def choose_path(self, kind, current=''):
        import webview
        if kind not in ('video', 'folder', 'project'):
            raise ValueError('Sélection inconnue')
        with app.LOCK:
            if app.STATE['busy']:
                raise ValueError('Attends la fin du traitement.')
        path = Path(str(current)).expanduser() if current else ROOT
        directory = path if path.is_dir() else path.parent
        if not directory.is_dir():
            directory = ROOT
        types = ('Vidéos (*.mp4;*.mkv;*.mov;*.ts;*.webm;*.avi;*.m2ts;*.flv)', 'Tous les fichiers (*.*)') if kind == 'video' else ('Projet VOD (projet.json)', 'JSON (*.json)')
        result = self._window.create_file_dialog(webview.FileDialog.FOLDER if kind == 'folder' else webview.FileDialog.OPEN,
                                                directory=str(directory),allow_multiple=False,file_types=types)
        return str(result[0]) if result else None


class CloseController:
    def __init__(self, window):
        self.window = window
        self.closing = threading.Event()

    def on_closing(self):
        with app.LOCK:
            busy = app.STATE['busy']
        if not busy:
            return True
        if self.closing.is_set():
            return False
        if not self.window.create_confirmation_dialog('Traitement en cours',
                'Arrêter le traitement et fermer ? Les clips déjà terminés seront conservés.'):
            return False
        self.closing.set()
        app.CANCEL.set()
        app.log('Fermeture demandée : attente de la fin de l’opération en cours…')
        def finish():
            while app.STATE['busy']:
                time.sleep(.2)
            self.window.destroy()
        threading.Thread(target=finish, daemon=True).start()
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--smoke-test', action='store_true')
    args = parser.parse_args()
    os.chdir(ROOT)
    if args.smoke_test:
        print('Initialisation de la fenêtre Windows…',flush=True)
    import webview
    if args.smoke_test:
        print('Moteur graphique importé.',flush=True)
    if os.name == 'nt':
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('VODAtelier.Desktop')
    ensure_ollama()
    session = DesktopSession(reuse_port=not args.smoke_test)
    session.start()
    if args.smoke_test:
        print('Serveur interne démarré.',flush=True)
    api = DesktopApi()
    window = webview.create_window('VOD Atelier', session.url, width=1360, height=900,
                                   min_size=(900, 640), background_color='#0b1018',
                                   text_select=True, focus=not args.smoke_test, js_api=api)
    api._window = window
    controller = CloseController(window)
    window.events.closing += controller.on_closing
    if args.smoke_test:
        def loaded():
            # Read-only acceptance check; never start analysis or touch API keys.
            import urllib.request
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            base = session.url.split('#')[0]
            with opener.open(urllib.request.Request(base+'api/state',headers={'X-Vod-Token':app.TOKEN}),timeout=5) as response:
                state = json.load(response)
            with opener.open(base,timeout=5) as response:
                html = response.read().decode('utf-8')
            result = {'loaded':True,'url':window.get_current_url().split('#')[0], 'version':state['version'],
                      'controls':all(f'id="{name}"' in html for name in ('source','provider','launch','montage','smart-cuts','render-quality','video-encoder')),
                      'av1_option':window.evaluate_js("!!document.querySelector('#video-encoder option[value=gpu_av1]')"),
                      'montage_defaults':window.evaluate_js("({montage:document.getElementById('montage').checked,smart_cuts:document.getElementById('smart-cuts').checked,quality:document.getElementById('render-quality').value,encoder:document.getElementById('video-encoder').value})")}
            report = ROOT/'tests'/'output'/'desktop-smoke.json'
            report.parent.mkdir(parents=True,exist_ok=True)
            report.write_text(json.dumps(result),encoding='utf-8')
            window.destroy()
        window.events.loaded += loaded
    try:
        webview.settings['ALLOW_FILE_URLS'] = False
        webview.settings['OPEN_DEVTOOLS_IN_DEBUG'] = False
        if args.smoke_test:
            print('Ouverture de WebView2…',flush=True)
        webview.start(gui='edgechromium', debug=False, private_mode=False,
                      storage_path=str(ROOT/'cache'/'desktop'),
                      icon=str(ROOT/'Installation'/'atelier.ico'))
    finally:
        session.stop()


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        import traceback
        with (ROOT/'application-desktop.log').open('a',encoding='utf-8') as stream:
            traceback.print_exc(file=stream)
        if os.name == 'nt' and '--smoke-test' not in sys.argv:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None,
                f'Impossible de démarrer VOD Atelier : {exc}\n\nRelance Installation\\Installer.cmd. Détails : application-desktop.log.',
                'VOD Atelier',0x10)
        sys.exit(1)
