#!/usr/bin/env python3
"""Produce independent excerpts from an evidence-backed editorial plan."""
import argparse
import datetime
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.writing')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temp.replace(path)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(4 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def key(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def run(argv):
    result = subprocess.run([str(a) for a in argv], capture_output=True, text=True)
    if result.returncode:
        raise ValueError(f'{argv[0]} failed ({result.returncode}): {result.stderr[-4000:]}')
    return result.stdout


def ff(*args):
    return run(['ffmpeg', '-hide_banner', '-nostdin', *args])


def probe(path):
    return json.loads(run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', path]))


def fingerprint(path):
    path = Path(path).resolve(strict=True)
    stat = path.stat()
    digest = hashlib.sha256()
    with path.open('rb') as f:
        digest.update(f.read(1 << 20))
        f.seek(max(0, stat.st_size - (1 << 20)))
        digest.update(f.read(1 << 20))
    return {'path': str(path), 'bytes': stat.st_size, 'mtime_ns': stat.st_mtime_ns,
            'edge_sha256': digest.hexdigest(), 'hash_kind': 'size-mtime-and-two-edges'}


def number(value, low=0, high=math.inf):
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError('Expected a JSON number')
    value = float(value)
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'Number outside [{low}, {high}]: {value}')
    return value


def preserve_partial(paths):
    """Keep incomplete generated artifacts before retrying an unstamped stage."""
    suffix = datetime.datetime.now().strftime('%Y%m%dT%H%M%S%f')
    for path in paths:
        path = Path(path)
        if path.exists():
            path.rename(path.with_name(path.name + '.interrupted-' + suffix))


