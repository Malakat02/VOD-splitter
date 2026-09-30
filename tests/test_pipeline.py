import json
from pathlib import Path
import sys
import threading
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import ROOT, Runner, Cancelled, parse_time, process, probe, binary


class PipelineTests(unittest.TestCase):
    def test_time_validation(self):
        self.assertEqual(parse_time("01:02:03"), 3723)
        self.assertEqual(parse_time("05:00"), 300)
        for invalid in ["nan", "inf", "-1", "1:70", "bonjour", "1:2:3:4"]:
            with self.assertRaises(ValueError):
                parse_time(invalid)

    def test_cancel(self):
        event = threading.Event()
        event.set()
        with self.assertRaises(Cancelled):
            Runner(cancel=event).run([binary("ffmpeg"), "-version"])

    def test_real_stream_copy_and_short_last_clip(self):
        fixtures = ROOT / "tests" / "fixtures"
        fixtures.mkdir(exist_ok=True)
        source = fixtures / "VOD été test.mp4"
        runner = Runner()
        if not source.exists():
            runner.run([binary("ffmpeg"), "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=10",
                        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=16000", "-t", "135",
                        "-c:v", "libx264", "-preset", "ultrafast", "-g", "20", "-keyint_min", "20",
                        "-sc_threshold", "0", "-bf", "0", "-c:a", "aac", source])
        result = process({"source": str(source), "start": "00:05", "minutes": 1,
                          "output": str(ROOT / "tests" / "output"), "ai": False}, runner, lambda _: None)
        self.assertEqual(len(result["clips"]), 3)
        self.assertEqual((Path(result['clips'][0]['file']).parent/'tags.txt').read_text(encoding='utf-8'), result['publication_tags']['tags_text'])
        self.assertLessEqual(result['publication_tags']['tags_characters'], 500)
        self.assertAlmostEqual(result["actual_start"], 6, delta=.1)
        durations = [c["duration"] for c in result["clips"]]
        self.assertTrue(all(58 <= d <= 62 for d in durations[:2]), durations)
        self.assertTrue(7 <= durations[-1] <= 11, durations)
        # Packet hashes prove that every video packet after the cut is copied exactly once.
        def hashes(path):
            raw = runner.run([binary("ffprobe"), "-v", "error", "-select_streams", "v:0",
                              "-show_packets", "-show_data_hash", "sha256", "-show_entries",
                              "packet=pts_time,data_hash", "-of", "json", path])
            return json.loads(raw)["packets"]
        expected = [p["data_hash"] for p in hashes(source) if float(p["pts_time"]) >= result["actual_start"]-.001]
        actual = []
        for clip in result["clips"]:
            actual += [p["data_hash"] for p in hashes(clip["file"])]
            self.assertEqual(probe(clip["file"])["video"], "h264")
            self.assertTrue(Path(clip["thumbnail"]).is_file())
        self.assertEqual(actual, expected)

    def test_b_frames_multiple_audio_tracks(self):
        folder = ROOT / "tests" / "fixtures"
        folder.mkdir(exist_ok=True)
        source = folder / "bframes.mp4"
        runner = Runner()
        if not source.exists():
            runner.run([binary("ffmpeg"), "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=160x90:rate=25",
                        "-f", "lavfi", "-i", "sine=frequency=440", "-t", "72", "-map", "0:v", "-map", "1:a", "-map", "1:a",
                        "-c:v", "libx264", "-g", "50", "-sc_threshold", "0", "-bf", "3", "-c:a", "aac", source])
        result = process({"source": str(source), "start": "5", "minutes": 1,
                          "output": str(ROOT / "tests" / "output")}, runner, lambda _: None)
        self.assertEqual(len(result["clips"]), 2)
        self.assertTrue(all(len(probe(c["file"])["audio_codecs"]) == 2 for c in result["clips"]))
        def packets(path):
            return json.loads(runner.run([binary("ffprobe"), "-v", "error", "-select_streams", "v:0",
                "-show_packets", "-show_data_hash", "sha256", "-show_entries", "packet=pts_time,data_hash",
                "-of", "json", path]))["packets"]
        source_packets = packets(source)
        expected = [p["data_hash"] for p in source_packets if float(p["pts_time"]) >= result["actual_start"]-.001]
        actual = [p["data_hash"] for c in result["clips"] for p in packets(c["file"])]
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
