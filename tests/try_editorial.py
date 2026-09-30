"""Manual acceptance run using one existing clip without touching its published outputs."""
from pathlib import Path
import json
import shutil
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import ROOT, Runner, probe, frames_for
from research import game_context
from analysis_local import analyse, title_with_suffix
from pipeline import LazySpeech

import argparse
parser = argparse.ArgumentParser(description="Tester l’analyse d’un clip existant sans modifier ses résultats publiés.")
parser.add_argument("project", type=Path, help="Chemin du fichier projet.json")
parser.add_argument("--game", required=True, help="Nom exact du jeu")
parser.add_argument("--clip", type=int, default=1, help="Numéro du clip à analyser")
args = parser.parse_args()
game = args.game
manifest = json.loads(args.project.read_text(encoding="utf-8"))
item = next((c for c in manifest["clips"] if c["number"] == args.clip), None)
if item is None:
    parser.error("Ce numéro de clip ne figure pas dans le projet.")
source = Path(item["file"])
old = Path(item["directory"])
import tempfile
directory = Path(tempfile.mkdtemp(prefix="editorial_", dir=ROOT/"tests"/"output")) if (ROOT/"tests"/"output").exists() else ROOT/"tests"/"output"/"editorial_review"
directory.mkdir(parents=True, exist_ok=True)
for name in ["transcription.json"]+[f"image_{i:02}.jpg" for i in range(1,9)]:
    if (old/name).exists():
        shutil.copy2(old/name, directory/name)
runner = Runner(lambda s: print(s,flush=True))
context = game_context(game, True, runner)
print("GAME CONTEXT", json.dumps(context,ensure_ascii=True),flush=True)
info = probe(source)
frames = frames_for(source, info["duration"], directory, runner, reuse=True)
result = analyse(source, info, directory, frames, LazySpeech(), runner, context, reuse_legacy=True)
result["titles"] = [title_with_suffix(t,game,args.clip) for t in result["titles"]]
(directory/"validation.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps({k:result[k] for k in ("titles","title_reasons","thumbnail_text","timings")},ensure_ascii=True),flush=True)

print("Résultats du test :", directory)
