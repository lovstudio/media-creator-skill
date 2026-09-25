"""Continuous sample-based dialogue, music and final encoded-media verification."""
import json
import math
from pathlib import Path
import re
import subprocess

from fractions import Fraction
from clip_batch import ff, preserve_partial, probe, read, run, sha, write


def measure(path):
    result = subprocess.run(['ffmpeg', '-hide_banner', '-nostdin', '-i', str(path), '-af',
                             'loudnorm=I=-16:TP=-1:LRA=11:print_format=json', '-f', 'null', '-'],
                            capture_output=True, text=True, check=True)
    values = json.loads(re.findall(r'\{\s*"input_i"[\s\S]*?\}', result.stderr)[-1])
    if not all(math.isfinite(float(values[k])) for k in ['input_i', 'input_tp', 'input_lra', 'input_thresh', 'target_offset']):
        raise ValueError('No measurable finite original audio; inspect source instead of amplifying silence')
    return values


def packet_clock(path):
    packets = json.loads(run(['ffprobe', '-v', 'error', '-select_streams', 'a:0', '-show_packets',
                              '-show_entries', 'packet=pts,duration', '-of', 'json', path]))['packets']
    if len(packets) < 3 or not all(int(p['duration']) == 1024 for p in packets[1:-1]):
        raise ValueError('Non-continuous AAC packet durations')
    if not all(int(b['pts'])-int(a['pts']) == 1024 for a, b in zip(packets[1:-2], packets[2:-1])):
        raise ValueError('Non-continuous AAC packet timestamps')


def music_bed(batch):
    config = batch.plan.get('music')
    if config is None:
        return None
    source = Path(config['path'])
    duration = max(c['duration'] for c in batch.plan['clips'])
    settings = {'sha256': sha(source), 'duration': duration, 'target_lufs': config.get('lufs', -34), 'crossfade': 2}
    path = batch.root/'music-bed.wav'
    record = batch.root/'music-bed.json'
    if record.exists():
        old = read(record)
        if old['settings'] != settings or sha(path) != old['sha256']:
            raise ValueError('Music bed changed; use a new audio revision')
        return path
    preserve_partial([path])
    length = float(probe(source)['format']['duration'])
    if length <= 4:
        raise ValueError('Music too short for a continuous two-second crossfade bed')
    count = max(1, math.ceil((duration-2)/(length-2)))
    args = []
    for _ in range(count): args += ['-i', str(source)]
    filters = []
    label = '0:a'
    for i in range(1, count):
        filters.append(f'[{label}][{i}:a]acrossfade=d=2:c1=tri:c2=tri[b{i}]')
        label = f'b{i}'
    filters.append(f'[{label}]atrim=duration={duration},asetpts=N/SR/TB,loudnorm=I={settings["target_lufs"]}:TP=-9:LRA=11,aresample=48000[bed]')
    ff('-n', *args, '-filter_complex', ';'.join(filters), '-map', '[bed]', '-c:a', 'pcm_s24le', path)
    write(record, {'settings': settings, 'sha256': sha(path), 'rights': config['rights']})
    return path


