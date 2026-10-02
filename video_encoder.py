"""Hardware encoding with real initialization checks and a CPU fallback."""
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


def nvidia_av1():
    return {'engine':'nvidia', 'codec':'av1_nvenc', 'pixel_format':'nv12', 'options':[
        '-c:v','av1_nvenc','-preset','p6','-tune','hq','-rc','vbr','-cq','16','-b:v','0']}


def intel_av1():
    return {'engine':'intel', 'codec':'av1_qsv', 'pixel_format':'nv12', 'options':[
        '-c:v','av1_qsv','-preset','slow','-global_quality','16','-b:v','0']}


def verify(encoder, info, runner):
    fps=str(Fraction(info.get('fps','30/1')))
    width=info['width']+(info['width']%2)
    height=info['height']+(info['height']%2)
    args=[binary('ffmpeg'),'-v','error','-nostdin','-f','lavfi','-i',
        f'color=size={width}x{height}:rate={fps}','-frames:v','8',
        *encoder['options'],'-pix_fmt',encoder.get('pixel_format','yuv420p'),'-an']
    if encoder['codec'].startswith('av1_'):
        # Verify codec and display dimensions rather than trusting ffmpeg's encoder list.
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)/'test.mp4'
            runner.run(args+[dest])
            encoded=probe(dest,runner)
            if encoded['video']!='av1' or (encoded['width'],encoded['height'])!=(width,height):
                raise RuntimeError('L’encodeur AV1 n’a pas conservé la résolution demandée.')
    else:
        runner.run(args+['-f','null','-'])


def choose(requested, info, lossless, runner):
    if requested not in {'cpu','amd','amd_av1','gpu_av1'}:
        raise ValueError('Choisis le processeur, le GPU AMD H.264 ou le GPU AV1 pour le montage.')
    fallback=cpu(lossless)
    if requested=='cpu':
        return fallback
    if lossless:
        runner.log('Le rendu sans perte de compression utilise le CPU ; les encodeurs GPU sont réservés au MP4 haute qualité.')
        return fallback
    if info.get('pix_fmt','yuv420p') != 'yuv420p':
        runner.log('Le format de couleur de cette source nécessite le CPU pour éviter une conversion en 8 bits.')
        return fallback
    candidates = [amd_av1(),nvidia_av1(),intel_av1()] if requested=='gpu_av1' else [amd_av1() if requested=='amd_av1' else amd()]
    names={'amd':'AMD AMF','nvidia':'NVIDIA NVENC','intel':'Intel Quick Sync'}
    for encoder in candidates:
        label=names[encoder['engine']]
        runner.log(f'Vérification du moteur vidéo {label}…')
        try:
            verify(encoder,info,runner)
        except Cancelled:
            raise
        except (RuntimeError,OSError) as exc:
            runner.log(f'{label} indisponible : '+str(exc)[-350:])
            continue
        codec='AV1' if encoder['codec'].startswith('av1_') else 'H.264'
        runner.log(f'GPU {label} prêt : encodage {codec} haute qualité ; les effets restent calculés sur le CPU.')
        # Keep the validated AMD decode path. Other vendors accept CPU-filtered NV12 frames.
        encoder['hardware_decode'] = encoder['engine']=='amd' and info.get('video')=='h264'
        return encoder
    fallback['fallback']='GPU AV1 indisponible' if requested=='gpu_av1' else 'AMD indisponible'
    runner.log('Aucun encodeur GPU compatible disponible : montage repris en H.264 sur le CPU.')
    return fallback
