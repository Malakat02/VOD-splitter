"""Cut once, expose completed clips immediately, and edit publications without re-cutting."""
from publication_tags import write_tags
import ai_provider
import json
import math
from pathlib import Path
import re
import shutil
import time
import uuid

from core import (Cancelled, binary, frames_for, next_keyframe, probe, parse_time,
                  speech_model, stamp, thumbnail, write_json, ai_status)
from analysis_local import analyse, identity, digest, cached, save_cache, title_with_suffix
from research import clean_game, game_context


class LazySpeech:
    def __init__(self):
        self.model = None

    def transcribe(self, *args, **kwargs):
        if self.model is None:
            self.model = speech_model()
        return self.model.transcribe(*args, **kwargs)


def settings(config):
    game = clean_game(config.get("game", ""))
    first = int(config.get("first_episode", 1))
    if not 1 <= first <= 99999:
        raise ValueError("Le numéro du premier clip doit être compris entre 1 et 99999.")
    return game, first


def safe_video_name(title, parent, extension, number):
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", title).strip(" .")
    limit = min(160, 240-len(str(parent))-len(extension)-1)
    if limit < 30 or len(name) > limit:
        # Keep the full publication title in metadata; prefer a short safe filename to a broken path.
        match = re.search(r"\s*(\[[^\]]+#\d+\])$", name)
        if match and len(match[1])+12 < limit:
            suffix = " " + match[1]
            name = name[:limit-len(suffix)].rstrip(" .") + suffix
        else:
            name = f"clip_{number:03d}"
    if re.match(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)", name, re.I):
        name = "_" + name
    return name + extension


def save_project(directory, manifest, update):
    write_json(directory / "projet.json", manifest)
    update({"clips": manifest["clips"], "project": str(directory / "projet.json"),
            "output": str(directory), "game_context": manifest.get("game_context", {}),
            "publication_tags": manifest.get("publication_tags", {})})


def load_project(path):
    path = Path(path).resolve()
    if path.is_dir():
        path = path / "projet.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("clips"), list):
        raise ValueError("Ce fichier n’est pas un projet VOD Atelier.")
    root = path.parent
    found = set()
    for item in data["clips"]:
        file = Path(item["file"]).resolve()
        folder = Path(item["directory"]).resolve()
        if file.parent != root or folder.parent != root or not file.is_file() or file.suffix.lower() not in {".mp4", ".mkv"}:
            raise ValueError("Un clip du projet est manquant ou se trouve hors du dossier du projet.")
        found.add(file)
    # Older interrupted jobs may already contain all copied videos but no per-clip records yet.
    for file in sorted(root.glob("clip_*.*")):
        if file.suffix.lower() not in {".mp4", ".mkv"} or file.resolve() in found:
            continue
        match = re.fullmatch(r"clip_(\d+)", file.stem)
        if not match:
            continue
        info = probe(file)
        n = int(match[1])
        data["clips"].append({"number": n, "file": str(file), "directory": str(root/file.stem),
                              "duration": info["duration"], "titles": [f"Clip {n}"], "ai": False, "status": "pending"})
    if not data["clips"]:
        raise ValueError("Ce projet ne contient aucun clip terminé.")
    data["clips"].sort(key=lambda item: item["number"])
    return root, data


