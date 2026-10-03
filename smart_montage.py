"""Encode H.264 edit boundaries and copy the closed GOPs between them."""
from fractions import Fraction
import json
from pathlib import Path
import re
import tempfile

from core import Cancelled, binary, probe
from montage import audio_graph, render
from video_encoder import cpu


class Incompatible(ValueError):
    pass


def inspect_frames(source, start, length, index, runner, keys_only=False):
    args=[binary('ffprobe'),'-v','error','-select_streams',str(index),
          '-read_intervals',f'{max(0,start):.6f}%+{length:.6f}']
    if keys_only:
        args += ['-skip_frame','nokey']
    args += ['-show_frames','-show_entries',
             'frame=best_effort_timestamp_time,width,height,pix_fmt,interlaced_frame,sample_aspect_ratio:stream=r_frame_rate,has_b_frames,profile,level',
             '-of','json',source]
    return json.loads(runner.run(args))


def key_packet(source, when, index, runner):
    data=json.loads(runner.run([binary('ffprobe'),'-v','error','-select_streams',str(index),
        '-read_intervals',f'{when:.6f}%+1','-show_packets',
        '-show_entries','packet=pts_time,dts_time,flags','-of','json',source]))
    for packet in data.get('packets',[]):
        if 'K' in packet.get('flags','') and abs(float(packet.get('pts_time',-1))-when)<.00001:
            if 'dts_time' not in packet:
                raise Incompatible('La source ne fournit pas les DTS nécessaires aux raccords.')
            return packet
    raise Incompatible('Image clé introuvable au raccord prévu.')


def plan(source, start, duration, info, runner):
    if info['video']!='h264' or info.get('pix_fmt')!='yuv420p':
        raise Incompatible('Le montage partiel nécessite actuellement une source H.264 8 bits.')
    if abs(info.get('start_time',0))>.00001:
        raise Incompatible('La source utilise une origine temporelle décalée.')
    end=start+duration
    data=inspect_frames(source,max(0,start-1),duration+4,info['video_index'],runner,True)
    keys=sorted([f for f in data.get('frames',[]) if start-.00001<=float(f.get('best_effort_timestamp_time',-1))<end],
                key=lambda f:float(f['best_effort_timestamp_time']))
    if not keys:
        raise Incompatible('Pas d’image clé exploitable dans ce clip.')
    first=keys[0]
    head=float(first['best_effort_timestamp_time'])
    tails=[f for f in keys if float(f['best_effort_timestamp_time'])<=end-2]
    if not tails:
        raise Incompatible('Pas d’image clé avant le fondu final.')
    tail=float(tails[-1]['best_effort_timestamp_time'])
    if tail-head<3 or head-start>30 or end-tail>30:
        raise Incompatible('Les images clés sont trop espacées, ou ce clip est trop court.')
    dimensions=(first['width'],first['height'])
    if any((f['width'],f['height'])!=dimensions or f.get('pix_fmt')!='yuv420p'
           or f.get('interlaced_frame') or f.get('sample_aspect_ratio','1:1') not in {'1:1','0:1'} for f in keys):
        raise Incompatible('La résolution ou le format d’image change à l’intérieur du clip.')
    try:
        fps=Fraction(data['streams'][0]['r_frame_rate'])
    except (ValueError,ZeroDivisionError):
        raise Incompatible('Cadence inconnue pour les raccords.')
    if not 1<=float(fps)<=240:
        raise Incompatible('Cadence non prise en charge pour les raccords.')
    local=dict(info,width=dimensions[0],height=dimensions[1],fps=str(fps))
    frames=inspect_frames(source,start,head-start+2,info['video_index'],runner)['frames']
    prefix=[f for f in frames if start-.00001<=float(f.get('best_effort_timestamp_time',-1))<head-.00001]
    # The edited prefix must have a stable cadence; the copied middle retains its timestamps.
    times=[float(f['best_effort_timestamp_time']) for f in prefix]+[head]
    if any(abs((b-a)-1/float(fps))>.002 for a,b in zip(times,times[1:])):
        raise Incompatible('La cadence du début varie : montage complet pour éviter des doublons.')
    if any((f['width'],f['height'])!=dimensions for f in prefix):
        raise Incompatible('La résolution change au début du clip.')
    profile={'High':'high','Main':'main','Constrained Baseline':'baseline','Baseline':'baseline'}.get(data['streams'][0].get('profile'))
    if not profile:
        raise Incompatible('Profil H.264 non pris en charge pour les raccords.')
    first_packet=key_packet(source,head,info['video_index'],runner)
    last_packet=key_packet(source,tail,info['video_index'],runner)
    delay=float(last_packet['pts_time'])-float(last_packet['dts_time'])
    if tail-head-delay<=0:
        raise Incompatible('Horodatages incompatibles avec la copie centrale.')
    return dict(head=head,tail=tail,prefix_frames=len(prefix),info=local,fps=float(fps),
                middle_seconds=tail-head,tail_delay=delay,
                head_delay=float(first_packet['pts_time'])-float(first_packet['dts_time']),
                profile=profile,bframes=data['streams'][0].get('has_b_frames',0),
                level=data['streams'][0].get('level'))