def validate_plan(plan):
    if plan.get('schema') != 'media-independent-clips/v1':
        raise ValueError('Expected media-independent-clips/v1')
    duration = number(plan['source']['duration'], .04)
    fps = number(plan['fps'], 1, 60)
    if fps != int(fps) or 48000 % int(fps):
        raise ValueError('Batch template requires integer fps dividing 48000; use a dedicated timeline for other rates')
    coverage = plan['coverage']
    cursor = 0
    for region in coverage:
        a, b = number(region['start']), number(region['end'], .001, duration)
        if abs(a - cursor) > .025 or b <= a or region['decision'] not in ['candidate', 'exclude', 'review']:
            raise ValueError('Coverage must continuously account for the full original recording')
        if not region.get('reason') or not region.get('evidence'):
            raise ValueError('Each coverage decision requires a reason and evidence')
        cursor = b
    if abs(cursor - duration) > .025:
        raise ValueError('Whole-recording coverage is incomplete')
    identifiers, timeline = set(), []
    if not plan['clips']:
        raise ValueError('No selected clips; retain the coverage review without starting production')
    if plan.get('music'):
        number(plan['music'].get('lufs', -34), -45, -24)
        if not plan['music'].get('rights'):
            raise ValueError('Music requires its authorization/source record')
    for clip in plan['clips']:
        ident = clip['id']
        if not re.fullmatch('[a-z0-9]+(?:-[a-z0-9]+)*', ident) or ident in identifiers:
            raise ValueError('Duplicate or unsafe clip id: ' + ident)
        identifiers.add(ident)
        if not clip.get('title') or not 1 <= len(clip.get('titleLines', [])) <= 2:
            raise ValueError('Each clip needs a title and one or two titleLines')
        if any(not isinstance(line, str) or not line.strip() for line in clip['titleLines']):
            raise ValueError('Title lines must be nonempty text')
        if any(sum(.56 if ord(ch) < 128 else 1 for ch in line) > 10.5 for line in clip['titleLines']):
            raise ValueError('Title line exceeds vertical safe width')
        if len(clip['title']) > plan.get('title_limit', 16):
            raise ValueError('Title exceeds target limit: ' + ident)
        if not clip.get('reason') or not clip.get('boundary_evidence') or not clip.get('standalone_reason'):
            raise ValueError('Missing editorial/boundary evidence: ' + ident)
        end = 0
        for a, b in clip['ranges']:
            a, b = number(a, 0, duration), number(b, .001, duration)
            if b-a < 1/fps:
                raise ValueError('Each retained range must contain at least one video frame')
            if b <= a or a < end or any(abs(t * fps - round(t * fps)) > .002 for t in [a, b]):
                raise ValueError('Ranges must be ordered, positive and frame-aligned: ' + ident)
            if any(min(b, x['end']) > max(a, x['start']) and x['decision'] != 'candidate' for x in coverage):
                raise ValueError('Selected range still overlaps excluded/unreviewed coverage: ' + ident)
            timeline.append((a, b, ident))
            end = b
        if not clip['ranges']:
            raise ValueError('Empty clip: ' + ident)
        clip['duration'] = round(sum(b - a for a, b in clip['ranges']), 6)
        if clip['duration'] < 1:
            raise ValueError('Excerpt is too short for this template')
        if clip.get('presentation', 'source-led') not in ['source-led', 'audio-led']:
            raise ValueError('Unknown presentation')
        if clip.get('presentation') == 'audio-led' and not clip.get('beats'):
            raise ValueError('Audio-led excerpts need evidence-backed summary beats')
        previous = -1
        for beat in clip.get('beats', []):
            start = number(beat['start'], 0, clip['duration'])
            if start <= previous or start >= clip['duration'] or not beat.get('heading') or not beat.get('detail'):
                raise ValueError('Summary beats must be ordered and contain text')
            previous = start
        if clip.get('beats') and clip['beats'][0]['start'] != 0:
            raise ValueError('First summary beat must start at zero')
        number(clip.get('cropX', 760), 0, 1520)
        number(clip.get('cropY', 520), 0, 677)
        for m in clip.get('privacyMasks', []):
            for name in ['x', 'y', 'w', 'h']:
                number(m[name], 0 if name in ['x', 'y'] else 1, 1920)
            if m['x'] + m['w'] > 1920 or m['y'] + m['h'] > 1080:
                raise ValueError('Mask is outside normalized 1920x1080 source')
        for w in clip.get('voice_gain_windows', []):
            if number(w['start'], 0, clip['duration']) >= number(w['end'], 0, clip['duration']):
                raise ValueError('Invalid voice leveling window')
            number(w['gain_db'], -24, 24)
        if len(clip.get('keywords', [])) > 3:
            raise ValueError('Use at most three static keywords, not fabricated chapters')
        if clip.get('presentation') == 'audio-led' and not clip.get('keywords'):
            raise ValueError('Audio-led covers need content-backed keywords')
    timeline.sort()
    for first, second in zip(timeline, timeline[1:]):
        if first[1] > second[0] + .001:
            raise ValueError('Duplicate source coverage across clips: ' + first[2] + ' / ' + second[2])
    for old in plan.get('already_published_ranges', []):
        a, b = old
        number(a, 0, duration); number(b, a, duration)
        if any(min(b, y) - max(a, x) > .001 for x, y, _ in timeline):
            raise ValueError('Selection overlaps already published material')
    return plan


def mapped_video_ranges(ranges, handoff):
    pieces = []
    for a, b in ranges:
        cursor = a
        for f in handoff['files']:
            lo, hi = max(a, f['source_start']), min(b, f['source_end'])
            if hi <= lo:
                continue
            if abs(lo - cursor) > .025:
                raise ValueError('Requested cut crosses a gap in prepared source coverage')
            pieces.append((f['path'], lo - f['source_start'], hi - f['source_start']))
            cursor = hi
        if abs(cursor - b) > .025:
            raise ValueError('Prepared media does not cover this cut')
    return pieces


def parse_srt(path, duration):
    cues = []
    for block in re.split(r'\n\s*\n', Path(path).read_text(encoding='utf-8-sig').strip()):
        lines = block.splitlines()
        if len(lines) < 3:
            raise ValueError('Invalid SRT block')
        match = re.fullmatch(r'(\d{2,}):(\d{2}):(\d{2}),(\d{3}) --> (\d{2,}):(\d{2}):(\d{2}),(\d{3})', lines[1])
        if not match:
            raise ValueError('Invalid SRT timestamp')
        n = list(map(int, match.groups()))
        if any(n[i] > 59 for i in [1, 2, 5, 6]):
            raise ValueError('Invalid SRT minute/second')
        a, b = n[0]*3600+n[1]*60+n[2]+n[3]/1000, n[4]*3600+n[5]*60+n[6]+n[7]/1000
        text = '\n'.join(lines[2:])
        if not 0 <= a < b <= duration + .001 or (cues and a < cues[-1]['end']):
            raise ValueError('SRT overlaps or escapes the final timeline')
        if len(lines[2:]) > 2 or any(sum(.55 if ord(c) < 128 else 1 for c in row) > 13.1 for row in lines[2:]):
            raise ValueError('SRT exceeds vertical safe area: ' + text)
        cues.append({'start': a, 'end': b, 'text': text})
    if not cues:
        raise ValueError('Empty subtitles')
    return cues


