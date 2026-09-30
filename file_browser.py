"""Read-only local file navigation for the in-page picker."""
import os
from pathlib import Path

VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.mov', '.ts', '.m2ts', '.webm', '.avi', '.flv'}


def browse(path, mode='video'):
    if mode not in {'video', 'folder', 'project'}:
        raise ValueError('Type de sélection invalide.')
    folder = Path(str(path).strip().strip('"')).expanduser().resolve()
    if folder.is_file():
        folder = folder.parent
    if not folder.is_dir():
        raise ValueError('Ce dossier est introuvable. Vérifie son chemin.')
    entries = []
    try:
        with os.scandir(folder) as scan:
            for item in scan:
                try:
                    directory = item.is_dir()
                    if directory or (mode == 'video' and Path(item.name).suffix.lower() in VIDEO_EXTENSIONS) or (mode == 'project' and item.name.lower() == 'projet.json'):
                        entries.append({'name': item.name, 'path': str(Path(item.path)), 'directory': directory})
                except OSError:
                    continue
    except PermissionError:
        raise ValueError('Windows refuse l’accès à ce dossier. Choisis un autre dossier.') from None
    entries.sort(key=lambda item: (not item['directory'], item['name'].casefold()))
    roots = [str(Path(f'{letter}:/')) for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' if Path(f'{letter}:/').is_dir()] if os.name == 'nt' else ['/']
    return {'path': str(folder), 'parent': str(folder.parent), 'entries': entries, 'roots': roots}