def check_idr(source, when, index, folder, runner):
    dest=folder/'idr.h264'
    runner.run([binary('ffmpeg'),'-v','error','-y','-ss',f'{when:.6f}','-i',source,
                '-map',f'0:{index}','-an','-frames:v','1','-c:v','copy',
                '-bsf:v','h264_mp4toannexb','-f','h264',dest])
    units=re.split(b'\x00\x00\x00\x01|\x00\x00\x01',dest.read_bytes())
    first_vcl=next((unit[0]&31 for unit in units if unit and 1<=unit[0]&31<=5),None)
    if first_vcl!=5:
        raise Incompatible('Le raccord nécessite une image IDR indépendante des images précédentes.')


def match_decode_delay(part, delay, runner):
    # Preserve PTS explicitly: setts defaults to using DTS for an unspecified PTS expression.
    data=json.loads(runner.run([binary('ffprobe'),'-v','error','-select_streams','v:0',
        '-read_intervals','%+#1','-show_packets','-show_entries','packet=pts_time,dts_time',
        '-of','json',part]))['packets'][0]
    current=float(data['pts_time'])-float(data['dts_time'])
    fixed=part.with_name(part.stem+'-fixed.mp4')
    runner.run([binary('ffmpeg'),'-v','error','-y','-i',part,'-c','copy',
        '-bsf:v',f'setts=pts=PTS:dts=DTS+({current-delay:.9f})/TB',
        '-avoid_negative_ts','disabled','-video_track_timescale','1000000',fixed])
    fixed.replace(part)


def packet_times(path, runner):
    data=json.loads(runner.run([binary('ffprobe'),'-v','error','-select_streams','v:0',
        '-show_packets','-show_entries','packet=pts_time,dts_time','-of','json',path]))
    return [(float(p['pts_time']),float(p['dts_time'])) for p in data['packets']]


