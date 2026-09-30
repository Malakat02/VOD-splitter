"""Shared game/channel tags, independent of individual clip events."""
import re
from title_guard import norm


def units(text):
    # Conservative for characters outside the BMP (e.g. emoji in a game title).
    return len(text.encode('utf-16-le')) // 2


def youtube_length(tags):
    # YouTube counts separators and implicit quotes around tags containing spaces.
    return sum(units(tag) + (2 if ' ' in tag else 0) for tag in tags) + max(0, len(tags) - 1)


def game_tags(game, overview=''):
    game = re.sub(r'\s+', ' ', str(game)).strip()
    # Commas would split one tag into multiple tags when pasted into Studio.
    game = re.sub(r'[,"<>\x00-\x1f]', ' ', game)
    game = re.sub(r'\s+', ' ', game).strip()
    short = game.split(' - ', 1)[0].strip()
    candidates = [game, short, f'{short} français', f'{short} gameplay',
                  f'{short} gameplay français', f'{short} lets play français'] if game else []
    candidates += ['gameplay français', 'gaming français', 'jeu vidéo français',
                   'lets play français', 'VOD français', 'stream français']
    # Genre tags require the game context; never use a clip's noisy transcription.
    context = ' ' + norm(overview) + ' '
    for word, tag in [('survie', 'jeu de survie'), ('horreur', 'jeu d’horreur'),
                      ('roguelike', 'roguelike français'), ('roguelite', 'roguelite français')]:
        if ' ' + word + ' ' in context:
            candidates.append(tag)
    tags, seen = [], set()
    for tag in candidates:
        if not tag or norm(tag) in seen:
            continue
        if youtube_length(tags + [tag]) <= 500:
            tags.append(tag)
            seen.add(norm(tag))
    return {'tags': tags, 'tags_text': ','.join(tags), 'tags_characters': youtube_length(tags)}


def write_tags(directory, game, overview=''):
    result = game_tags(game, overview)
    # Copy/paste only: no headings or explanations mixed into the tag list.
    (directory / 'tags.txt').write_text(result['tags_text'], encoding='utf-8')
    return result
