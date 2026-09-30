import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis_local import analyse, identity, title_with_suffix
from core import Runner
from pipeline import safe_video_name
from research import within_game_scope
from title_guard import reviewed_candidates, scope_error

GAME = "DIVE or DIE - Children of Rain"


class EditorialTests(unittest.TestCase):
    def test_exact_game_suffix_and_number(self):
        title = title_with_suffix("Je le recrute pour le sacrifier", GAME, 12)
        self.assertEqual(title, "Je le recrute pour le sacrifier [DIVE or DIE - Children of Rain #12]")
        self.assertLessEqual(len(title_with_suffix("Une longue accroche "*20, GAME, 12)), 100)
        self.assertTrue(title_with_suffix("Un risque [Autre jeu #1]", GAME, 12).endswith(f"[{GAME} #12]"))

    def test_foreign_game_rejected_even_if_reviewer_approves(self):
        data = {"candidates": [{"title": t, "moment_id": 1} for t in ["Dave the Diver me piège", "Je manque d’air", "Un sacrifice de trop"]]}
        review = {"scope_game": GAME, "best": [0,1,2], "judgments": [dict(index=i,scope_ok=True,grounded=True,catchy=True) for i in range(3)]}
        with self.assertRaises(ValueError):
            reviewed_candidates(data, review, GAME, [{"id":1}])
        self.assertTrue(scope_error("Je replonge dans Subnautica", GAME))

    def test_reviewer_wrong_scope_and_unproven_event_rejected(self):
        data = {"candidates": [{"title": t, "moment_id": 2} for t in ["Je manque d’air", "Un sacrifice de trop", "Cette idole coûte cher"]]}
        review = {"scope_game": GAME, "best": [0,1,2], "judgments": [dict(index=i,scope_ok=True,grounded=True,catchy=True) for i in range(3)]}
        with self.assertRaises(ValueError):
            reviewed_candidates(data, review, GAME, [{"id":1}])
        review["scope_game"] = "DAVE THE DIVER"
        with self.assertRaises(ValueError):
            reviewed_candidates(data, review, GAME, [{"id":2}])

    def test_search_scope(self):
        self.assertTrue(within_game_scope("DIVE or DIE Wiki – objets", GAME))
        self.assertFalse(within_game_scope("DAVE THE DIVER – Wiki officiel", GAME))
        self.assertFalse(within_game_scope("Plongée et survie : Subnautica", GAME))

    def test_safe_filename_and_identity_survive_rename(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            file = parent/"clip.mp4"
            file.write_bytes(b"video-data"*100)
            before = identity(file)
            target = parent/safe_video_name("Je plonge : sans air [DIVE or DIE #3]", parent, ".mp4", 3)
            file.rename(target)
            self.assertEqual(before, identity(target))
            self.assertNotIn(":", target.name)
            self.assertIn("#3]", target.name)

    def test_regeneration_reuses_transcript_moments_and_all_eight_frames(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            clip = folder/"clip.mp4"
            clip.write_bytes(b"test-video")
            quote = "Je vais le recruter pour le sacrifier"
            (folder/"transcription.json").write_text(json.dumps([{"start":1,"end":3,"text":quote}]),encoding="utf-8")
            frames=[]
            for i in range(8):
                path=folder/f"image_{i+1:02}.jpg"
                path.write_bytes(b"image"+bytes([i]))
                frames.append({"path":path})
            calls=[]
            titles=["Je recrute mon futur sacrifice", "Ce plongeur ne reviendra pas", "Je l’envoie sans équipement"]
            def fake_chat(messages, runner, timings, stage, **kwargs):
                calls.append(stage)
                if stage.startswith("moments"):
                    return {"moments":[{"start_segment":0,"end_segment":0,"event":"Projet de sacrifice","stakes":"Perdre un plongeur"}]}
                if stage=="vision":
                    self.assertEqual(len(kwargs["images"]),8)
                    return {"frame":2,"description":"Un plongeur"}
                if stage.startswith("titles"):
                    return {"candidates":[{"title":t,"moment_id":1,"reason":"citation","thumbnail_text":"Sacrifice prévu"} for t in titles],"summary":"Un sacrifice est prévu."}
                return {"scope_game":GAME,"best":[0,1,2],"judgments":[dict(index=i,scope_ok=True,grounded=True,catchy=True) for i in range(3)]}
            class NoSpeech:
                def transcribe(self,*args,**kwargs):
                    raise AssertionError("Whisper ne doit pas tourner à nouveau")
            with patch("analysis_local.chat",side_effect=fake_chat):
                for _ in range(2):
                    result=analyse(clip,{"audio":True,"duration":4},folder,frames,NoSpeech(),Runner(),{"game":GAME},reuse_legacy=True)
                    self.assertEqual(result["frame"],2)
            self.assertEqual(calls.count("vision"),1)
            self.assertEqual(calls.count("moments_0"),0)
            self.assertEqual(calls.count("titles_0"),2)


if __name__ == "__main__":
    unittest.main()
