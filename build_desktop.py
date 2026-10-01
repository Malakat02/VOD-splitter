"""Reproducible Windows EXE build. Run with the project's virtual environment."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def build():
    if sys.platform != 'win32':
        raise RuntimeError('La création de l’EXE nécessite Windows.')
    from PIL import Image, ImageDraw
    icon = ROOT/'Installation'/'atelier.ico'
    if not icon.is_file():
        im = Image.new('RGBA',(256,256),'#0b1018')
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((18,18,238,238),radius=48,fill='#bef264')
        d.polygon([(86,65),(193,128),(86,191)],fill='#142011')
        d.rectangle((50,65,61,191),fill='#142011')
        im.save(icon,sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
    subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onefile',
                    '--windowed','--name','VOD Atelier','--icon',str(icon),
                    '--distpath',str(ROOT),'--workpath',str(ROOT/'cache'/'build'),
                    '--specpath',str(ROOT/'cache'/'build'),str(ROOT/'windows_entry.py')],check=True,cwd=ROOT)
    return ROOT/'VOD Atelier.exe'


if __name__ == '__main__':
    print(build())
