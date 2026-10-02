"""Optional AMD hardware encoding; preserve the CPU reference and its lossless mode."""
from fractions import Fraction

from core import Cancelled, binary


def cpu(lossless=False):
    return {'engine':'cpu', 'codec':'libx264', 'options':[
        '-c:v','libx264','-preset','fast','-crf','0' if lossless else '16']}


def amd():
    # CQP and CRF scales are not equivalent. Use a conservative low QP for game footage.
    return {'engine':'amd', 'codec':'h264_amf', 'options':[
        '-c:v','h264_amf','-usage','high_quality','-quality','quality','-rc','cqp',
        '-qp_i','20','-qp_p','20','-qp_b','20']}


def choose(requested, info, lossless, runner):
    if requested not in {'cpu','amd'}:
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
    encoder=amd()
    fps=str(Fraction(info.get('fps','30/1')))
    width=info['width']+(info['width']%2)
    height=info['height']+(info['height']%2)
    runner.log('Vérification du moteur vidéo AMD AMF…')
    try:
        # Test real initialization, not just the presence of an encoder in ffmpeg -encoders.
        runner.run([binary('ffmpeg'),'-v','error','-nostdin','-f','lavfi','-i',
            f'color=size={width}x{height}:rate={fps}','-frames:v','8',
            *encoder['options'],'-pix_fmt','yuv420p','-an','-f','null','-'])
    except Cancelled:
        raise
    except (RuntimeError,OSError) as exc:
        runner.log('GPU AMD indisponible : montage repris sur le CPU. '+str(exc)[-350:])
        fallback['fallback']='AMD indisponible'
        return fallback
    runner.log('GPU AMD prêt : encodage H.264 haute qualité ; les effets restent calculés sur le CPU.')
    # D3D11VA decoding was validated on H.264 VODs with identical encoded output.
    encoder['hardware_decode'] = info.get('video') == 'h264'
    return encoder
