"""Bounded, local speech detection around planned cuts; no transcription or API calls."""
import json
import math
from fractions import Fraction
from pathlib import Path
import tempfile

from core import binary


def silence_candidates(speech, length, nominal, low, high, minimum=.5, step=0, origin=0):
    """Pick the closest point with 250 ms clearance on either side of speech."""
    gaps, end = [], 0.0
    for segment in sorted(speech, key=lambda s: s['start']):
        begin = max(end, float(segment['start']))
        if begin-end >= minimum:
            gaps.append((end, begin))
        end = max(end, float(segment['end']))
    if length-end >= minimum:
        gaps.append((end, length))
    candidates = []
    for a, b in gaps:
        left, right = max(low, a+.25), min(high, b-.25)
        if step:
            left = math.ceil((left+origin)/step-1e-8)*step-origin
            right = math.floor((right+origin)/step+1e-8)*step-origin
        if left <= right:
            point = round((nominal+origin)/step)*step-origin if step else nominal
            candidates.append(min(right, max(left, point)))
    return sorted(candidates, key=lambda point: abs(point-nominal))


def speech_window(source, start, length, runner):
    from faster_whisper.audio import decode_audio
    from faster_whisper.vad import get_speech_timestamps, VadOptions
    with tempfile.TemporaryDirectory() as tmp:
        audio = Path(tmp)/'pause.wav'
        runner.run([binary('ffmpeg'), '-v', 'error', '-nostdin', '-ss', f'{start:.6f}',
                    '-i', source, '-t', f'{length:.6f}', '-map', '0:a:0',
                    '-ac', '1', '-ar', '16000', audio])
        samples = decode_audio(str(audio))
        runner.check()
        chunks = get_speech_timestamps(samples, VadOptions(min_speech_duration_ms=100,
                      min_silence_duration_ms=500, speech_pad_ms=150))
        runner.check()
        return [{'start': s['start']/16000, 'end': s['end']/16000} for s in chunks]


def keyframes(source, start, length, info, runner):
    raw = runner.run([binary('ffprobe'), '-v', 'error', '-select_streams', str(info['video_index']),
        '-skip_frame', 'nokey', '-read_intervals', f'{start:.6f}%+{length:.6f}',
        '-show_frames', '-show_entries', 'frame=best_effort_timestamp_time', '-of', 'json', source])
    return [float(f['best_effort_timestamp_time'])-info['start_time']
            for f in json.loads(raw).get('frames', []) if 'best_effort_timestamp_time' in f]


def adjust_boundaries(source, start, duration, boundaries, info, runner, exact=True):
    if not info['audio'] or not boundaries:
        return boundaries, []
    result, decisions = [], []
    for i, nominal in enumerate(boundaries):
        runner.check()
        runner.log(f'Recherche de pause de voix : coupe {i+1}/{len(boundaries)}…')
        # Retain at least one second between cuts, even with one-minute episodes.
        previous = result[-1] if result else 0
        target = nominal-(boundaries[i-1] if i else 0)
        low = max(nominal-30, previous+max(1,target-30))
        high = min(nominal+30, previous+target+30, duration-1,
                   boundaries[i+1]-31 if i+1 < len(boundaries) else duration-1)
        # Context outside the candidate range prevents mistaking a truncated word for silence.
        window_start = max(0, low-2)
        window_end = min(duration, high+2)
        speech = speech_window(source, start+window_start, window_end-window_start, runner)
        candidates = silence_candidates(speech, window_end-window_start,
                        nominal-window_start, low-window_start, high-window_start,
                        step=1/float(Fraction(info.get('fps','30/1'))) if exact else 0,
                        origin=start+window_start)
        point, reason = nominal, 'no_pause'
        if exact and candidates:
            point, reason = candidates[0]+window_start, 'voice_pause'
        elif not exact:
            keys = keyframes(source, start+window_start, window_end-window_start, info, runner)
            valid = []
            for key in keys:
                p = key-start-window_start
                # A keyframe must be inside a safe gap, not merely close to one.
                if silence_candidates(speech, window_end-window_start, p, p, p) and low <= key-start <= high:
                    valid.append(key-start)
            if valid:
                point, reason = min(valid, key=lambda p: abs(p-nominal)), 'voice_pause_keyframe'
        result.append(point)
        decisions.append({'nominal': nominal, 'selected': point, 'shift': point-nominal, 'reason': reason})
        runner.log(f'Coupe {i+1} : décalage {point-nominal:+.2f} s.' if reason != 'no_pause' else
                   f'Coupe {i+1} : aucune pause exploitable ; limite prévue conservée.')
    return result, decisions
