from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core import Cancelled
from video_encoder import choose, cpu, amd, amd_av1


class VideoEncoderTests(unittest.TestCase):
    def setUp(self):
        self.info={'width':1920,'height':1080,'fps':'60/1','pix_fmt':'yuv420p','video':'h264'}
        self.runner=Mock()

    def test_cpu_lossless_and_non_8bit_do_not_attempt_hardware(self):
        self.assertEqual(choose('cpu',self.info,False,self.runner)['engine'],'cpu')
        chosen=choose('amd',self.info,True,self.runner)
        self.assertEqual(chosen['options'],cpu(True)['options'])
        chosen=choose('amd',dict(self.info,pix_fmt='yuv420p10le'),False,self.runner)
        self.assertEqual(chosen['engine'],'cpu')
        self.runner.run.assert_not_called()

    def test_gpu_initialization_uses_source_resolution_and_quality_options(self):
        chosen=choose('amd',self.info,False,self.runner)
        self.assertEqual(chosen['codec'],'h264_amf')
        self.assertTrue(chosen['hardware_decode'])
        args=self.runner.run.call_args.args[0]
        self.assertIn('color=size=1920x1080:rate=60',args)
        self.assertIn('quality',args)
        self.assertEqual(args[args.index('-rc')+1],'cqp')
        self.assertNotIn('-crf',args)

    def test_missing_encoder_or_driver_falls_back_to_original_cpu_quality(self):
        self.runner.run.side_effect=RuntimeError('AMD driver unavailable')
        chosen=choose('amd',self.info,False,self.runner)
        self.assertEqual(chosen['options'],cpu()['options'])
        self.assertEqual(chosen['fallback'],'AMD indisponible')

    def test_cancel_never_starts_cpu_retry(self):
        self.runner.run.side_effect=Cancelled('cancelled')
        with self.assertRaises(Cancelled):choose('amd',self.info,False,self.runner)
        self.assertEqual(self.runner.run.call_count,1)
        with self.assertRaises(ValueError):choose('unknown',self.info,False,self.runner)

    def test_av1_uses_its_own_quality_scale_and_checks_mp4_dimensions(self):
        with patch('video_encoder.probe',return_value={'video':'av1','width':1920,'height':1080}) as inspection:
            chosen=choose('amd_av1',self.info,False,self.runner)
        self.assertEqual(chosen['codec'],'av1_amf')
        self.assertEqual(chosen['pixel_format'],'nv12')
        self.assertTrue(chosen['hardware_decode'])
        args=self.runner.run.call_args.args[0]
        self.assertEqual(args[args.index('-qp_i')+1], '40')
        self.assertEqual(args[args.index('-preanalysis')+1], 'false')
        self.assertEqual(Path(args[-1]).suffix,'.mp4')
        inspection.assert_called_once()

    def test_av1_unexpected_padding_falls_back_without_resizing_source(self):
        with patch('video_encoder.probe',return_value={'video':'av1','width':1920,'height':1082}):
            chosen=choose('amd_av1',self.info,False,self.runner)
        self.assertEqual(chosen['codec'],'libx264')
        self.assertEqual(chosen['options'],cpu()['options'])
        self.assertEqual(choose('amd_av1',self.info,True,self.runner)['options'],cpu(True)['options'])

    def test_auto_av1_uses_first_working_vendor_and_stops_detection(self):
        for failures,engine,codec in [(0,'amd','av1_amf'),(1,'nvidia','av1_nvenc'),(2,'intel','av1_qsv')]:
            with self.subTest(engine=engine):
                runner=Mock();runner.run.side_effect=[RuntimeError('not supported')]*failures+[None]
                with patch('video_encoder.probe',return_value={'video':'av1','width':1920,'height':1080}):
                    chosen=choose('gpu_av1',self.info,False,runner)
                self.assertEqual(chosen['engine'],engine)
                self.assertEqual(chosen['codec'],codec)
                self.assertEqual(runner.run.call_count,failures+1)
                self.assertEqual(chosen['hardware_decode'],engine=='amd')

    def test_auto_av1_unsupported_or_padded_devices_then_cpu(self):
        self.runner.run.side_effect=RuntimeError('encoder or driver missing')
        chosen=choose('gpu_av1',self.info,False,self.runner)
        self.assertEqual(chosen['options'],cpu()['options'])
        self.assertEqual(self.runner.run.call_count,3)
        self.assertEqual(chosen['fallback'],'GPU AV1 indisponible')
        self.runner.reset_mock(side_effect=True)
        with patch('video_encoder.probe',side_effect=[
            {'video':'av1','width':1920,'height':1082},
            {'video':'av1','width':1920,'height':1080}]):
            self.assertEqual(choose('gpu_av1',self.info,False,self.runner)['engine'],'nvidia')

    def test_auto_av1_cancellation_and_quality_guards_do_not_try_next_vendor(self):
        self.runner.run.side_effect=Cancelled('cancelled')
        with self.assertRaises(Cancelled):choose('gpu_av1',self.info,False,self.runner)
        self.assertEqual(self.runner.run.call_count,1)
        self.runner.reset_mock()
        self.assertEqual(choose('gpu_av1',self.info,True,self.runner)['options'],cpu(True)['options'])
        self.assertEqual(choose('gpu_av1',dict(self.info,pix_fmt='yuv420p10le'),False,self.runner)['engine'],'cpu')
        self.runner.run.assert_not_called()


if __name__=='__main__':
    unittest.main()