class Batch:
    def __init__(self, directory):
        self.root = Path(directory).resolve(strict=True)
        self.plan = validate_plan(read(self.root / 'plan.json'))
        self.fps = self.plan['fps']
        self.source = Path(self.plan['source']['path'])
        if fingerprint(self.source) != read(self.root / 'source-identity.json'):
            raise ValueError('Original source changed; start a new source revision')

    def path(self, ident, name):
        p = self.root / 'clips' / ident / name
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def clips(self, selected):
        unknown = set(selected or []) - {c['id'] for c in self.plan['clips']}
        if unknown:
            raise ValueError('Unknown clip ids: ' + ', '.join(sorted(unknown)))
        return [c for c in self.plan['clips'] if not selected or c['id'] in selected]

    def cached(self, ident, stage, inputs):
        p = self.path(ident, stage + '.json')
        if not p.exists():
            return None
        old = read(p)
        if old['input_key'] != key(inputs):
            raise ValueError(f'{ident}/{stage} inputs changed. Start a new revision directory; old outputs are preserved')
        for path, digest in old['artifacts'].items():
            if sha(self.root / path) != digest:
                raise ValueError('Cached artifact changed: ' + path)
        return old

    def stamp(self, ident, stage, inputs, files, **extra):
        result = {'stage': stage, 'id': ident, 'input_key': key(inputs),
                  'artifacts': {str(Path(p).relative_to(self.root)): sha(p) for p in files}, **extra}
        write(self.path(ident, stage + '.json'), result)
        return result

    def prepared(self, c):
        inputs = {'source': read(self.root/'source-identity.json'), 'ranges': c['ranges'],
                  'handoff': read(self.plan['handoff']) if self.plan.get('handoff') else None,
                  'fps': self.fps, 'masks': c.get('privacyMasks', [])}
        result = self.cached(c['id'], 'prepare', inputs)
        if result is None:
            raise ValueError('Prepare this clip before production')
        return result

    def prepare(self, c):
        ident, duration = c['id'], c['duration']
        handoff = read(self.plan['handoff']) if self.plan.get('handoff') else None
        pieces = [(str(self.source), a, b) for a, b in c['ranges']]
        if handoff:
            identity = read(self.root / 'source-identity.json')
            if (handoff.get('schema') != 'media-preprocess-handoff/v1' or
                    handoff.get('source_timebase') != 'original-seconds' or
                    handoff['source']['bytes'] != identity['bytes'] or
                    handoff['source']['edge_sha256'] != identity['edge_sha256']):
                raise ValueError('Prepared handoff belongs to a different source/timebase')
            pieces = mapped_video_ranges(c['ranges'], handoff)
            used = {p for p, _, _ in pieces}
            for f in handoff['files']:
                if f['path'] in used and sha(f['path']) != f['sha256']:
                    raise ValueError('Prepared enhancement file changed')
        inputs = {'source': read(self.root/'source-identity.json'), 'ranges': c['ranges'],
                  'handoff': handoff, 'fps': self.fps, 'masks': c.get('privacyMasks', [])}
        if self.cached(ident, 'prepare', inputs):
            return
        preserve_partial([self.path(ident, n) for n in ['source.wav', 'body.mp4']])
        stem = self.root/'source-48k.wav'
        if stem.exists() and not (self.root/'source-pcm.json').exists():
            preserve_partial([stem])
        if not stem.exists():
            temp = self.root/'source-48k.partial.wav'
            preserve_partial([temp])
            ff('-n', '-i', self.source, '-map', '0:a:0', '-vn', '-ar', '48000', '-ac', '2', '-c:a', 'pcm_s24le', temp)
            temp.replace(stem)
            write(self.root/'source-pcm.json', {'source': inputs['source'], 'sha256': sha(stem)})
        elif read(self.root/'source-pcm.json')['sha256'] != sha(stem):
            raise ValueError('Source PCM changed')
        audio = self.path(ident, 'source.wav')
        filters, labels = [], []
        for i, (a, b) in enumerate(c['ranges']):
            filters.append(f'[0:a]atrim=start_sample={round(a*48000)}:end_sample={round(b*48000)},asetpts=N/SR/TB,afade=t=in:d=0.006,afade=t=out:st={b-a-.006}:d=0.006[a{i}]')
            labels.append(f'[a{i}]')
        filters.append(''.join(labels)+f'concat=n={len(labels)}:v=0:a=1[a]')
        ff('-n', '-i', stem, '-filter_complex', ';'.join(filters), '-map', '[a]', '-c:a', 'pcm_s24le', audio)
        body = self.path(ident, 'body.mp4')
        args, filters, labels = [], [], []
        for i, (p, a, b) in enumerate(pieces):
            args += ['-ss', str(a), '-t', str(b-a), '-i', p]
            filters.append(f'[{i}:v]trim=duration={b-a},setpts=PTS-STARTPTS,scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={self.fps}[v{i}]')
            labels.append(f'[v{i}]')
        masks = ''.join(f",drawbox=x={m['x']}:y={m['y']}:w={m['w']}:h={m['h']}:color=0xF0EAE1:t=fill" for m in c.get('privacyMasks', []))
        filters.append(''.join(labels)+f'concat=n={len(labels)}:v=1:a=0'+masks+'[v]')
        ff('-n', *args, '-i', audio, '-filter_complex', ';'.join(filters), '-map', '[v]', '-map', f'{len(pieces)}:a:0', '-frames:v', str(round(duration*self.fps)), '-c:v', 'libx264', '-preset', 'fast', '-crf', '18', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '256k', '-ar', '48000', '-map_metadata', '-1', '-movflags', '+faststart', body)
        v = next(s for s in probe(body)['streams'] if s['codec_type'] == 'video')
        if int(v['nb_frames']) != round(duration*self.fps) or abs(float(probe(audio)['format']['duration'])-duration) > .001:
            raise ValueError('Prepared frame/sample count differs from the precise cut')
        ff('-v', 'error', '-xerror', '-i', body, '-f', 'null', '-')
        self.stamp(ident, 'prepare', inputs, [body, audio], ranges=c['ranges'], duration=duration)

    def transcribe(self, c, model, language):
        import numpy as np
        import mlx_whisper
        model = Path(model).resolve(strict=True)
        if not model.is_dir() or not any((model/name).is_file() for name in ['weights.safetensors', 'weights.npz']):
            raise ValueError('Supply a local MLX model directory with weights; downloads are not implicit')
        prepared = self.prepared(c)
        if getattr(self, '_model_path', None) != model:
            self._model_hashes = {p.name: sha(p) for p in model.iterdir() if p.is_file()}
            self._model_path = model
        inputs = {'prepared': prepared['artifacts'], 'model': self._model_hashes, 'language': language, 'word_timestamps': True}
        if self.cached(c['id'], 'transcribe', inputs):
            return
        pcm = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(self.path(c['id'], 'source.wav')), '-ac', '1', '-ar', '16000', '-f', 's16le', 'pipe:1'])
        result = mlx_whisper.transcribe(np.frombuffer(pcm, dtype='<i2').astype(np.float32)/32768, path_or_hf_repo=str(model), language=language, temperature=0, condition_on_previous_text=False, word_timestamps=True, verbose=None)
        out = self.path(c['id'], 'asr.json')
        write(out, {'source_body_sha256': sha(self.path(c['id'], 'body.mp4')), 'source_pcm_sha256': sha(self.path(c['id'], 'source.wav')), 'transcript': result})
        self.stamp(c['id'], 'transcribe', inputs, [out], human_auditory_review=False)

    def template_identity(self):
        root = self.root/'remotion'
        paths = [root/'package.json', root/'render.mjs', root/'src/Scene.tsx',
                 root/'src/index.tsx', root/'src/settings.json', *sorted((root/'public/fonts').glob('*'))]
        if (root/'public/cover-paper.png').exists(): paths.append(root/'public/cover-paper.png')
        return {str(p.relative_to(root)): sha(p) for p in paths if p.is_file()}

    def lock(self, c, review_path):
        review = read(review_path)
        ident = c['id']
        if review.get('reviewer') not in ['user', 'delegated-agent'] or not review.get('authorization_evidence'):
            raise ValueError('Record actual reviewer and authorization evidence')
        for field in ['content', 'boundaries', 'subtitles', 'privacy', 'presentation']:
            if review.get(field) != 'passed':
                raise ValueError('Missing actual review: ' + field)
        if not review.get('evidence'):
            raise ValueError('Missing actual review evidence')
        self.prepared(c)
        body, pcm, mix = (self.path(ident, p) for p in ['body.mp4', 'source.wav', 'mix.m4a'])
        asr = read(self.path(ident, 'asr.json'))
        if asr['source_body_sha256'] != sha(body) or asr['source_pcm_sha256'] != sha(pcm):
            raise ValueError('ASR belongs to a different cut')
        srt = Path(review['srt']).expanduser()
        if not srt.is_absolute():
            srt = Path(review_path).resolve().parent/srt
        if review['srt_sha256'] != sha(srt) or review['body_sha256'] != sha(body):
            raise ValueError('Review belongs to a different body or SRT')
        aq = read(self.path(ident, 'mix.json'))
        if aq['status'] != 'passed' or aq['source_pcm_sha256'] != sha(pcm) or aq['mix_sha256'] != sha(mix):
            raise ValueError('Mix lineage or QC failed')
        cues = parse_srt(srt, c['duration'])
        locked = self.path(ident, 'lock.json')
        if locked.exists():
            self.check_lock(c)
            if read(locked)['srt_sha256'] != sha(srt):
                raise ValueError('Locked subtitle differs; choose a new revision directory')
            return
        preserve_partial([self.path(ident, n) for n in ['locked.srt', 'head.jpg', 'middle.jpg', 'tail.jpg', 'cover-photo.jpg']])
        shutil.copy2(srt, self.path(ident, 'locked.srt'))
        frames = []
        for label, sec in [('head', min(1, c['duration']/4)), ('middle', c['duration']/2), ('tail', max(0, c['duration']-.6))]:
            jpg = self.path(ident, label+'.jpg')
            ff('-n', '-v', 'error', '-ss', str(sec), '-i', body, '-frames:v', '1', '-q:v', '2', jpg)
            frames.append(jpg)
        photo = self.path(ident, 'cover-photo.jpg')
        shutil.copy2(frames[0 if c.get('cover_frame') == 'head' else 1], photo)
        data = {**c, 'cues': cues, 'audio': 'audio/'+ident+'.m4a', 'fps': self.fps,
                'brand': self.plan.get('brand', ''), 'role': c.get('role', '现场原声'),
                'cropX': c.get('cropX', 760), 'cropY': c.get('cropY', 520),
                'chapters': [{'start': 0, 'label': x} for x in c.get('keywords', [])],
                'coverKeywords': c.get('keywords', []), 'waveform': aq['waveform']}
        record = {'id': ident, 'clip_key': key(c), 'clip_data': data,
                  'body_sha256': sha(body), 'pcm_sha256': sha(pcm), 'audio_sha256': sha(mix),
                  'srt_sha256': sha(srt), 'template': self.template_identity(),
                  'cover_photo_sha256': sha(photo), 'brand': self.plan.get('brand', ''),
                  'review': review, 'status': 'locked', 'human_auditory_review': review.get('human_auditory_review', False)}
        write(locked, record)

    def check_lock(self, c):
        self.prepared(c)
        record = read(self.path(c['id'], 'lock.json'))
        if record['clip_key'] != key(c):
            raise ValueError('Locked editorial plan changed')
        for name, field in [('body.mp4', 'body_sha256'), ('source.wav', 'pcm_sha256'), ('mix.m4a', 'audio_sha256'), ('locked.srt', 'srt_sha256')]:
            if sha(self.path(c['id'], name)) != record[field]:
                raise ValueError('Locked artifact changed: ' + name)
        if self.template_identity() != record['template'] or self.plan.get('brand', '') != record['brand']:
            raise ValueError('Locked template/assets/brand changed')
        if sha(self.path(c['id'], 'cover-photo.jpg')) != record['cover_photo_sha256']:
            raise ValueError('Locked cover photo changed')
        return record

    def render(self, c, mode):
        record = self.check_lock(c)
        root = self.root/'remotion'
        for folder, name, source in [('body', c['id']+'.mp4', 'body.mp4'), ('audio', c['id']+'.m4a', 'mix.m4a'), ('photos', c['id']+'.jpg', 'cover-photo.jpg')]:
            target = root/'public'/folder/name
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists() or sha(target) != sha(self.path(c['id'], source)):
                shutil.copy2(self.path(c['id'], source), target)
        write(root/'src/clips.json', [record['clip_data']])
        run(['node', root/'render.mjs', c['id'], mode])


