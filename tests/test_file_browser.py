import sys
from pathlib import Path
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from file_browser import browse


class BrowserTests(unittest.TestCase):
    def test_modes_unicode_and_parent_navigation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            child = root / 'Vidéos été'
            child.mkdir()
            video = root / 'Départ du stream.MP4'
            video.write_bytes(b'video')
            (root / 'projet.json').write_text('{}')
            (root / 'secret.txt').write_text('not returned')
            videos = browse(root)
            self.assertEqual([e['name'] for e in videos['entries']], ['Vidéos été', video.name])
            self.assertEqual(browse(video)['path'], str(root.resolve()))
            self.assertEqual(browse(child)['parent'], str(root.resolve()))
            self.assertEqual([e['name'] for e in browse(root, 'folder')['entries']], ['Vidéos été'])
            self.assertEqual([e['name'] for e in browse(root, 'project')['entries']], ['Vidéos été', 'projet.json'])
            self.assertEqual(browse(child, 'project')['entries'], [])
            self.assertTrue(video.exists())

    def test_invalid_paths_and_modes(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                browse(Path(tmp)/'absent')
            with self.assertRaises(ValueError):
                browse(tmp, 'anything')


if __name__ == '__main__':
    unittest.main()
