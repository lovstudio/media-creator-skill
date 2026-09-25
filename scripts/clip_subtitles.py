"""Create editable draft captions from ASR word timing; never approve them."""
import re
from clip_batch import read, sha


def units(text):
    return sum(.55 if ord(c) < 128 else 1 for c in text)


def timestamp(seconds):
    ms = round(seconds*1000)
    h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
    return f'{h:02}:{m:02}:{s:02},{ms:03}'


def build_cues(transcript, duration):
    tokens = []
    for segment in transcript['segments']:
        if not segment.get('words'):
            raise ValueError('Word timestamps are required; segment timing alone cannot certify a precise cut')
        for word in segment['words']:
            text = word['word']
            parts = re.findall(r"[A-Za-z0-9]+(?:['.-][A-Za-z0-9]+)*|[^A-Za-z0-9]", text)
            parts = [p for p in parts if p.strip()]
            if not parts: continue
            a, b = max(0, float(word['start'])), min(duration, float(word['end']))
            if b <= a:
                raise ValueError('ASR contains zero-length words; correct their timing before drafting')
            for i, part in enumerate(parts):
                if units(part) > 13:
                    raise ValueError('Long token needs an explicit editorial abbreviation: ' + part)
                tokens.append((a+(b-a)*i/len(parts), a+(b-a)*(i+1)/len(parts), part))
    cues, lines, start, end = [], [''], None, 0
    def flush():
        if start is not None:
            cues.append({'start': start, 'end': end, 'text': '\n'.join(lines)})
    for a, b, token in tokens:
        if start is not None and (a-end > .65 or b-start > 4.8):
            flush(); lines, start = [''], None
        spacing = ' ' if lines[-1] and lines[-1][-1].isascii() and lines[-1][-1].isalnum() and token[0].isascii() and token[0].isalnum() else ''
        if units(lines[-1]+spacing+token) > 13:
            if len(lines) == 2:
                flush(); lines, start = [''], None
            else:
                lines.append('')
            spacing = ''
        if start is None: start = max(a, cues[-1]['end'] if cues else 0)
        lines[-1] += spacing+token
        end = max(b, start+.001)
        if token in '。！？!?':
            flush(); lines, start = [''], None
    flush()
    if not cues or any(c['end'] > duration+.001 or c['end'] <= c['start'] for c in cues):
        raise ValueError('ASR timing needs review; cannot generate bounded captions')
    return cues


def draft(batch, c):
    ident = c['id']; batch.prepared(c)
    source = batch.path(ident, 'asr.json'); asr = read(source)
    if asr['source_body_sha256'] != sha(batch.path(ident, 'body.mp4')) or asr['source_pcm_sha256'] != sha(batch.path(ident, 'source.wav')):
        raise ValueError('ASR belongs to another edit')
    inputs = {'asr_sha256': sha(source), 'caption_width': 13, 'lines': 2}
    if batch.cached(ident, 'subtitles', inputs): return
    path = batch.path(ident, 'draft.srt')
    if path.exists():
        raise ValueError('Unstamped draft.srt exists; preserve your edits and use a new draft filename/revision')
    cues = build_cues(asr['transcript'], c['duration'])
    path.write_text('\n\n'.join(f'{i+1}\n{timestamp(q["start"])} --> {timestamp(q["end"])}\n{q["text"]}' for i,q in enumerate(cues))+'\n', encoding='utf-8')
    batch.stamp(ident, 'subtitles', inputs, [path], status='draft-needs-review',
                timing='ASR word anchors; intraword character timing interpolated', human_auditory_review=False)
