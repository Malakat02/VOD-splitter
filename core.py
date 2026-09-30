"""Local VOD pipeline. Video/audio streams are always copied, never encoded."""
from __future__ import annotations
import base64
import csv
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parent
MODELS = ROOT / "models"
NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


class Cancelled(Exception):
    pass


class Runner:
    def __init__(self, log=lambda message: None, cancel=None):
        self.log = log
        self.cancel = cancel or threading.Event()

    def check(self):
        if self.cancel.is_set():
            raise Cancelled("Traitement arrêté. Les clips déjà terminés sont conservés.")

    def run(self, args):
        self.check()
        # Temporary files avoid full pipes blocking ffmpeg on long VODs.
        import tempfile
        with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
            p = subprocess.Popen([str(a) for a in args], stdout=out, stderr=err,
                                 creationflags=NO_WINDOW)
            try:
                while p.poll() is None:
                    if self.cancel.wait(.05):
                        p.terminate()
                        try:
                            p.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            p.kill()
                            p.wait()
                        self.check()
                out.seek(0)
                err.seek(0)
                result = out.read().decode("utf-8", errors="replace")
                error = err.read().decode("utf-8", errors="replace")
                if p.returncode:
                    raise RuntimeError(error[-2500:] or f"Échec de {args[0]}")
                return result
            finally:
                if p.poll() is None:
                    p.kill()
                    p.wait()


def binary(name):
    found = shutil.which(name)
    if not found:
        raise RuntimeError(f"{name} introuvable. Installe FFmpeg puis relance l’application.")
    return found


def probe(path, runner=None):
    r = runner or Runner()
    data = json.loads(r.run([binary("ffprobe"), "-v", "error", "-show_format",
                             "-show_streams", "-of", "json", path]))
    video = next((s for s in data["streams"] if s["codec_type"] == "video"
                  and not s.get("disposition", {}).get("attached_pic")), None)
    if not video:
        raise ValueError("Ce fichier ne contient pas de piste vidéo.")
    duration = float(data["format"].get("duration", video.get("duration", 0)))
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("Impossible de déterminer la durée de cette vidéo.")
    return {"duration": duration, "video": video["codec_name"],
            "video_index": video["index"],
            "audio": any(s["codec_type"] == "audio" for s in data["streams"]),
            "audio_codecs": [s["codec_name"] for s in data["streams"] if s["codec_type"] == "audio"],
            "width": video["width"], "height": video["height"],
            "start_time": float(data["format"].get("start_time", 0))}


def parse_time(value):
    parts = str(value).strip().split(":")
    if not 1 <= len(parts) <= 3:
        raise ValueError("Utilise secondes, mm:ss ou hh:mm:ss pour le début.")
    try:
        nums = [float(p) for p in parts]
    except ValueError:
        raise ValueError("Le début doit être une durée, par exemple 05:00.")
    if any(not math.isfinite(n) or n < 0 for n in nums) or any(n >= 60 for n in nums[1:]):
        raise ValueError("Durée invalide.")
    return sum(n * 60 ** i for i, n in enumerate(reversed(nums)))


def stamp(seconds):
    n = max(0, int(seconds))
    return f"{n // 3600:02}:{n // 60 % 60:02}:{n % 60:02}"


def ollama(payload=None, endpoint="tags", timeout=5):
    body = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request("http://127.0.0.1:11434/api/" + endpoint,
                                 data=body, headers={"Content-Type": "application/json"})
    # Do not send local content through a configured system HTTP proxy.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read(3000).decode("utf-8", errors="replace")
        raise RuntimeError(f"Moteur IA local : HTTP {exc.code} — {detail}") from exc


def ai_status():
    import importlib.util
    speech = importlib.util.find_spec("faster_whisper") is not None
    downloaded = (MODELS / "whisper-base" / "model.bin").exists()
    try:
        tags = [m["name"] for m in ollama()["models"]]
        from model_config import TEXT_MODEL, VISION_MODEL
        vision = VISION_MODEL in tags
        editor = TEXT_MODEL in tags
        running = True
    except Exception:
        vision = editor = running = False
    return {"speech": speech and downloaded, "vision": vision, "editor": editor, "ollama": running,
            "ready": speech and downloaded and vision and editor}


def speech_model():
    from faster_whisper import WhisperModel
    path = MODELS / "whisper-base"
    if not (path / "model.bin").exists():
        raise RuntimeError("Installe d’abord les modèles IA avec le bouton de préparation.")
    return WhisperModel(str(path), device="cpu", compute_type="int8",
                        cpu_threads=max(1, min(8, (os.cpu_count() or 4) - 1)),
                        local_files_only=True)