def initialize(plan_path, output):
    plan_path = Path(plan_path).resolve(strict=True)
    plan = validate_plan(read(plan_path))
    for field in ['handoff']:
        if plan.get(field):
            plan[field] = str((plan_path.parent/Path(plan[field]).expanduser()).resolve(strict=True))
    source = (plan_path.parent/Path(plan['source']['path']).expanduser()).resolve(strict=True)
    plan['source']['path'] = str(source)
    actual = probe(source)
    video = next(s for s in actual['streams'] if s['codec_type'] == 'video')
    if abs(float(actual['format']['duration'])-plan['source']['duration']) > .05 or Fraction(video['avg_frame_rate']) != Fraction(plan['fps']):
        raise ValueError('Source duration/frame rate differs from editorial plan')
    if not any(s['codec_type'] == 'audio' for s in actual['streams']):
        raise ValueError('This spoken excerpt workflow requires original audio')
    for name in ['body_font', 'title_font', 'paper']:
        if plan.get('assets', {}).get(name):
            plan['assets'][name] = str((plan_path.parent/Path(plan['assets'][name]).expanduser()).resolve(strict=True))
    if plan.get('music'):
        plan['music']['path'] = str((plan_path.parent/Path(plan['music']['path']).expanduser()).resolve(strict=True))
        if not plan['music'].get('rights'):
            raise ValueError('Record the supplied music authorization/source')
    root = Path(output).resolve()
    for name in ['body_font', 'title_font']:
        if not plan.get('assets', {}).get(name):
            raise ValueError('Supply local licensed font: ' + name)
    if root.exists() and any(root.iterdir()):
        if read(root/'plan.json') != plan:
            raise ValueError('Existing run has a different plan; choose a new revision directory')
        return
    root.mkdir(parents=True, exist_ok=True)
    template = Path(__file__).resolve().parents[1]/'assets/independent-clips'
    shutil.copytree(template, root/'remotion')
    for name, filename in [('body_font', 'NotoSansSC-VariableFont_wght.ttf'), ('title_font', 'SmileySans-Oblique.ttf')]:
        src = plan.get('assets', {}).get(name)
        if not src:
            raise ValueError('Supply local licensed font: ' + name)
        target = root/'remotion/public/fonts'/filename
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
    if plan.get('assets', {}).get('paper'):
        shutil.copy2(plan['assets']['paper'], root/'remotion/public/cover-paper.png')
    write(root/'remotion/src/settings.json', {'paper': bool(plan.get('assets', {}).get('paper'))})
    write(root/'plan.json', plan)
    write(root/'source-identity.json', fingerprint(source))


