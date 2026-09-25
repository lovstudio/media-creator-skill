#!/usr/bin/env python3
"""Analyze a user-provided BGM library for cue-sheet design; writes tracks.json and a markdown summary.

The whole library is in scope: every audio file found is analyzed, and files that cannot be decoded
are listed under "unplayable" with the reason so they can be reported instead of silently dropped.
Per playable track: duration, 1 s loudness and brightness curves, tempo estimate, energy change
points, quiet windows (clean entry/exit points), rises (hit points) and sung-lyric spans from a
sidecar .lrc. A track without .lrc has instrumental=null (unknown) unless declared --instrumental.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

import numpy as np

SR = 22050
AUDIO = {".mp3", ".m4a", ".aac", ".flac", ".wav", ".ogg", ".opus", ".aiff", ".aif"}
CREDIT = re.compile(r"^(作词|作曲|编曲|制作|出品|OP|SP|混音|录音|母带|吉他|贝斯|鼓|和声|监制|原唱|"
                    r"Lyrics|Composer|Arranger|Producer)")


def lang(text):
    if re.search(r"[぀-ヿ]", text):
        return "ja"
    if re.search(r"[᠀-᢯]", text):
        return "mn"
    if re.search(r"[一-鿿]", text):
        return "zh"
    if re.search(r"[A-Za-z]", text):
        return "en"
    return "other"


def decode(path):
    r = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", str(path), "-ac", "1", "-ar", str(SR),
                        "-f", "f32le", "-"], capture_output=True)
    if r.returncode:
        lines = r.stderr.decode("utf-8", "replace").strip().splitlines()
        raise ValueError(lines[-1] if lines else f"ffmpeg exit {r.returncode}")
    return np.frombuffer(r.stdout, np.float32)


def lrc(path):
    """(lyrics_found, [(t, text)]) from the sidecar .lrc; credits and 'pure music' notes removed."""
    f = path.with_suffix(".lrc")
    if not f.exists():
        return False, []
    lines = []
    for ln in f.read_text(encoding="utf-8", errors="replace").splitlines():
        for mm, ss, txt in re.findall(r"\[(\d+):(\d+(?:\.\d+)?)\]([^\[]*)", ln):
            txt = txt.strip()
            if txt and "纯音乐" not in txt and not CREDIT.match(txt):
                lines.append((int(mm) * 60 + float(ss), txt))
    return True, sorted(lines)


def analyze(key, path, declared_instrumental):
    x = decode(path)
    if len(x) < SR:
        raise ValueError("decoded audio is shorter than 1 s")
    n = len(x) // SR
    fr = x[: n * SR].reshape(n, SR)
    rms = 20 * np.log10(np.sqrt((fr ** 2).mean(1)) + 1e-9)
    spec = np.abs(np.fft.rfft(fr * np.hanning(SR), axis=1))
    freqs = np.fft.rfftfreq(SR, 1 / SR)
    cent = (spec * freqs).sum(1) / (spec.sum(1) + 1e-9)
    h2 = int(SR * 0.01)
    m = len(x) // h2
    e = np.sqrt((x[: m * h2].reshape(m, h2) ** 2).mean(1))
    seg = np.maximum(0, np.diff(np.log(e + 1e-6)))[:6000]
    seg = seg - seg.mean()
    ac = np.correlate(seg, seg, "full")[len(seg) - 1:]
    lo, hi = int(60 / 180 / 0.01), int(60 / 60 / 0.01)
    bpm = 60 / ((lo + int(np.argmax(ac[lo:hi]))) * 0.01) if len(ac) > hi else None
    sm = np.convolve(rms, np.ones(4) / 4, "same")
    rises = [i for i in range(4, len(sm) - 1) if sm[i] - sm[i - 4] >= 5 and sm[i] > sm.max() - 18]
    rises = [r for i, r in enumerate(rises) if i == 0 or r - rises[i - 1] > 6]
    quiet_thr = np.percentile(sm[5:-5] if len(sm) > 12 else sm, 20)
    quiet, i = [], 0
    while i < len(sm):
        if sm[i] <= quiet_thr:
            j = i
            while j < len(sm) and sm[j] <= quiet_thr:
                j += 1
            if j - i >= 3:
                quiet.append([i, j])
            i = j
        else:
            i += 1
    feat = np.stack([(rms - rms.mean()) / (rms.std() + 1e-6), (cent - cent.mean()) / (cent.std() + 1e-6)], 1)
    w = 8
    nov = np.array([np.linalg.norm(feat[t - w:t].mean(0) - feat[t:t + w].mean(0)) if w <= t <= len(feat) - w else 0
                    for t in range(len(feat))])
    cps = []
    for t in np.argsort(-nov):
        if nov[t] < 0.8:
            break
        if all(abs(t - c) > 12 for c in cps):
            cps.append(int(t))
    found, lyr = lrc(path)
    sung = [{"t0": round(t, 2), "t1": round(min(lyr[k + 1][0] if k + 1 < len(lyr) else t + 6, t + 8), 2),
             "text": txt, "lang": lang(txt)} for k, (t, txt) in enumerate(lyr)]
    if sung:
        instrumental, source = False, "lrc"
    elif found or declared_instrumental:
        instrumental, source = True, "lrc" if found else "declared-instrumental"
    else:
        instrumental, source = None, "none"
    return {
        "key": key, "file": str(path), "duration": round(len(x) / SR, 2),
        "bpm_estimate": round(bpm, 1) if bpm else None,
        "loudness_db_per_s": [round(float(v), 1) for v in rms],
        "brightness_hz_per_s": [int(v) for v in cent],
        "peak_loudness_db": round(float(sm.max()), 1), "median_loudness_db": round(float(np.median(rms)), 1),
        "rises_s": rises, "quiet_windows_s": quiet, "change_points_s": sorted(cps),
        "sung_lines": sung, "instrumental": instrumental, "lyrics_source": source,
    }


def summarize(a):
    L = a["loudness_db_per_s"]
    prof = " ".join(str(int(np.mean(L[i:i + 10]))) for i in range(0, len(L), 10))
    kind = {True: "INSTRUMENTAL", False: "SUNG", None: "LYRICS UNKNOWN"}[a["instrumental"]]
    s = [f"### {a['key']}  ({Path(a['file']).name})",
         f"- duration {a['duration']}s, bpm~{a['bpm_estimate']}, median {a['median_loudness_db']} dB, "
         f"peak(4s) {a['peak_loudness_db']} dB, {kind}",
         f"- loudness per 10 s: {prof}",
         f"- change points (s): {a['change_points_s']}",
         f"- rises / hit points (s): {a['rises_s']}",
         f"- quiet windows (s): {a['quiet_windows_s'][:12]}"]
    if a["sung_lines"]:
        s.append(f"- sung from {a['sung_lines'][0]['t0']}s to {a['sung_lines'][-1]['t1']}s:")
        s += [f"  - {x['t0']:.1f}-{x['t1']:.1f} [{x['lang']}]: {x['text']}" for x in a["sung_lines"]]
    return "\n".join(s)


def slug(stem, taken):
    base = re.sub(r"[^\w]+", "_", stem).strip("_").lower() or "track"
    key, n = base, 2
    while key in taken:
        key, n = f"{base}_{n}", n + 1
    return key


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--library", action="append", default=[], help="directory scanned recursively (repeatable)")
    ap.add_argument("--track", action="append", default=[], metavar="KEY=PATH", help="explicit track (repeatable)")
    ap.add_argument("--instrumental", action="append", default=[], metavar="KEY",
                    help="declare a track without .lrc as instrumental (repeatable)")
    ap.add_argument("--output", required=True, help="tracks.json path")
    ap.add_argument("--summary", help="markdown summary for cue designers")
    args = ap.parse_args()
    items, seen = {}, set()
    for spec in args.track:
        key, _, path = spec.partition("=")
        p = Path(path).expanduser().resolve()
        items[key] = p
        seen.add(p)
    for root in args.library:
        for p in sorted(Path(root).expanduser().rglob("*")):
            if p.suffix.lower() in AUDIO and p.is_file() and p.resolve() not in seen:
                items[slug(p.stem, items)] = p.resolve()
                seen.add(p.resolve())
    if not items:
        ap.error("no audio files; pass --library DIR or --track KEY=PATH")
    playable, unplayable = {}, {}
    for key, p in items.items():
        try:
            playable[key] = analyze(key, p, key in args.instrumental)
            a = playable[key]
            kind = {True: "instrumental", False: f"sung ({len(a['sung_lines'])} lines)", None: "lyrics unknown"}
            print(f"OK   {key}: {a['duration']}s, {kind[a['instrumental']]}")
        except (ValueError, subprocess.SubprocessError) as exc:
            unplayable[key] = {"key": key, "file": str(p), "reason": str(exc)}
            print(f"SKIP {key}: {exc}")
    out = {"schema": "lovstudio/bgm-tracks/v1", "playable": playable, "unplayable": unplayable}
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    if args.summary:
        md = "# BGM library (user-provided; every file is in scope)\n\n## Playable\n\n"
        md += "\n\n".join(summarize(a) for a in playable.values())
        if unplayable:
            md += "\n\n## Unplayable (report to the user; do not use in the mix)\n\n"
            md += "\n".join(f"- {u['key']} ({Path(u['file']).name}): {u['reason']}" for u in unplayable.values())
        Path(args.summary).write_text(md + "\n", encoding="utf-8")
    print(f"{len(playable)} playable, {len(unplayable)} unplayable -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
