from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core import binary
from setup_tools import extract_checked


class SetupToolsTests(unittest.TestCase):
    def test_portable_binaries_take_precedence_and_path_remains_fallback(self):
        with tempfile.TemporaryDirectory() as tmp,patch('core.ROOT',Path(tmp)),patch('core.shutil.which',return_value='system/ffmpeg.exe'):
            folder=Path(tmp)/'tools/ffmpeg/bin';folder.mkdir(parents=True)
            (folder/'ffmpeg.exe').write_bytes(b'test')
            self.assertEqual(binary('ffmpeg'),str(folder/'ffmpeg.exe'))
            self.assertEqual(binary('ffprobe'),'system/ffmpeg.exe')

    def test_archive_cannot_write_outside_installation_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); archive=root/'download.zip';target=root/'extracted'
            with zipfile.ZipFile(archive,'w') as z:
                z.writestr('bin/ffmpeg.exe',b'test')
                z.writestr('../outside.exe',b'bad')
            with self.assertRaises(RuntimeError):extract_checked(archive,target)
            self.assertFalse((root/'outside.exe').exists())
            self.assertFalse((target/'bin/ffmpeg.exe').exists())
