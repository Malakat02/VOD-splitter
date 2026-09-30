"""Deterministic publication checks, complemented by a separate evidence review."""
import re
import unicodedata

# Extra guard against frequent game substitutions in noisy underwater/survival transcripts.
# This is not the primary scope check: every candidate also undergoes a separate model review.
GAME_NAMES = ("DAVE THE DIVER", "Subnautica", "Below Zero", "Minecraft", "Terraria", "Dredge",
              "Rain World", "Dark Souls", "Elden Ring", "Bloodborne", "Fortnite", "Dead by Daylight",
              "Project Zomboid", "The Forest", "Sons of the Forest", "Don't Starve", "No Man's Sky",
              "Deep Rock Galactic", "Sea of Thieves", "Hollow Knight", "Clair Obscur", "Expedition 33")


def norm(text):
    text = unicodedata.normalize("NFKD", str(text)).casefold().replace("’", "'")
    return re.sub(r"[^a-z0-9]+", " ", "".join(c for c in text if not unicodedata.combining(c))).strip()


def scope_error(title, game):
    clean = " " + norm(title) + " "
    for other in GAME_NAMES:
        if " " + norm(other) + " " in clean and norm(other) not in norm(game):
            return f"Référence hors du jeu autorisé : {other}"
    if re.search(r"\[[^\]]*#\s*\d+\]", title):
        return "L’IA a ajouté un suffixe ; seul l’application doit le faire."
    return ""


def generic_title(title):
    value = norm(title)
    return any(phrase in value for phrase in ("gameplay", "survie intense", "analyse du jeu", "strategies et ressources",
                                               "les defis de", "une aventure epique", "secrets du jeu", "et le silence",
                                               "le prix de la survie", "une promesse", "appel des abysses"))


def unknown_name(title, allowed_terms):
    words = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ'’]*", title)
    known = set(norm(" ".join(allowed_terms)).split())
    common = set("je j il ils elle elles on nous vous un une le la les l des de du d ce ces cette c mon ma mes ton ta tes son sa ses sans avec et ou mais plus pas tout tous quand comment pourquoi qui quoi ou quel quelle rien impossible ca c est ai fait neuf dix deux trois quatre cinq six sept huit alors attention jamais encore dernier derniere objectif sacrifice sacrifices prix difficulte course oxygene temps sang choix mort plongeur plongee perdre perdu tuer danger survie cristal cristaux porte portail".split())
    for i, word in enumerate(words):
        if i and word[0].isupper() and norm(word) not in known|common:
            return word
    return ""


def reviewed_candidates(data, review, game, moments, allowed_terms=(), min_count=3):
    if not isinstance(data, dict) or not isinstance(review, dict) or norm(review.get("scope_game", "")) != norm(game):
        raise ValueError("Le contrôle éditorial n’a pas respecté le jeu demandé.")
    candidates = data.get("candidates", [])
    verdicts = {v.get("index"): v for v in review.get("judgments", []) if isinstance(v, dict)}
    valid_ids = {m["id"] for m in moments}
    approved = []
    rejected = []
    seen = set()
    for index in review.get("best", []):
        if type(index) is not int or not 0 <= index < len(candidates) or index in seen:
            continue
        seen.add(index)
        candidate = candidates[index]
        if not isinstance(candidate, dict) or not isinstance(candidate.get("title"), str):
            continue
        title = candidate["title"].strip()
        verdict = verdicts.get(index, {})
        if not title or scope_error(title, game) or generic_title(title) or unknown_name(title, allowed_terms):
            rejected.append(title+" : nom ou formulation non validé")
            continue
        if moments and candidate.get("moment_id") not in valid_ids:
            continue
        if not all(verdict.get(k) is True for k in ("scope_ok", "grounded", "catchy")):
            continue
        proof = next((m.get("quote", "") for m in moments if m["id"] == candidate.get("moment_id")), "")
        percentages = re.findall(r"(\d+)\s*%\s*(?:de\s+|d['’])([A-Za-zÀ-ÖØ-öø-ÿ]+)", title, re.I)
        if any(number not in proof or norm(unit)[:5] not in norm(proof) for number,unit in percentages):
            rejected.append(title+" : le pourcentage change la statistique citée dans le clip")
            continue
        if norm(title) in {norm(c["title"]) for c in approved}:
            continue
        approved.append(candidate)
    if len(approved) < min_count:
        raise ValueError("Pas assez de titres ont passé le contrôle du jeu, des faits et de l’accroche. " + "; ".join(rejected))
    return approved[:3]
