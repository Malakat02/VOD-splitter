"""Small EXE entry point; installed dependencies stay alongside the application."""
import ctypes
import os
from pathlib import Path
import subprocess
import sys


def main():
    root = Path(sys.executable if getattr(sys,'frozen',False) else __file__).resolve().parent
    python = root/'.venv'/'Scripts'/'pythonw.exe'
    if not python.is_file():
        python = root/'.venv'/'Scripts'/'python.exe'
    if not python.is_file() or not (root/'desktop.py').is_file():
        raise RuntimeError('Lance Installation\\Installer.cmd dans le dossier de l’application.\nGarde le fichier EXE avec les autres fichiers du dossier.')
    with (root/'application-desktop.log').open('a',encoding='utf-8') as stream:
        subprocess.Popen([str(python),str(root/'desktop.py'),*sys.argv[1:]],cwd=root,
                         stdout=stream,stderr=stream,creationflags=subprocess.CREATE_NO_WINDOW)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        ctypes.windll.user32.MessageBoxW(None,str(exc),'VOD Atelier',0x10)
        sys.exit(1)
