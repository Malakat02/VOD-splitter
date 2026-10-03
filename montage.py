"""Render a transparent stinger and a closing fade, keeping all gameplay and audio tracks."""
from fractions import Fraction
from pathlib import Path
import tempfile

from core import ROOT, Runner, binary, probe
from video_encoder import cpu


def assets(directory=None, runner=None):
    runner = runner or Runner()
    root = Path(directory or ROOT/'Montage')
    screen, stinger = root/'Starting Screen.mp4', root/'Stinger.webm'
    if not screen.is_file() or not stinger.is_file():
        raise ValueError('Montage : ajoute Starting Screen.mp4 et Stinger.webm au dossier Montage, '
                         'ou décoche le montage pour copier les pistes sans réencodage.')
    screen_info, stinger_info = probe(screen, runner), probe(stinger, runner)
    if screen_info['duration'] < 2:
        raise ValueError('Le starting screen doit durer au moins deux secondes.')
    if stinger_info['duration'] > 30:
        raise ValueError('Le stinger dépasse 30 secondes : vérifie le fichier de transition.')
    # Decode VP9 with libvpx: the native decoder does not expose WebM alpha.
    switch = stinger_info['duration']/2
    if stinger_info.get('alpha'):
        import numpy as np
        with tempfile.TemporaryDirectory() as tmp:
            alpha = Path(tmp)/'alpha.raw'
            runner.run([binary('ffmpeg'), '-v', 'error', '-nostdin', '-c:v', 'libvpx-vp9',
                        '-i', stinger, '-vf', 'alphaextract,scale=64:36',
                        '-f', 'rawvideo', '-pix_fmt', 'gray', alpha])
            frames = np.frombuffer(alpha.read_bytes(), dtype=np.uint8).reshape(-1,36,64)
            # Prefer the middle fully opaque frame; hide the background switch under the stinger.
            opaque = np.where(frames.min(axis=(1,2)) >= 250)[0]
            if len(opaque):
                switch = float(opaque[len(opaque)//2])/float(Fraction(stinger_info['fps']))
            else:
                runner.log('Le stinger ne couvre jamais toute l’image ; un changement de fond peut rester visible.')
    return {'screen': screen, 'stinger': stinger, 'screen_info': screen_info,
            'stinger_info': stinger_info, 'switch': switch,
            'intro_seconds': 2+stinger_info['duration']}


def audio_graph(info, media, duration, intro, source_input=0, screen_input=1):
    tracks = info.get('audio_tracks', [])
    original_audio = bool(tracks)
    if not tracks and media['screen_info']['audio']:
        tracks = media['screen_info']['audio_tracks'][:1]
    graph=[]
    for i, track in enumerate(tracks):
        rate, layout = int(track.get('sample_rate',48000)), track.get('channel_layout') or f'{track["channels"]}c'
        form = f'aresample={rate},aformat=sample_fmts=fltp:sample_rates={rate}:channel_layouts={layout}'
        if media['screen_info']['audio']:
            graph.append(f'[{screen_input}:a:0]atrim=duration={intro:.6f},asetpts=PTS-STARTPTS,{form},afade=t=out:st={max(0,intro-.25):.6f}:d=0.25[ia{i}]')
        else:
            graph.append(f'anullsrc=r={rate}:cl={layout},atrim=duration={intro:.6f}[ia{i}]')
        if original_audio:
            graph.append(f'[{source_input}:a:{i}]atrim=duration={duration:.6f},asetpts=PTS-STARTPTS,{form},apad,atrim=duration={duration:.6f}[ga{i}]')
        else:
            graph.append(f'anullsrc=r={rate}:cl={layout},atrim=duration={duration:.6f}[ga{i}]')
        graph.append(f'[ia{i}][ga{i}]concat=n=2:v=0:a=1[a{i}]')
    return tracks,graph


def render(source, start, duration, dest, info, media, runner, lossless=False, encoder=None,
           *, fade=True, video_only=False, frame_count=None):
    encoder = encoder if encoder is not None and not lossless else cpu(lossless)
    fps = float(Fraction(info.get('fps', '30/1')))
    fps_string = info.get('fps', '30/1')
    # Round intro to whole frames. Gameplay duration remains separate for five-minute summaries.
    before = round((2+media['switch'])*fps)/fps
    intro = round(media['intro_seconds']*fps)/fps
    reveal = intro-before
    total = intro+duration
    w, h = info['width']+(info['width']%2), info['height']+(info['height']%2)
    scale = f'scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps_string}'
    args = [binary('ffmpeg'), '-v', 'warning', '-nostdin', '-y', '-ss', f'{start:.6f}',
            '-t', f'{duration:.6f}', '-i', source, '-stream_loop', '-1', '-i', media['screen']]
    if encoder.get('hardware_decode'):
        position=args.index('-i')
        args[position:position]=['-hwaccel','d3d11va']
    if media['stinger_info'].get('alpha'):
        args += ['-c:v', 'libvpx-vp9']
    args += ['-i', media['stinger']]
    # Show the first gameplay frame beneath the revealing transition. Its audio and full motion
    # begin after the stinger finishes, so the transition never hides the start of a sentence.
    graph = [f'[0:{info["video_index"]}]setpts=PTS-STARTPTS,{scale},split=2[game][first]',
        f'[first]trim=end_frame=1,loop=loop=-1:size=1:start=0,setpts=N/({fps:.9f}*TB),fps={fps_string},trim=duration={reveal:.6f}[freeze]',
        f'[1:{media["screen_info"]["video_index"]}]setpts=PTS-STARTPTS,{scale},trim=duration={before:.6f}[screen]',
        '[screen][freeze]concat=n=2:v=1:a=0[background]',
        f'[2:{media["stinger_info"]["video_index"]}]setpts=PTS-STARTPTS,{scale},format=yuva420p,setpts=PTS+2/TB[stinger]',
        '[background][stinger]overlay=eof_action=pass:repeatlast=0:format=auto[intro]',
        '[intro][game]concat=n=2:v=1:a=0[joined]',
        (f'[joined]fade=t=out:st={max(intro,total-2):.6f}:d={min(2,duration):.6f}[video]' if fade else '[joined]null[video]')]
    tracks, sounds = ([],[]) if video_only else audio_graph(info,media,duration,intro)
    graph += sounds
    args += ['-filter_complex_threads', '2', '-filter_complex', ';'.join(graph), '-map', '[video]']
    for i, track in enumerate(tracks):
        args += ['-map', f'[a{i}]', f'-metadata:s:a:{i}', 'language='+track.get('language','und'),
                 f'-metadata:s:a:{i}', 'title='+track.get('title',f'Audio {i+1}')]
    pixel_format = info.get('pix_fmt', 'yuv420p')
    # libx264 supports these formats; reject silent HDR/high-bit-depth conversion.
    if pixel_format not in {'yuv420p','yuv420p10le','yuv422p','yuv422p10le','yuv444p','yuv444p10le'}:
        raise ValueError(f'Format vidéo {pixel_format} non pris en charge pour le montage. Utilise le mode sans montage.')
    encoding_index = len(args)
    args += encoder['options'] + ['-pix_fmt', encoder.get('pixel_format',pixel_format)]
    if tracks:
        args += ['-c:a', 'flac' if lossless else 'aac']
        if not lossless:
            args += ['-b:a','320k']
    if frame_count is not None:
        args += ['-frames:v',str(frame_count)]
    args += ['-t', f'{total:.6f}', dest]
    try:
        try:
            runner.run(args)
        except RuntimeError:
            if encoder['engine'] == 'cpu':
                raise
            dest.unlink(missing_ok=True)
            runner.log('Échec du rendu GPU : nouvelle tentative de ce clip sur le CPU, avec la qualité habituelle.')
            length=len(encoder['options'])
            if encoder.get('hardware_decode'):
                position=args.index('-hwaccel')
                del args[position:position+2]
                encoding_index-=2
            encoder.clear()
            encoder.update(cpu())
            encoder['fallback']='Échec du rendu GPU'
            args[encoding_index:encoding_index+length]=encoder['options']
            args[args.index('-pix_fmt',encoding_index)+1]=pixel_format
            runner.run(args)
    except BaseException:
        # An incomplete encode is never advertised as a finished clip.
        dest.unlink(missing_ok=True)
        raise
    return intro
