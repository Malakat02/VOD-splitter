import sys
from pathlib import Path
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from publication_tags import game_tags, write_tags, youtube_length


class TagTests(unittest.TestCase):
    def test_game_french_content_and_genre_are_shared(self):
        result = game_tags('DIVE or DIE - Children of Rain', 'Un jeu de survie et d’horreur.')
        self.assertIn('DIVE or DIE - Children of Rain', result['tags'])
        self.assertIn('gameplay français', result['tags'])
        self.assertIn('jeu de survie', result['tags'])
        self.assertNotIn('jeu de survie', game_tags('Autre jeu')['tags'])
        self.assertEqual(result['tags_characters'], youtube_length(result['tags']))
        self.assertLessEqual(result['tags_characters'], 500)

    def test_count_quotes_commas_and_unicode_conservatively(self):
        self.assertEqual(youtube_length(['Foo-Baz']), 7)
        self.assertEqual(youtube_length(['Foo Baz']), 9)
        self.assertEqual(youtube_length(['Foo Baz', 'Bar']), 13)
        self.assertEqual(youtube_length(['😀']), 2)
        for game in ['A' * 490, 'Jeu très long ' * 30, '😀 ' * 120, 'Nom, avec "guillemets"']:
            result = game_tags(game)
            self.assertLessEqual(result['tags_characters'], 500)
            self.assertLessEqual(len(result['tags_text']), 500)
            self.assertEqual(result['tags_text'].split(','), result['tags'])

    def test_one_copyable_file_in_project_and_game_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = write_tags(root, 'Premier jeu')
            self.assertEqual((root/'tags.txt').read_text(encoding='utf-8'), first['tags_text'])
            second = write_tags(root, 'Second jeu')
            self.assertNotIn('Premier jeu', second['tags_text'])
            self.assertEqual(list(root.iterdir()), [root/'tags.txt'])


if __name__ == '__main__':
    unittest.main()