def enrich(directory, manifest, config, runner, update, reuse=False):
    game, first = settings(config)
    use_ai = bool(config.get("ai", False))
    if use_ai and not ai_provider.ready(ai_status()):
        raise ValueError("Prépare l’IA locale : Whisper et Qwen sont nécessaires pour les résumés de cinq minutes, même avec OpenAI pour les titres.")
    manifest.update(openai_model=ai_provider.selected_model() if ai_provider.remote() else None, provider="openai" if ai_provider.remote() else "local", game=game, first_episode=first, status="analysing")
    context = {"game": game, "sources": [], "terms": [], "web": False}
    if use_ai:
        update({"stage": "Contexte du jeu", "progress": 12})
        try:
            context = game_context(game, bool(config.get("web", False)), runner, bool(config.get("refresh_web", False)))
        except Cancelled:
            raise
        except Exception as e:
            context["warning"] = "Contexte Internet indisponible : " + str(e)
            runner.log(context["warning"])
    manifest["publication_tags"] = write_tags(directory, game, context.get("overview", ""))
    manifest["game_context"] = context
    write_json(directory / "contexte_jeu.json", context)
    save_project(directory, manifest, update)
    model = LazySpeech()
    errors = 0
    for index, item in enumerate(manifest["clips"]):
        runner.check()
        started = time.perf_counter()
        number = first+index
        item["number"] = number
        clip, folder = Path(item["file"]), Path(item["directory"])
        folder.mkdir(exist_ok=True)
        if reuse and (folder / "infos.json").exists():
            history = folder / "historique" / (time.strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:4])
            history.mkdir(parents=True)
            for name in ("infos.json", "titres.txt", "miniature.jpg", "analyse_editoriale.json"):
                if (folder/name).exists():
                    shutil.copy2(folder/name, history/name)
        item.pop("warning", None)
        item["status"] = "analysing"
        item["ai"] = False
        runner.log(f"Clip {index+1}/{len(manifest['clips'])} — vidéo déjà disponible ; préparation de la publication…")
        update({"stage": f"Analyse {index+1} / {len(manifest['clips'])}", "progress": 15+80*index/len(manifest["clips"])})
        save_project(directory, manifest, update)
        info = probe(clip, runner)
        item["duration"] = info["duration"]
        try:
            frame_key = digest({"clip": identity(clip), "count": 8, "resolution": [1280,720], "version": 1})
            frame_cache = folder / "frames.cache.json"
            reuse_frames = cached(frame_cache, frame_key) is not None or reuse
            frame_started = time.perf_counter()
            frames = frames_for(clip, info["duration"], folder, runner, reuse=reuse_frames)
            frame_seconds = round(time.perf_counter()-frame_started, 2)
            save_cache(frame_cache, frame_key, True)
            chosen = max(range(8), key=lambda n: frames[n]["score"])
            item.update(frame=chosen+1, thumbnail_text=f"PARTIE {number:02}")
            if use_ai:
                item.update(analyse(clip, info, folder, frames, model, runner, context,
                                    reuse_legacy=reuse and bool(config.get("reuse_transcript", True))))
                item["ai"] = True
            else:
                item["titles"] = [f"Épisode {number}"]
            item["titles"] = [title_with_suffix(t, game, number) for t in item["titles"]]
            thumbnail(frames[item["frame"]-1]["path"], item["thumbnail_text"], folder/"miniature.jpg", number)
            item["thumbnail"] = str(folder/"miniature.jpg")
            (folder/"titres.txt").write_text("\n".join(item["titles"])+"\n\n"+item.get("summary", "Analyse IA désactivée."), encoding="utf-8")
            if game:
                target = directory/safe_video_name(item["titles"][0], directory, clip.suffix, number)
                if target != clip:
                    if target.exists():
                        # Never overwrite a clip, including after a renumbering collision.
                        item["warning"] = "Nom de fichier déjà utilisé ; titre enregistré dans titres.txt."
                    else:
                        clip.rename(target)
                        item["file"] = str(target)
            item.setdefault("timings", {})["frames"] = frame_seconds
            item["timings"]["total"] = round(time.perf_counter()-started, 2)
            item["status"] = "ready"
        except Cancelled:
            item["status"] = "pending"
            manifest["status"] = "interrupted"
            save_project(directory, manifest, update)
            raise
        except Exception as e:
            errors += 1
            item["warning"] = str(e)
            item["status"] = "warning"
            item["titles"] = [title_with_suffix(f"À revoir — épisode {number}", game, number)]
            item["summary"] = "La publication n’a pas été validée. Consulte l’avertissement et relance la rédaction."
            runner.log(f"Vidéo conservée ; publication à vérifier : {e}")
        write_json(folder/"infos.json", item)
        (folder/"titres.txt").write_text("\n".join(item["titles"])+"\n\n"+item.get("summary", ""), encoding="utf-8")
        save_project(directory, manifest, update)
    manifest["status"] = "completed_with_warnings" if errors else "completed"
    save_project(directory, manifest, update)
    update({"progress": 100, "stage": "Terminé avec avertissements" if errors else "Terminé"})
    runner.log(f"{len(manifest['clips'])} clips prêts dans {directory}")
    return manifest


