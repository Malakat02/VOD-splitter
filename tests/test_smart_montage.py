import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock

import test_montage as fixtures
from core import ROOT, Runner, Cancelled, binary, probe
from montage import assets
from smart_montage import hybrid, render_smart, plan, check_idr, Incompatible


class SmartMontageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.MontageTests.setUpClass()
        cls.source=fixtures.MontageTests.source
        cls.fixture=fixtures.MontageTests.fixture
        cls.r=Runner()
        cls.media=assets(cls.fixture,cls.r)

    pixels=fixtures.MontageTests.pixels
    audio=fixtures.MontageTests.audio

    def hashes(self,args):
        text=self.r.run([binary('ffmpeg'),'-v','error',*args,'-an','-s','160x90',
                        '-pix_fmt','yuv420p','-fps_mode','passthrough','-f','framemd5','-'])
        return [line.split(',')[-1].strip() for line in text.splitlines() if line and not line.startswith('#')]

    def test_real_copy_is_pixel_identical_with_continuous_junctions_and_both_tracks(self):
        dest=ROOT/'tests/output/hybrid-real.mp4'
        offset,details=hybrid(self.source,20.3,18.7,dest,probe(self.source),self.media,self.r)
        self.assertEqual(details['render_method'],'hybrid')
        self.assertEqual(details['copied_seconds'],14)
        actual=probe(dest)
        self.assertEqual(len(actual['audio_tracks']),2)
        self.assertAlmostEqual(actual['duration'],offset+18.7,delta=.12)
        first=details['head_frames'];count=round(details['copied_seconds']*10)
        copied=self.hashes(['-ss',str(details['copied_start']),'-t',str(details['copied_seconds']),'-i',self.source])
        output=self.hashes(['-i',dest,'-vf',f'select=between(n\\,{first}\\,{first+count-1})'])
        self.assertEqual(len(copied),count)
        self.assertEqual(copied,output)
        data=json.loads(self.r.run([binary('ffprobe'),'-v','error','-select_streams','v:0',
            '-show_packets','-show_entries','packet=pts_time,dts_time','-of','json',dest]))['packets']
        pts=sorted(float(p['pts_time']) for p in data);dts=[float(p['dts_time']) for p in data]
        self.assertTrue(all(b>a for a,b in zip(dts,dts[1:])))
        self.assertTrue(all(abs(b-a-.1)<.00001 for a,b in zip(pts,pts[1:])))
        self.assertLess(self.pixels(dest,offset+18.6).mean(),9)
        self.assertGreater(self.pixels(dest,offset+1)[:,1].mean(),20)
        import numpy as np
        tone=self.audio(dest,offset+1)
        dominant=np.argmax(abs(np.fft.rfft(tone)))
        self.assertAlmostEqual(dominant,500,delta=2)

    def test_start_on_keyframe_and_fractional_end_keep_the_requested_range(self):
        for start,length in ((20,20),(20.35,18.65)):
            with self.subTest(start=start):
                dest=ROOT/'tests/output'/f'hybrid-{start}.mp4'
                offset,details=hybrid(self.source,start,length,dest,probe(self.source),self.media,self.r)
                self.assertAlmostEqual(probe(dest)['duration'],offset+length,delta=.11)
                self.assertEqual(details['head_frames'],30+(0 if start==20 else 16))
                self.r.run([binary('ffmpeg'),'-v','error','-xerror','-i',dest,'-f','null','-'])

    def test_unsupported_sources_short_clips_and_lossless_use_full_render(self):
        info=probe(self.source);fake=Mock()
        with patch('smart_montage.render',return_value=3) as full:
            for modified,lossless in ((dict(info,video='av1'),False),(info,True),(dict(info,start_time=2),False)):
                offset,details=render_smart(self.source,0,20,ROOT/'tests/output/absent.mp4',modified,self.media,fake,lossless)
                self.assertEqual(offset,3)
                self.assertEqual(details['render_method'],'full')
                self.assertTrue(details['hybrid_fallback'])
            self.assertEqual(full.call_count,3)
        with self.assertRaises(Incompatible):plan(self.source,0,3,info,self.r)

    def test_failed_partial_output_is_removed_and_cancel_never_runs_full_render(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tests/output') as tmp:
            dest=Path(tmp)/'clip.mp4'
            def fail(*args):
                dest.write_bytes(b'incomplete')
                raise RuntimeError('join failed')
            with patch('smart_montage.hybrid',side_effect=fail),patch('smart_montage.render',return_value=3) as full:
                _,details=render_smart(self.source,0,20,dest,probe(self.source),self.media,self.r)
                self.assertFalse(dest.exists())
                self.assertEqual(details['render_method'],'full')
                full.assert_called_once()
            def cancel(*args):
                dest.write_bytes(b'incomplete')
                raise Cancelled('stop')
            with patch('smart_montage.hybrid',side_effect=cancel),patch('smart_montage.render') as full:
                with self.assertRaises(Cancelled):render_smart(self.source,0,20,dest,probe(self.source),self.media,self.r)
                self.assertFalse(dest.exists())
                full.assert_not_called()

    def test_open_gop_is_rejected_before_concatenation(self):
        source=self.fixture/'open-gop.mp4'
        if not source.exists():
            self.r.run([binary('ffmpeg'),'-v','error','-f','lavfi','-i','testsrc2=size=160x90:rate=10',
                '-t','16','-c:v','libx264','-x264-params','open-gop=1:keyint=20:min-keyint=20:scenecut=0',source])
        with self.assertRaises(Incompatible):
            hybrid(source,2.3,12,ROOT/'tests/output/open-gop-result.mp4',probe(source),self.media,self.r)
        with tempfile.TemporaryDirectory(dir=ROOT/'tests/output') as tmp:
            with self.assertRaisesRegex(Incompatible,'IDR'):
                check_idr(source,4,0,Path(tmp),self.r)