def first_speech(source, runner):
    """Detect a speech candidate in the first 15 minutes; user validates before cutting."""
    import tempfile
    with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
        audio = Path(tmp) / "intro.wav"
        runner.log("Recherche de paroles dans les 15 premières minutes…")
        runner.run([binary("ffmpeg"), "-v", "error", "-i", source, "-t", "900",
                    "-map", "0:a:0", "-ac", "1", "-ar", "16000", audio])
        model = speech_model()
        segments, _ = model.transcribe(str(audio), vad_filter=True, beam_size=3,
                                       condition_on_previous_text=False)
        for seg in segments:
            runner.check()
            if seg.no_speech_prob < .5 and len(seg.text.strip()) >= 8:
                return {"start": max(0, seg.start - 2), "text": seg.text.strip()}
    raise ValueError("Aucune parole fiable trouvée dans les 15 premières minutes. Choisis le début manuellement.")


def next_keyframe(source, start, info, runner):
    if start == 0:
        return 0.0
    # Seek near requested start and only decode keyframes; bounded memory.
    interval = f"{start:.6f}%+120"
    raw = runner.run([binary("ffprobe"), "-v", "error", "-select_streams", str(info["video_index"]),
                      "-skip_frame", "nokey", "-read_intervals", interval,
                      "-show_frames", "-show_entries", "frame=best_effort_timestamp_time",
                      "-of", "json", source])
    for frame in json.loads(raw).get("frames", []):
        pos = float(frame.get("best_effort_timestamp_time", -1)) - info["start_time"]
        if pos + .001 >= start:
            return max(start, pos)
    raise RuntimeError("Aucune image clé trouvée après ce début (dans les 120 secondes). Choisis un autre point de départ.")


def write_json(path, data):
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def frames_for(clip, duration, directory, runner, reuse=False):
    from PIL import Image, ImageDraw, ImageStat, ImageFilter, ImageFont
    frames = []
    for i in range(8):
        runner.check()
        t = duration * (i + 1) / 9
        dest = directory / f"image_{i+1:02}.jpg"
        if not (reuse and dest.exists()):
            runner.run([binary("ffmpeg"), "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", clip,
                    "-frames:v", "1", "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2",
                    "-q:v", "2", dest])
        with Image.open(dest) as im:
            gray = im.convert("L").resize((320, 180))
            # Ranking is a fallback only, not semantic understanding.
            light = ImageStat.Stat(gray).mean[0]
            edges = ImageStat.Stat(gray.filter(ImageFilter.FIND_EDGES)).mean[0]
            score = edges - abs(light - 120) / 20
        frames.append({"path": dest, "time": t, "score": score})
    sheet = Image.new("RGB", (1280, 800), "#111820")
    draw = ImageDraw.Draw(sheet)
    for i, f in enumerate(frames):
        with Image.open(f["path"]) as im:
            sheet.paste(im.resize((320, 180)), ((i % 4) * 320, (i // 4) * 400))
        draw.text(((i % 4) * 320 + 12, (i // 4) * 400 + 188),
                  f"{i+1} | {stamp(f['time'])}", fill="white", font=ImageFont.truetype("arial.ttf", 24) if os.name == "nt" else None)
    sheet.save(directory / "planche.jpg", quality=90)
    return frames


def thumbnail(frame, title, dest, episode):
    from PIL import Image, ImageDraw, ImageFont
    im = Image.open(frame).convert("RGB").resize((1280, 720))
    overlay = Image.new("RGBA", im.size)
    d = ImageDraw.Draw(overlay)
    for y in range(720):
        alpha = int(220 * max(0, (y - 160) / 560))
        d.line((0, y, 1280, y), fill=(6, 10, 18, alpha))
    im = Image.alpha_composite(im.convert("RGBA"), overlay)
    d = ImageDraw.Draw(im)
    fontpath = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "arialbd.ttf"
    def font(size):
        return ImageFont.truetype(str(fontpath), size) if fontpath.exists() else ImageFont.load_default(size=size)
    title = " ".join(title.split())[:90].upper()
    size = 82
    while True:
        f = font(size)
        lines, current = [], ""
        for word in title.split():
            candidate = (current + " " + word).strip()
            if d.textlength(candidate, font=f) > 1140 and current:
                lines.append(current)
                current = word
            else:
                current = candidate
        lines.append(current)
        if (len(lines) <= 3 and all(d.textlength(line, font=f) <= 1140 for line in lines)) or size <= 24:
            break
        size -= 4
    d.rounded_rectangle((48, 44, 260, 100), radius=12, fill="#bef264")
    d.text((66, 52), f"ÉPISODE {episode:02}", fill="#142011", font=font(28))
    d.rectangle((50, 660-len(lines)*(size+8), 58, 666), fill="#bef264")
    d.multiline_text((82, 660-len(lines)*(size+8)), "\n".join(lines), fill="white",
                     font=f, spacing=8, stroke_width=2, stroke_fill="#10151c")
    im.convert("RGB").save(dest, quality=91, optimize=True)


def analyse(*args, **kwargs):
    from analysis_local import analyse as implementation
    return implementation(*args, **kwargs)


def process(*args, **kwargs):
    from pipeline import process as implementation
    return implementation(*args, **kwargs)
