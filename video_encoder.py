"""Optional AMD hardware encoding; preserve the CPU reference and its lossless mode."""
from fractions import Fraction
from pathlib import Path
import tempfile

from core import Cancelled, binary, probe


def cpu(lossless=False):
    return {'engine':'cpu', 'codec':'libx264', 'options':[
        '-c:v','libx264','-preset','fast','-crf','0' if lossless else '16']}


def amd():
    # CQP and CRF scales are not equivalent. Use a conservative low QP for game footage.
    return {'engine':'amd', 'codec':'h264_amf', 'options':[
        '-c:v','h264_amf','-usage','high_quality','-quality','quality','-rc','cqp',
        '-qp_i','20','-qp_p','20','-qp_b','20']}


def amd_av1():
    # AV1 uses its own quantizer scale. Explicitly disable analysis for fixed quantization;
    # on the tested driver the automatic high-quality analysis severely reduced fidelity.
    return {'engine':'amd', 'codec':'av1_amf', 'pixel_format':'nv12', 'options':[
        '-c:v','av1_amf','-usage','transcoding','-quality','quality','-rc','cqp',
        '-qp_i','40','-qp_p','40','-preanalysis','false','-preencode','false']}


def choose(requested, info, lossless, runner):
    if requested not in {'cpu','amd','amd_av1'}:
        raise ValueError('Choisis le processeur ou le GPU AMD pour le montage.')
    fallback=cpu(lossless)
    if requested=='cpu':
        return fallback
    if lossless:
        runner.log('Le rendu sans perte de compression utilise le CPU ; AMD AMF est réservé au MP4 haute qualité.')
        return fallback
    if info.get('pix_fmt','yuv420p') != 'yuv420p':
        runner.log('Le format de couleur de cette source nécessite le CPU pour éviter une conversion en 8 bits.')
        return fallback
    encoder=amd_av1() if requested=='amd_av1' else amd()
    label='AV1' if requested=='amd_av1' else 'H.264'
    fps=str(Fraction(info.get('fps','30/1')))
    width=info['width']+(info['width']%2)
    height=info['height']+(info['height']%2)
    runner.log('Vérification du moteur vidéo AMD AMF…')
    try:
        # Test real initialization, not just the presence of an encoder in ffmpeg -encoders.
        args=[binary('ffmpeg'),'-v','error','-nostdin','-f','lavfi','-i',
            f'color=size={width}x{height}:rate={fps}','-frames:v','8',
            *encoder['options'],'-pix_fmt',encoder.get('pixel_format','yuv420p'),'-an']
        if requested=='amd_av1':
            # Some driver/SDK versions pad AV1 frames. Check the MP4 display dimensions
            # before committing to rendering a full episode at an altered resolution.
            with tempfile.TemporaryDirectory() as tmp:
                dest=Path(tmp)/'test.mp4'
                runner.run(args+[dest])
                encoded=probe(dest,runner)
                if encoded['video']!='av1' or (encoded['width'],encoded['height'])!=(width,height):
                    raise RuntimeError('L’encodeur AV1 n’a pas conservé la résolution demandée.')
        else:
            runner.run(args+['-f','null','-'])
    except Cancelled:
        raise
    except (RuntimeError,OSError) as exc:
        runner.log(f'GPU AMD {label} indisponible : montage repris en H.264 sur le CPU. '+str(exc)[-350:])
        fallback['fallback']='AMD indisponible'
        return fallback
    runner.log(f'GPU AMD prêt : encodage {label} haute qualité ; les effets restent calculés sur le CPU.')
    # D3D11VA decoding was validated on H.264 VODs with identical encoded output.
    encoder['hardware_decode'] = info.get('video') == 'h264'
    return encoder