def status(batch):
    rows = []
    for c in batch.plan['clips']:
        ident = c['id']
        qcpath = batch.path(ident, 'final-qc.json')
        state = 'draft'
        if qcpath.exists():
            batch.check_lock(c)
            qc = read(qcpath)
            if sha(batch.path(ident, 'final.mp4')) != qc['sha256']:
                raise ValueError('Final file changed: ' + ident)
            state = 'encoded-awaiting-visual-review'
            visual = batch.path(ident, 'visual-review.json')
            if visual.exists():
                v = read(visual)
                if (v.get('status') == 'passed' and v.get('reviewer') in ['user', 'delegated-agent']
                        and v.get('evidence') and v.get('video_sha256') == qc['sha256']
                        and all(v.get(name+'_sha256') == sha(batch.path(ident, name+'.png')) for name in ['cover-3x4', 'cover-4x3'])):
                    state = 'platform-ready'
        rows.append({'id': ident, 'title': c['title'], 'duration': c['duration'], 'status': state,
                     'video': str(batch.path(ident, 'final.mp4')),
                     'cover_3x4': str(batch.path(ident, 'cover-3x4.png')),
                     'cover_4x3': str(batch.path(ident, 'cover-4x3.png')),
                     'subtitles': str(batch.path(ident, 'locked.srt')),
                     'qc': str(qcpath), 'source_ranges': c['ranges'],
                     'description': c.get('description', ''), 'topics': c.get('topics', []),
                     'publication': 'not-published'})
    result = {'schema': 'media-clip-delivery/v1', 'clips': rows, 'selected': len(rows),
              'platform_ready': sum(r['status']=='platform-ready' for r in rows), 'publication': 'not-published'}
    write(batch.root/'delivery.json', result)
    lines = ['# 独立切片清单', '', '| 标题 | 时长 | 状态 | 视频 | 封面 | 字幕 |', '|---|---:|---|---|---|---|']
    for r in rows:
        title = r['title'].replace('|', '\\|')
        link = f"[MP4](<{r['video']}>)" if Path(r['video']).exists() else '尚未导出'
        covers = ' · '.join(f"[{label}](<{r[name]}>)" for name,label in [('cover_3x4','3:4'),('cover_4x3','4:3')] if Path(r[name]).exists()) or '尚未导出'
        subtitle = f"[SRT](<{r['subtitles']}>)" if Path(r['subtitles']).exists() else '尚未锁定'
        lines.append(f"| {title} | {r['duration']:.2f}s | {r['status']} | {link} | {covers} | {subtitle} |")
    (batch.root/'delivery.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('init'); p.add_argument('--plan', required=True); p.add_argument('--output', required=True)
    p = sub.add_parser('check-plan'); p.add_argument('--plan', required=True)
    for name in ['prepare', 'transcribe', 'subtitles', 'mix', 'lock', 'render', 'verify', 'status']:
        p = sub.add_parser(name); p.add_argument('--run', required=True); p.add_argument('--clip', action='append')
        if name == 'transcribe':
            p.add_argument('--model', required=True); p.add_argument('--language', default='zh')
        if name == 'lock': p.add_argument('--review', required=True)
        if name == 'render': p.add_argument('--mode', choices=['covers', 'video', 'canary'], default='video')
    args = parser.parse_args()
    try:
        if args.command == 'init': initialize(args.plan, args.output)
        elif args.command == 'check-plan':
            plan = validate_plan(read(args.plan)); print(json.dumps({'valid': True, 'clips': len(plan['clips'])}))
        else:
            batch = Batch(args.run)
            if args.command == 'status': print(json.dumps(status(batch), ensure_ascii=False)); return
            clips = batch.clips(args.clip)
            if args.command == 'lock' and len(clips) != 1:
                raise ValueError('Lock one reviewed clip at a time with --clip')
            for c in clips:
                print(args.command, c['id'], flush=True)
                if args.command == 'prepare': batch.prepare(c)
                elif args.command == 'transcribe': batch.transcribe(c, args.model, args.language)
                elif args.command == 'subtitles':
                    from clip_subtitles import draft
                    draft(batch, c)
                elif args.command == 'mix':
                    from clip_audio import mix
                    mix(batch, c)
                elif args.command == 'lock': batch.lock(c, args.review)
                elif args.command == 'render': batch.render(c, args.mode)
                elif args.command == 'verify':
                    from clip_audio import finalize
                    finalize(batch, c)
            status(batch)
    except (ValueError, KeyError, OSError, StopIteration, subprocess.CalledProcessError) as error:
        parser.exit(2, f'error: {error}\n')


if __name__ == '__main__':
    main()