def mix(batch, c):
    import numpy as np
    ident, duration = c['id'], c['duration']
    batch.prepared(c)
    source = batch.path(ident, 'source.wav')
    bed = music_bed(batch)
    settings = {'pcm': sha(source), 'bed': sha(bed) if bed else None,
                'gain_windows': c.get('voice_gain_windows', []), 'duration': duration}
    if batch.cached(ident, 'mix', settings): return
    preserve_partial([batch.path(ident, name) for name in ['leveled.wav', 'voice.wav', 'premix.wav', 'mix.m4a',
        *[f'mix-{kind}-{i}.m4a' for kind in ['attempt', 'clock'] for i in range(4)]]])
    leveled, voice, premix = (batch.path(ident, f) for f in ['leveled.wav', 'voice.wav', 'premix.wav'])
    gain_filters = ','.join(f"volume={w['gain_db']}dB:enable='between(t,{w['start']},{w['end']})'" for w in c.get('voice_gain_windows', [])) or 'anull'
    ff('-n', '-i', source, '-af', gain_filters, '-c:a', 'pcm_s24le', leveled)
    m = measure(leveled)
    normalization = f'loudnorm=I=-16:TP=-3:LRA=11:measured_I={m["input_i"]}:measured_TP={m["input_tp"]}:measured_LRA={m["input_lra"]}:measured_thresh={m["input_thresh"]}:offset={m["target_offset"]}:linear=true,aresample=48000,alimiter=limit=0.630957:level=false:latency=true,atrim=end_sample={round(duration*48000)},asetpts=N/SR/TB'
    ff('-n', '-i', leveled, '-af', normalization, '-c:a', 'pcm_s24le', voice)
    if bed:
        filters = f'[0:a]asplit=2[v][key];[1:a]atrim=duration={duration},asetpts=N/SR/TB,afade=t=in:d={min(1.5,duration/4)},afade=t=out:st={max(0,duration-2)}:d={min(2,duration)}[b];[b][key]sidechaincompress=threshold=0.02:ratio=4:attack=15:release=200[duck];[v][duck]amix=inputs=2:normalize=0:duration=first,atrim=end_sample={round(duration*48000)},asetpts=N/SR/TB[m]'
        ff('-n', '-i', voice, '-i', bed, '-filter_complex', filters, '-map', '[m]', '-c:a', 'pcm_s24le', premix)
    else:
        ff('-n', '-i', voice, '-c:a', 'copy', premix)
    measured = measure(premix)
    gain = -16-float(measured['input_i'])
    if abs(gain) > 7: raise ValueError('Unexpected mix gain; inspect speech/music balance')
    post_gain = 0
    for attempt in range(4):
        encoded = batch.path(ident, f'mix-attempt-{attempt}.m4a')
        clocked = batch.path(ident, f'mix-clock-{attempt}.m4a')
        ff('-n', '-i', premix, '-af', f'volume={gain}dB,aresample=192000,alimiter=limit=0.501187:level=false:latency=true,aresample=48000,volume={post_gain}dB,atrim=end_sample={round(duration*48000)},asetpts=N/SR/TB', '-c:a', 'aac', '-b:a', '256k', '-ar', '48000', '-movflags', '+faststart', encoded)
        ff('-n', '-i', encoded, '-c', 'copy', '-bsf:a', r'setts=pts=round(PTS/1024)*1024:dts=round(DTS/1024)*1024:duration=if(gt(DURATION\,512)\,1024\,DURATION)', '-movflags', '+faststart', clocked)
        actual = measure(clocked)
        if abs(float(actual['input_i'])+16) <= 1.5 and float(actual['input_tp']) <= -1:
            dest = batch.path(ident, 'mix.m4a'); clocked.replace(dest); break
        delta = min(-16-float(actual['input_i']), -1.8-float(actual['input_tp']))
        if abs(delta) < .05 or attempt == 3:
            raise ValueError('Encoded audio does not meet LUFS/true peak limits: '+str(actual))
        post_gain += delta
    packet_clock(dest)
    pcm = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(voice), '-ac', '1', '-ar', '16000', '-f', 's16le', 'pipe:1'])
    x = np.frombuffer(pcm, dtype='<i2').astype(float)/32768
    x = np.pad(x, (0, (-len(x)) % 800))
    rms = np.sqrt(np.mean(x.reshape(-1, 800)**2, axis=1))
    waveform = np.clip(rms/max(float(np.percentile(rms, 92)), .001), 0, 1).round(3).tolist()
    batch.stamp(ident, 'mix', settings, [dest, voice], status='passed', source_pcm_sha256=sha(source),
                mix_sha256=sha(dest), measured=actual, packet_continuity='passed', waveform=waveform,
                music_rights=batch.plan.get('music', {}).get('rights') if bed else 'no-music-requested',
                human_auditory_review=False)


