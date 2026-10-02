import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import ROOT, Runner, Cancelled, binary, probe
from montage import assets, render
from pipeline import process, load_project
from smart_cuts import silence_candidates, adjust_boundaries, speech_window
from video_encoder import amd, amd_av1


class MontageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = Runner()
        cls.fixture = ROOT/'tests'/'fixtures'/'montage'
        cls.fixture.mkdir(parents=True,exist_ok=True)
        cls.source = cls.fixture/'source.mp4'
        if not cls.source.exists():
            cls.r.run([binary('ffmpeg'),'-v','error','-f','lavfi','-i','testsrc2=size=160x90:rate=10',
                '-f','lavfi','-i','sine=frequency=500:sample_rate=48000','-t','130',
                '-map','0:v','-map','1:a','-map','1:a','-c:v','libx264','-preset','ultrafast',
                '-g','20','-bf','2','-c:a','aac',cls.source])
        screen = cls.fixture/'Starting Screen.mp4'
        if not screen.exists():
            cls.r.run([binary('ffmpeg'),'-v','error','-f','lavfi','-i','color=c=red:s=160x90:r=10',
                '-f','lavfi','-i','sine=frequency=200:sample_rate=48000','-t','4',
                '-c:v','libx264','-c:a','aac',screen])
        stinger = cls.fixture/'Stinger.webm'
        if not stinger.exists():
            cls.r.run([binary('ffmpeg'),'-v','error','-f','lavfi','-i',
                'color=c=blue:s=160x90:r=10,format=yuva420p,fade=t=in:st=0:d=0.3:alpha=1,fade=t=out:st=0.7:d=0.3:alpha=1',
                '-t','1','-c:v','libvpx-vp9','-pix_fmt','yuva420p','-auto-alt-ref','0',stinger])

    def pixels(self,file,time):
        import numpy as np
        # Runner returns text; use a temporary raw file to retain all pixel values.
        with tempfile.TemporaryDirectory(dir=ROOT/'tests'/'output') as tmp:
            raw=Path(tmp)/'pixels.raw'
            self.r.run([binary('ffmpeg'),'-v','error','-ss',str(time),'-i',file,
                        '-frames:v','1','-f','rawvideo','-pix_fmt','rgb24',raw])
            return np.frombuffer(raw.read_bytes(),dtype=np.uint8).reshape(-1,3)

    def audio(self,file,time):
        import numpy as np
        with tempfile.TemporaryDirectory(dir=ROOT/'tests'/'output') as tmp:
            raw=Path(tmp)/'audio.raw'
            self.r.run([binary('ffmpeg'),'-v','error','-ss',str(time),'-i',file,'-t','1',
                        '-map','0:a:0','-f','f32le','-c:a','pcm_f32le',raw])
            return np.frombuffer(raw.read_bytes(),dtype=np.float32)

    def test_real_transparent_stinger_fade_and_all_audio_tracks(self):
        dest=ROOT/'tests'/'output'/'render-test.mkv'
        media=assets(self.fixture,self.r)
        self.assertTrue(media['stinger_info']['alpha'])
        offset=render(self.source,120.3,9.7,dest,probe(self.source),media,self.r,lossless=True)
        info=probe(dest)
        self.assertAlmostEqual(info['duration'],offset+9.7,delta=.11)
        self.assertEqual(info['audio_codecs'],['flac','flac'])
        self.assertEqual((info['width'],info['height'],info['fps']),(160,90,'10/1'))
        intro=self.pixels(dest,1)
        self.assertGreater(intro[:,0].mean(),240)
        self.assertLess(intro[:,1].mean(),10)
        opaque=self.pixels(dest,2.5)
        self.assertGreater(opaque[:,2].mean(),230)
        self.assertLess(opaque[:,0].mean(),15)
        # Last gameplay frame almost black; gameplay starts without losing the first frame.
        self.assertLess(self.pixels(dest,offset+9.6).mean(),9)
        import numpy as np
        before=self.pixels(self.source,120.3)
        after=self.pixels(dest,offset)
        self.assertTrue(np.array_equal(before,after),'Lossless gameplay frame changed before fade')
        source_audio=self.audio(self.source,121.3)
        rendered_audio=self.audio(dest,offset+1)
        self.assertEqual(len(source_audio),len(rendered_audio))
        self.assertTrue(np.allclose(source_audio,rendered_audio,atol=1e-6),'Gameplay audio shifted or changed')

    def test_complete_pipeline_folders_ranges_and_content_only_frames(self):
        with patch('smart_cuts.speech_window',return_value=[{'start':0,'end':30},{'start':31,'end':64}]):
            result=process({'source':str(self.source),'start':'0.3','minutes':1,'game':'Palworld',
                'output':str(ROOT/'tests'/'output'),'ai':False,'montage':True,
                'montage_directory':str(self.fixture),'render_quality':'high'},self.r,lambda _:None)
        clips=result['clips']
        self.assertEqual(len(clips),2)
        self.assertEqual([Path(c['directory']).name for c in clips],['Clip 001','Clip 002'])
        self.assertEqual(clips[0]['source_end'],clips[1]['source_start'])
        self.assertAlmostEqual(clips[-1]['source_end'],probe(self.source)['duration'],delta=.001)
        for clip in clips:
            self.assertEqual(Path(clip['file']).parent,Path(clip['directory']))
            self.assertTrue(Path(clip['thumbnail']).is_file())
            self.assertIn('[Palworld #',Path(clip['file']).name)
            self.assertAlmostEqual(clip['duration'],clip['content_duration']+clip['content_offset'],delta=.12)
            # Sampled thumbnail frames must show gameplay, not the red intro.
            from PIL import Image
            import numpy as np
            frame=np.asarray(Image.open(Path(clip['directory'])/'image_01.jpg'))
            self.assertGreater(frame[:,:,1].mean(),20)
        root,loaded=load_project(Path(clips[0]['directory']).parent/'projet.json')
        self.assertEqual(len(loaded['clips']),2)
        self.assertTrue((root/'tags.txt').is_file())

    def test_pause_selection_consecutive_cuts_and_fallback(self):
        speech=[{'start':0,'end':29},{'start':31,'end':64}]
        self.assertEqual(silence_candidates(speech,64,30,0,64)[0],30)
        self.assertEqual(silence_candidates([{'start':0,'end':64}],64,30,0,64),[])
        info={'audio':True,'video_index':0,'start_time':0}
        with patch('smart_cuts.speech_window',return_value=speech):
            cuts,decisions=adjust_boundaries(self.source,0,190,[60,120],info,self.r)
        self.assertTrue(all(abs(p-n)<=30 for p,n in zip(cuts,[60,120])))
        self.assertTrue(all(30<=b-a<=90 for a,b in zip([0]+cuts,cuts)))
        self.assertTrue(all(d['reason']=='voice_pause' for d in decisions))
        with patch('smart_cuts.speech_window',return_value=[{'start':0,'end':1000}]):
            cuts,decisions=adjust_boundaries(self.source,0,130,[60],info,self.r)
        self.assertEqual(cuts,[60])
        self.assertEqual(decisions[0]['reason'],'no_pause')
        self.assertEqual(adjust_boundaries(self.source,0,130,[60],{'audio':False},self.r),([60],[]))

    def test_copy_requires_keyframe_inside_the_pause(self):
        info={'audio':True,'video_index':0,'start_time':0}
        with patch('smart_cuts.speech_window',return_value=[{'start':0,'end':30},{'start':32,'end':64}]), \
             patch('smart_cuts.keyframes',return_value=[57,59]):
            cuts,decisions=adjust_boundaries(self.source,0,130,[60],info,self.r,exact=False)
        self.assertEqual(cuts,[59])
        self.assertEqual(decisions[0]['reason'],'voice_pause_keyframe')

    def test_local_vad_runs_without_whisper_or_online(self):
        # Synthetic tone is not human speech; real packaged ONNX VAD runs locally.
        self.assertEqual(speech_window(self.source,0,2,self.r),[])

    def test_cancelled_render_keeps_finished_clips_loadable(self):
        updates=[]
        def interrupted(*args,**kwargs):
            if Path(args[3]).parent.name=='Clip 002':
                raise Cancelled('test stop')
            return render(*args,**kwargs)
        with patch('pipeline.render',side_effect=interrupted):
            with self.assertRaises(Cancelled):
                process({'source':str(self.source),'start':'0','minutes':1,'smart_cuts':False,
                    'output':str(ROOT/'tests'/'output'),'ai':False,'montage':True,
                    'montage_directory':str(self.fixture)},self.r,updates.append)
        project=next(u['project'] for u in reversed(updates) if 'project' in u)
        _,saved=load_project(project)
        self.assertEqual(saved['status'],'interrupted')
        self.assertEqual(len(saved['clips']),1)
        self.assertTrue(Path(saved['clips'][0]['file']).is_file())

    def test_old_project_loads_and_outside_folder_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tests'/'output') as tmp:
            root=Path(tmp); video=root/'old.mp4'; video.write_bytes(b'video')
            folder=root/'clip_001';folder.mkdir()
            data={'clips':[{'number':1,'file':str(video),'directory':str(folder)}]}
            project=root/'projet.json';project.write_text(json.dumps(data))
            self.assertEqual(len(load_project(project)[1]['clips']),1)
            data['clips'][0]['file']=str(self.source)
            project.write_text(json.dumps(data))
            with self.assertRaises(ValueError):load_project(project)

    def test_silent_gameplay_preserves_starting_screen_audio(self):
        silent=self.fixture/'silent.mp4'
        if not silent.exists():
            self.r.run([binary('ffmpeg'),'-v','error','-i',self.source,'-t','4','-map','0:v:0','-c','copy',silent])
        dest=ROOT/'tests'/'output'/'silent-with-intro.mp4'
        media=assets(self.fixture,self.r)
        offset=render(silent,0,4,dest,probe(silent),media,self.r)
        self.assertEqual(probe(dest)['audio_codecs'],['aac'])
        self.assertGreater(abs(self.audio(dest,1)).max(),.01)
        self.assertLess(abs(self.audio(dest,offset+1)).max(),1e-6)

    def test_failed_gpu_render_retries_cpu_without_losing_completed_content(self):
        dest=ROOT/'tests'/'output'/'gpu-retry.mp4'
        encoder=amd()
        encoder['hardware_decode']=True
        real_run=self.r.run
        attempts=[]
        def run(args):
            if '-filter_complex' in args:
                attempts.append(args)
                if 'h264_amf' in args:
                    dest.write_bytes(b'incomplete gpu output')
                    raise RuntimeError('GPU driver failure')
            return real_run(args)
        with patch.object(self.r,'run',side_effect=run):
            offset=render(self.source,120,10,dest,probe(self.source),assets(self.fixture,self.r),self.r,encoder=encoder)
        self.assertEqual(encoder['engine'],'cpu')
        self.assertEqual(len(attempts),2)
        self.assertNotIn('h264_amf',attempts[1])
        self.assertNotIn('-hwaccel',attempts[1])
        self.assertIn('libvpx-vp9',attempts[1])
        self.assertAlmostEqual(probe(dest)['duration'],offset+10,delta=.12)

    def test_av1_failure_restores_cpu_pixel_format_and_all_tracks(self):
        dest=ROOT/'tests'/'output'/'av1-retry.mp4'
        encoder=amd_av1();encoder['hardware_decode']=True
        real_run=self.r.run;attempts=[]
        def run(args):
            if '-filter_complex' in args:
                attempts.append(list(args))
                if 'av1_amf' in args:
                    raise RuntimeError('AV1 driver failure')
            return real_run(args)
        with patch.object(self.r,'run',side_effect=run):
            render(self.source,120,10,dest,probe(self.source),assets(self.fixture,self.r),self.r,encoder=encoder)
        self.assertEqual(encoder['engine'],'cpu')
        self.assertIn('nv12',attempts[0])
        self.assertNotIn('nv12',attempts[1])
        self.assertNotIn('-hwaccel',attempts[1])
        self.assertNotIn('-preanalysis',attempts[1])
        self.assertEqual(probe(dest)['video'],'h264')
        self.assertEqual(len(probe(dest)['audio_tracks']),2)


if __name__=='__main__':
    unittest.main()
