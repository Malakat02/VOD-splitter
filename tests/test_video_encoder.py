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


if __name__=='__main__':
    unittest.main()