def alignment(reference, output, positions, duration):
    import numpy as np
    findings = []
    for t in positions:
        seconds = min(6, duration-t)
        arrays = []
        for p in [reference, output]:
            raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-ss', str(t), '-i', str(p), '-t', str(seconds), '-ac', '1', '-ar', '16000', '-f', 's16le', 'pipe:1'])
            arrays.append(np.frombuffer(raw, dtype='<i2').astype(float))
        n = min(map(len, arrays)); x, y = [a[:n]-a[:n].mean() for a in arrays]
        norm = float(np.sqrt(np.dot(x, x)*np.dot(y, y)))
        if not norm or n < 1600:
            raise ValueError('Alignment window is silent/too short; choose an audible evidence window')
        size = 1 << (2*n-1).bit_length(); lags = np.arange(-min(1600,n//4), min(1600,n//4)+1)
        corr = np.fft.irfft(np.fft.rfft(x,size)*np.conj(np.fft.rfft(y,size)),size)[lags % size]/norm
        best = int(np.argmax(corr)); lag, score = float(lags[best])/16, float(corr[best])
        if abs(lag) > 40 or score < .8:
            raise ValueError(f'Audio alignment failed at {t}s: lag {lag}ms, correlation {score}')
        findings.append({'seconds': t, 'lag_ms': lag, 'correlation': score})
    return findings


def finalize(batch, c):
    ident, duration = c['id'], c['duration']
    lock = batch.check_lock(c)
    muted, audio, dest = (batch.path(ident, f) for f in ['muted.mp4', 'mix.m4a', 'final.mp4'])
    render = read(batch.path(ident, 'render.json'))
    if render['lock_sha256'] != sha(batch.path(ident, 'lock.json')) or render['sha256'] != sha(muted):
        raise ValueError('Rendered video differs from locked revision')
    if not batch.path(ident, 'final-qc.json').exists():
        preserve_partial([dest, *[batch.path(ident, 'final-'+label+'.jpg') for label in ['head', 'middle', 'tail']]])
        ff('-n', '-i', muted, '-i', audio, '-map', '0:v:0', '-map', '1:a:0', '-c', 'copy', '-map_metadata', '-1', '-movflags', '+faststart', dest)
    elif sha(dest) != read(batch.path(ident, 'final-qc.json'))['sha256']:
        raise ValueError('Verified final changed; choose a new revision directory')
    p = probe(dest)
    v = next(s for s in p['streams'] if s['codec_type']=='video')
    a = next(s for s in p['streams'] if s['codec_type']=='audio')
    if ((v['width'],v['height'],v['pix_fmt'],v['codec_name']) != (1080,1920,'yuv420p','h264')
            or Fraction(v['avg_frame_rate']) != Fraction(batch.fps) or int(v['nb_frames']) != round(duration*batch.fps)):
        raise ValueError('Final video dimensions/frames/codec do not match plan')
    if a['codec_name'] != 'aac' or a['sample_rate'] != '48000' or abs(float(p['format']['duration'])-duration) > .05:
        raise ValueError('Final audio/container duration mismatch')
    hash_audio = lambda path: ff('-v', 'error', '-i', path, '-map', '0:a:0', '-c:a', 'copy', '-f', 'hash', '-hash', 'sha256', '-').strip()
    if hash_audio(dest) != hash_audio(audio): raise ValueError('Verified AAC changed during mux')
    ff('-v', 'error', '-xerror', '-i', dest, '-f', 'null', '-')
    packet_clock(dest)
    joins, at = [], 0
    for start, end in c['ranges'][:-1]:
        at += end-start; joins.append(max(0, at-2))
    positions = sorted(set([0, duration*.3, duration*.65, max(0,duration-6), *joins]))
    matches = alignment(batch.path(ident, 'voice.wav'), dest, positions, duration)
    for label, t in [('head',min(1,duration/4)),('middle',duration/2),('tail',max(0,duration-.6))]:
        path = batch.path(ident, 'final-'+label+'.jpg')
        if not path.exists(): ff('-n','-v','error','-ss',str(t),'-i',dest,'-frames:v','1','-q:v','2',path)
    for name, dimensions in [('cover-3x4.png',(1080,1440)),('cover-4x3.png',(1440,1080))]:
        covers = read(batch.path(ident, 'covers.json'))
        if covers['lock_sha256'] != sha(batch.path(ident, 'lock.json')) or covers['artifacts'][name] != sha(batch.path(ident, name)):
            raise ValueError('Cover differs from the locked render revision')
        cover = probe(batch.path(ident,name))['streams'][0]
        if (cover['width'],cover['height']) != dimensions: raise ValueError('Cover dimensions mismatch')
    write(batch.path(ident,'final-qc.json'), {'status':'encoded-awaiting-visual-review','sha256':sha(dest),
          'full_decode':'passed','audio_bitstream_identical':True,'packet_clock':'passed',
          'audio_alignment':matches,'alignment_reference':'normalized original PCM; no time-shift compensation',
          'subtitle_sha256':lock['srt_sha256'],'duration':duration,'probe':p,'publication':'not-published'})