def regenerate(config, runner, update):
    directory, manifest = load_project(config["project"])
    runner.log("Projet existant : aucun découpage et aucune copie des vidéos.")
    return enrich(directory, manifest, config, runner, update, reuse=True)


def process(config, runner, update):
    source = Path(config["source"]).resolve()
    if not source.is_file():
        raise ValueError("Choisis un fichier vidéo existant.")
    game, first = settings(config)
    info = probe(source, runner)
    start = parse_time(config.get("start", "05:00"))
    minutes = float(config.get("minutes", 20))
    if not math.isfinite(minutes) or not 1 <= minutes <= 120:
        raise ValueError("La durée des clips doit être comprise entre 1 et 120 minutes.")
    if start >= info["duration"]:
        raise ValueError("Le début choisi dépasse la fin de la vidéo.")
    if config.get("ai") and not ai_provider.ready(ai_status()):
        raise ValueError("Prépare l’IA locale : Whisper et Qwen sont nécessaires pour les résumés de cinq minutes, même avec OpenAI pour les titres. Ou décoche l’analyse.")
    output = Path(config.get("output") or source.parent/"Clips VOD").resolve()
    output.mkdir(parents=True, exist_ok=True)
    directory = output/(source.stem[:65]+"_"+time.strftime("%Y%m%d_%H%M%S")+"_"+uuid.uuid4().hex[:4])
    directory.mkdir()
    actual_start = next_keyframe(source, start, info, runner)
    if actual_start >= info["duration"]-.1:
        raise ValueError("Aucune séquence utilisable après ce début.")
    runner.log(f"Début retenu : {stamp(actual_start)} (image clé, écart {actual_start-start:.2f} s).")
    mp4_ok = info["video"] in {"h264", "hevc", "av1", "mpeg4"} and all(
        c in {"aac", "mp3", "ac3", "eac3", "alac"} for c in info["audio_codecs"])
    ext = ".mp4" if mp4_ok else ".mkv"
    manifest = {"source": str(source), "requested_start": start, "actual_start": actual_start,
                "target_seconds": minutes*60, "game": game, "first_episode": first, "clips": [], "status": "cutting"}
    save_project(directory, manifest, update)
    runner.log("Découpage sans réencodage — une seule passe d’écriture des pistes vidéo et audio…")
    update({"stage": "Découpage des vidéos", "progress": 5})
    args = [binary("ffmpeg"), "-v", "warning", "-nostdin", "-ss", f"{actual_start:.6f}", "-i", source,
            "-map", f"0:{info['video_index']}", "-map", "0:a?", "-c", "copy", "-avoid_negative_ts", "make_zero",
            "-f", "segment", "-segment_time", str(minutes*60), "-segment_time_delta", "0.1", "-reset_timestamps", "1",
            "-segment_start_number", "1", "-segment_list", directory/"segments.csv", "-segment_list_type", "csv",
            directory/("clip_%03d"+ext)]
    started = time.perf_counter()
    try:
        runner.run(args)
    except Exception:
        manifest["status"] = "interrupted"
        save_project(directory, manifest, update)
        raise
    manifest["cut_seconds"] = round(time.perf_counter()-started, 2)
    clips = sorted(directory.glob("clip_*"+ext))
    if not clips:
        raise RuntimeError("FFmpeg n’a produit aucun clip.")
    for idx, clip in enumerate(clips):
        ci = probe(clip, runner)
        manifest["clips"].append({"number": first+idx, "file": str(clip), "duration": ci["duration"],
            "directory": str(directory/clip.stem), "titles": [title_with_suffix(f"Épisode {first+idx}", game, first+idx)],
            "ai": False, "status": "pending"})
    manifest["status"] = "cut_complete"
    save_project(directory, manifest, update)
    runner.log(f"Découpage terminé en {manifest['cut_seconds']:.1f} s : {len(clips)} vidéos déjà disponibles. L’analyse commence séparément.")
    return enrich(directory, manifest, config, runner, update)
