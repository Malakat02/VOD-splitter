import json
from pathlib import Path
import sys
import threading
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import ROOT, Runner, Cancelled, parse_time, process, probe, binary
from pipeline import clip_plan
from timeline_summary import windows


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

    def test_real_stream_copy_and_short_tail_in_previous_clip(self):
        fixtures = ROOT / "tests" / "fixtures"
        fixtures.mkdir(exist_ok=True)
        source = fixtures / "VOD été test.mp4"
        runner = Runner()
        if not source.exists():
            runner.run([binary("ffmpeg"), "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=10",
                        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=16000", "-t", "135",
                        "-c:v", "libx264", "-preset", "ultrafast", "-g", "20", "-keyint_min", "20",
                        "-sc_threshold", "0", "-bf", "0", "-c:a", "aac", source])
        result = process({"source": str(source), "start": "00:05", "minutes": 1, "montage": False, "smart_cuts": False,
                          "output": str(ROOT / "tests" / "output"), "ai": False}, runner, lambda _: None)
        self.assertEqual(len(result["clips"]), 2)
        self.assertEqual((Path(result['clips'][0]['directory']).parent/'tags.txt').read_text(encoding='utf-8'), result['publication_tags']['tags_text'])
        self.assertLessEqual(result['publication_tags']['tags_characters'], 500)
        self.assertAlmostEqual(result["actual_start"], 6, delta=.1)
        durations = [c["duration"] for c in result["clips"]]
        self.assertTrue(58 <= durations[0] <= 62, durations)
        self.assertTrue(67 <= durations[-1] <= 71, durations)
        self.assertTrue(result['merge_short_tail'])
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
        result = process({"source": str(source), "start": "5", "minutes": 1, "montage": False, "smart_cuts": False,
                          "output": str(ROOT / "tests" / "output")}, runner, lambda _: None)
        self.assertEqual(len(result["clips"]), 1)
        self.assertTrue(64 <= result['clips'][0]['duration'] <= 68)
        self.assertTrue(all(len(probe(c["file"])["audio_codecs"]) == 2 for c in result["clips"]))
        def packets(path):
            return json.loads(runner.run([binary("ffprobe"), "-v", "error", "-select_streams", "v:0",
                "-show_packets", "-show_data_hash", "sha256", "-show_entries", "packet=pts_time,data_hash",
                "-of", "json", path]))["packets"]
        source_packets = packets(source)
        expected = [p["data_hash"] for p in source_packets if float(p["pts_time"]) >= result["actual_start"]-.001]
        actual = [p["data_hash"] for c in result["clips"] for p in packets(c["file"])]
        self.assertEqual(actual, expected)

    def test_clip_plan_merges_only_the_last_remainder(self):
        boundaries, durations = clip_plan(170*60,20*60)
        self.assertEqual(len(durations),8)
        self.assertEqual(boundaries,[20*60*i for i in range(1,8)])
        self.assertEqual(durations[-1],30*60)
        self.assertEqual(len(windows([],durations[-1])),6)
        self.assertEqual(clip_plan(60*60,20*60)[1],[20*60]*3)
        self.assertEqual(clip_plan(50*60,20*60)[1],[20*60,30*60])
        self.assertEqual(clip_plan(10*60,20*60),([],[10*60]))
        self.assertEqual(clip_plan(30*60,20*60),([],[30*60]))
        self.assertEqual(len(clip_plan(40*60-.03,20*60)[1]),2)
        self.assertEqual(len(clip_plan(40*60+.03,20*60)[1]),2)
        for invalid in [float('nan'),float('inf'),0,-1]:
            with self.assertRaises(ValueError):clip_plan(invalid,1200)

    def test_exact_multiple_stays_separate_and_short_vod_stays_single(self):
        folder=ROOT/'tests'/'fixtures'
        folder.mkdir(exist_ok=True)
        source=folder/'exact_120.mp4'
        runner=Runner()
        if not source.exists():
            runner.run([binary('ffmpeg'),'-v','error','-f','lavfi','-i','testsrc2=size=64x64:rate=10',
                        '-t','120','-c:v','libx264','-preset','ultrafast','-g','20','-sc_threshold','0','-bf','0',source])
        result=process({'source':str(source),'start':'0','minutes':1,'montage':False,'smart_cuts':False,'output':str(ROOT/'tests'/'output')},runner,lambda _:None)
        self.assertEqual(len(result['clips']),2)
        self.assertTrue(all(59.9<=c['duration']<=60.1 for c in result['clips']))
        short=process({'source':str(source),'start':'90','minutes':1,'montage':False,'smart_cuts':False,'output':str(ROOT/'tests'/'output')},runner,lambda _:None)
        self.assertEqual(len(short['clips']),1)
        self.assertAlmostEqual(short['clips'][0]['duration'],30,delta=.1)


if __name__ == "__main__":
    unittest.main()