def hybrid(source, start, duration, dest, info, media, runner):
    decision=plan(source,start,duration,info,runner)
    local=decision['info'];fps=decision['fps'];head=decision['head'];tail=decision['tail']
    intro_frames=round(media['intro_seconds']*fps);intro=intro_frames/fps
    prefix_frames=decision['prefix_frames'];head_duration=(intro_frames+prefix_frames)/fps
    edge=cpu()
    edge['options']+=['-bf',str(decision['bframes']),'-profile:v',decision['profile'],
                      '-video_track_timescale','1000000']
    if decision['level']:
        edge['options']+=['-level:v',str(decision['level']/10)]
    with tempfile.TemporaryDirectory(prefix='montage-',dir=dest.parent) as tmp:
        folder=Path(tmp)
        for when in (head,tail):check_idr(source,when,info['video_index'],folder,runner)
        runner.log(f'Montage partiel : {decision["middle_seconds"]:.1f} s de vidéo copiée ; seuls les raccords et les effets sont encodés.')
        first=folder/'head.mp4';middle=folder/'middle.mp4';last=folder/'tail.mp4'
        render(source,start,max(head-start,1/fps),first,local,media,runner,encoder=edge,
               fade=False,video_only=True,frame_count=intro_frames+prefix_frames)
        # Stream-copy -t uses DTS. Stop before the next IDR's DTS to keep its whole GOP out.
        runner.run([binary('ffmpeg'),'-v','error','-y','-ss',f'{head:.6f}','-i',source,
            '-t',f'{decision["middle_seconds"]-decision["tail_delay"]-.000001:.6f}',
            '-map',f'0:{info["video_index"]}','-an','-c:v','copy',
            '-video_track_timescale','1000000',middle])
        tail_duration=start+duration-tail
        runner.run([binary('ffmpeg'),'-v','error','-y','-ss',f'{tail:.6f}','-i',source,
            '-t',f'{tail_duration:.6f}','-map',f'0:{info["video_index"]}','-an',
            '-vf',f'setpts=PTS-STARTPTS,fade=t=out:st={max(0,tail_duration-2):.6f}:d=2',
            *edge['options'],'-pix_fmt','yuv420p','-r',local['fps'],last])
        match_decode_delay(first,decision['head_delay'],runner)
        match_decode_delay(last,decision['tail_delay'],runner)
        listing=folder/'parts.txt'
        listing.write_text(f"file 'head.mp4'\nduration {head_duration:.9f}\nfile 'middle.mp4'\nduration {decision['middle_seconds']:.9f}\nfile 'tail.mp4'\n",encoding='utf-8')
        joined=folder/'joined.mp4'
        runner.run([binary('ffmpeg'),'-v','error','-y','-f','concat','-safe','0','-i',listing,
                    '-map','0:v:0','-c:v','copy','-video_track_timescale','1000000',joined])
        tracks,sounds=audio_graph(info,media,duration,intro,1,2)
        args=[binary('ffmpeg'),'-v','error','-y','-i',joined,'-ss',f'{start:.6f}',
              '-t',f'{duration:.6f}','-i',source,'-stream_loop','-1','-i',media['screen']]
        if sounds:args+=['-filter_complex',';'.join(sounds)]
        args+=['-map','0:v:0']
        for i,track in enumerate(tracks):
            args+=['-map',f'[a{i}]',f'-metadata:s:a:{i}','language='+track.get('language','und'),
                   f'-metadata:s:a:{i}','title='+track.get('title',f'Audio {i+1}')]
        runner.run(args+['-c:v','copy','-c:a','aac','-b:a','320k',
                        '-t',f'{intro+duration:.6f}','-video_track_timescale','1000000',dest])
        copied=packet_times(middle,runner)
        output=packet_times(dest,runner)
        after=output[intro_frames+prefix_frames:intro_frames+prefix_frames+len(copied)]
        if not copied or len(after)!=len(copied) or any(
            abs(new_value-head_duration-original_value)>.00001
            for original,joined_packet in zip(copied,after)
            for original_value,new_value in zip(original,joined_packet)):
            raise Incompatible('Les raccords ont modifié les horodatages de la vidéo centrale.')
        if any(b[1]<=a[1] for a,b in zip(output,output[1:])):
            raise Incompatible('Les horodatages du montage ne sont pas continus.')
        actual=probe(dest,runner)
        if actual['video']!='h264' or (actual['width'],actual['height'])!=(local['width'],local['height']) or len(actual['audio_tracks'])!=len(tracks) or abs(actual['duration']-(intro+duration))>max(.1,2/fps):
            raise Incompatible('Le contrôle du montage partiel a échoué.')
        # Decode each junction, including the in-band SPS/PPS update, before advertising success.
        for when in (head_duration,head_duration+decision['middle_seconds']):
            runner.run([binary('ffmpeg'),'-v','error','-xerror','-ss',f'{max(0,when-1):.6f}',
                        '-i',dest,'-t','3','-map','0:v:0','-an','-f','null','-'])
    return intro,{'render_method':'hybrid','video_encoder':'cpu','video_codec':'libx264',
                  'copied_seconds':decision['middle_seconds'],
                  'encoded_video_seconds':head_duration+tail_duration,
                  'head_frames':intro_frames+prefix_frames,'copied_start':head,'copied_end':tail}


def render_smart(source, start, duration, dest, info, media, runner, lossless=False, encoder=None):
    try:
        if lossless:raise Incompatible('Le rendu sans perte utilise le montage complet.')
        return hybrid(source,start,duration,dest,info,media,runner)
    except Cancelled:
        dest.unlink(missing_ok=True)
        raise
    except (Incompatible,RuntimeError,OSError) as exc:
        dest.unlink(missing_ok=True)
        reason=str(exc)[-500:]
        runner.log('Montage complet pour ce clip : '+reason)
        offset=render(source,start,duration,dest,info,media,runner,lossless,encoder=encoder)
        used=encoder if encoder is not None and not lossless else cpu(lossless)
        return offset,{'render_method':'full','video_encoder':used['engine'],
                       'video_codec':used['codec'],'hybrid_fallback':reason}
