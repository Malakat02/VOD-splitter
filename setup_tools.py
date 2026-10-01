"""Install FFmpeg/FFprobe locally when no usable pair is available."""
import hashlib
import re
import shutil
import subprocess
import urllib.request
import uuid
import zipfile
from pathlib import Path

from core import ROOT, NO_WINDOW, binary

URL = 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip'


def usable(name):
    try:
        return subprocess.run([binary(name),'-version'],capture_output=True,creationflags=NO_WINDOW,timeout=15).returncode == 0
    except (RuntimeError,OSError,subprocess.TimeoutExpired):
        return False


def extract_checked(archive, target):
    target = target.resolve()
    with zipfile.ZipFile(archive) as z:
        for member in z.infolist():
            if not (target/member.filename).resolve().is_relative_to(target):
                raise RuntimeError('Chemin invalide dans l’archive FFmpeg.')
        z.extractall(target)


def setup():
    if usable('ffmpeg') and usable('ffprobe'):
        print('FFmpeg et FFprobe sont déjà disponibles.',flush=True)
        return
    tools = (ROOT/'tools').resolve()
    if not tools.is_relative_to(ROOT.resolve()):
        raise RuntimeError('Le dossier tools se trouve hors de l’application.')
    tools.mkdir(exist_ok=True)
    cache = ROOT/'.cache'/'downloads'
    cache.mkdir(parents=True,exist_ok=True)
    with urllib.request.urlopen(URL+'.sha256',timeout=60) as response:
        match = re.search(r'\b[a-fA-F0-9]{64}\b',response.read().decode('ascii'))
    if not match:
        raise RuntimeError('Empreinte FFmpeg manquante.')
    expected = match[0].lower()
    archive = cache/'ffmpeg.zip'
    def valid(path):
        if not path.is_file():return False
        with path.open('rb') as stream:
            return hashlib.file_digest(stream,'sha256').hexdigest() == expected
    if not valid(archive):
        print('Téléchargement de FFmpeg et FFprobe…',flush=True)
        part = cache/'ffmpeg.zip.part'
        last = [-1]
        def report(count,size,total):
            mb = count*size//(10*1024*1024)
            if mb != last[0]:
                last[0]=mb
                print(f'FFmpeg : {count*size//(1024*1024)} Mo…',flush=True)
        urllib.request.urlretrieve(URL,part,reporthook=report)
        if not valid(part):
            raise RuntimeError('Le téléchargement FFmpeg ne correspond pas à son empreinte SHA-256. Relance l’installation.')
        part.replace(archive)
    stage = tools/('ffmpeg_install_'+uuid.uuid4().hex[:8])
    stage.mkdir()
    extract_checked(archive,stage)
    candidates = [p.parent.parent for p in stage.glob('*/bin/ffmpeg.exe') if (p.parent/'ffprobe.exe').is_file()]
    if len(candidates) != 1:
        raise RuntimeError('Archive FFmpeg inattendue.')
    source = candidates[0].resolve()
    target = (tools/'ffmpeg').resolve()
    if not source.is_relative_to(tools) or not target.is_relative_to(tools):
        raise RuntimeError('Dossier d’installation invalide.')
    if target.exists():
        backup = tools/('ffmpeg_incomplet_'+uuid.uuid4().hex[:8])
        target.rename(backup)
    source.rename(target)
    stage.rmdir()
    if not usable('ffmpeg') or not usable('ffprobe'):
        raise RuntimeError('FFmpeg ou FFprobe ne démarre pas sur ce PC.')
    print('FFmpeg et FFprobe prêts dans tools/ffmpeg/bin, sans modifier le PATH Windows.',flush=True)


if __name__ == '__main__':
    setup()
