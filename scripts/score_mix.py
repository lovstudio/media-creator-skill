#!/usr/bin/env python3
"""Mix a narrative film's stereo track from voice lines, optional ambience and multi-track BGM cues.

Voice lines are gain-matched to --voice-lufs and peak-limited. Music cues are cut from the analyzed
library (bgm_tracks.py), loudness-matched with level_db, faded, automated with env points and ducked
by the voice bus (ducking.py). Ducking depth follows the director's mix intent per moment:
clear (music steps back, default), blend (music stays present under the voice) or feature (music
leads and the voice rides on top); intents change over 250 ms ramps, never as gain steps.
Ambience ducks at half depth; a chunk from the same source clip as an overlapping voice line is
dropped, otherwise the same words play twice.

Mastering is linear: limit peaks, measure I/TP with ebur128, apply one static gain to --target-lufs,
and lower the limiter ceiling until the true peak stays under --tp-ceiling. loudnorm is not used: its
single-pass mode turns dynamic whenever the linear gain would break the true-peak target. Master to
-3 dBTP by default because AAC encoding raises true peak afterwards.

voice.json (paths resolve relative to the file):
  {"duration": s, "lines": [{"id", "file", "at", "lufs"?, "source"?}],
   "ambient": [{"file", "at", "dur", "ss"?, "level_db"?, "source"?}]}
cues.json:  {"cues": [{"id", "track", "track_in", "at", "dur", "level_db" | "gain_db",
                       "fade_in"?, "fade_out"?, "env"?: [[t_rel, db], ...], "rationale"}],
             "mix_intents"?: [{"t0", "t1", "intent": "clear|blend|feature", "reason",
                               "duck_db"?, "band_cut_db"?}]}
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ducking  # noqa: E402

SR = ducking.SR
# (broadband duck, extra speech-band duck) in dB. clear comes from --duck-db/--band-cut-db; blend and
# feature are starting points to calibrate by ear and with smr_check/intelligibility, not fixed law.
INTENTS = {"blend": (-7.0, -6.0), "feature": (-3.0, -4.0)}


def decode(path, ch=1, ss=None, dur=None, af=None):
    cmd = ["ffmpeg", "-v", "error", "-nostdin"]
    if ss is not None:
        cmd += ["-ss", f"{ss:.3f}"]
    if dur is not None:
        cmd += ["-t", f"{dur:.3f}"]
    cmd += ["-i", str(path), "-map", "0:a:0", "-ac", str(ch), "-ar", str(SR)]
    if af:
        cmd += ["-af", af]
    cmd += ["-f", "f32le", "-"]
    x = np.frombuffer(subprocess.run(cmd, capture_output=True, check=True).stdout, np.float32).copy()
    return x.reshape(-1, ch) if ch > 1 else x


def ramp(x, fin, fout):
    x = x.copy()
    n_in, n_out = min(int(fin * SR), len(x) // 2), min(int(fout * SR), len(x) // 2)
    if n_in:
        x[:n_in] = (x[:n_in].T * np.linspace(0, 1, n_in, dtype=np.float32)).T
    if n_out:
        x[-n_out:] = (x[-n_out:].T * np.linspace(1, 0, n_out, dtype=np.float32)).T
    return x


def place(bus, x, at):
    i = int(round(at * SR))
    if i < 0:
        x, i = x[-i:], 0
    j = min(len(bus), i + len(x))
    if j > i:
        bus[i:j] += x[: j - i]


def rms_db(x):
    return float(20 * np.log10(np.sqrt(np.mean(np.square(x))) + 1e-9))


def measure_i_tp(path):
    """Integrated loudness (LUFS) and true peak (dBTP) from ffmpeg ebur128."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-i", str(path), "-af", "ebur128=peak=true",
                        "-f", "null", "-"], capture_output=True, text=True, check=True)
    tail = r.stderr[r.stderr.rfind("Summary:"):]
    return float(tail.split("I:")[1].split()[0]), float(tail.split("Peak:")[1].split()[0])


def write_wav(path, arr):
    ch = 2 if arr.ndim == 2 else 1
    subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-f", "f32le", "-ar", str(SR), "-ac", str(ch),
                    "-i", "-", "-c:a", "pcm_s24le", str(path)],
                   input=np.ascontiguousarray(arr, np.float32).tobytes(), check=True)


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def add_mix_args(p):
    p.add_argument("--voice", required=True, help="voice.json with lines (and optional ambient)")
    p.add_argument("--cues", required=True, help="cue sheet JSON")
    p.add_argument("--tracks", required=True, help="tracks.json from bgm_tracks.py")
    p.add_argument("--voice-lufs", type=float, default=-20.0, help="per-line voice loudness (default -20)")
    p.add_argument("--max-voice-boost", type=float, default=14.0, help="max gain added to a quiet line, dB")
    p.add_argument("--voice-limit", type=float, default=-6.0, help="voice bus peak ceiling, dBFS")
    p.add_argument("--music-ref", type=float, default=-27.0,
                   help="RMS dBFS of a level_db=0 music bed before ducking (default -27)")
    p.add_argument("--duck-db", type=float, help="clear-intent broadband duck under speech (sheet value, else -13)")
    p.add_argument("--band-cut-db", type=float, help="clear-intent extra 500-3000 Hz duck (sheet value, else -8)")


def mix_params(args, sheet):
    return {
        "voice_lufs": args.voice_lufs, "max_voice_boost": args.max_voice_boost,
        "voice_limit": args.voice_limit, "music_ref": args.music_ref,
        "duck_db": args.duck_db if args.duck_db is not None else sheet.get("duck_db", -13.0),
        "band_cut_db": args.band_cut_db if args.band_cut_db is not None else sheet.get("band_cut_db", -8.0),
    }


def intent_at(sheet, t0, t1):
    """Mix intent covering at least half of [t0, t1]; clear otherwise."""
    best, cover = "clear", 0.0
    for r in sheet.get("mix_intents", []):
        ov = max(0.0, min(t1, r["t1"]) - max(t0, r["t0"]))
        if ov > cover:
            best, cover = r["intent"], ov
    return best if cover >= 0.5 * (t1 - t0) else "clear"


def depth_curves(sheet, n, p):
    """Per-sample duck depths from mix_intents (scalars when none are set), ramped over 250 ms."""
    ranges = sheet.get("mix_intents", [])
    if not ranges:
        return p["duck_db"], p["band_cut_db"]
    hop, m = 480, n // 480 + 1
    duck, band = np.full(m, p["duck_db"]), np.full(m, p["band_cut_db"])
    for r in ranges:
        if r["intent"] not in ("clear", *INTENTS):
            raise SystemExit(f"unknown mix intent '{r['intent']}' (use clear, blend or feature)")
        d, b = INTENTS.get(r["intent"], (p["duck_db"], p["band_cut_db"]))
        i, j = int(r["t0"] * 100), int(r["t1"] * 100)
        duck[i:j], band[i:j] = r.get("duck_db", d), r.get("band_cut_db", b)
    ker = np.ones(25) / 25
    duck = np.convolve(np.pad(duck, 12, mode="edge"), ker, "valid")
    band = np.convolve(np.pad(band, 12, mode="edge"), ker, "valid")
    return np.repeat(duck, hop)[:n].astype(np.float32), np.repeat(band, hop)[:n].astype(np.float32)


def build_buses(voice_path, sheet, tracks, p, ambient=True):
    """Return voice (limited), ambient (ducked), music (ducked, stereo), envelope and a report."""
    plan = load_json(voice_path)
    base = Path(voice_path).resolve().parent
    n = int(round(plan["duration"] * SR))
    voice = np.zeros(n, np.float32)
    amb = np.zeros(n, np.float32)
    music = np.zeros((n, 2), np.float32)
    report = {"params": p, "voice": [], "ambient": [], "music": []}
    spans = []
    for v in plan["lines"]:
        path = base / v["file"]
        lufs = v.get("lufs")
        if lufs is None:
            lufs = measure_i_tp(path)[0]
        x = decode(path)
        g = min(p["voice_lufs"] - lufs, p["max_voice_boost"])
        place(voice, ramp(x * 10 ** (g / 20), 0.01, 0.02), v["at"])
        dur = len(x) / SR
        spans.append((v.get("source"), v["at"] - 1.0, v["at"] + dur + 1.0))
        report["voice"].append({"id": v.get("id"), "at": v["at"], "dur": round(dur, 3), "gain_db": round(g, 1)})
    if ambient:
        pad = 0.3
        for a in plan.get("ambient", []):
            src = a.get("source")
            if src is not None and any(s == src and t0 < a["at"] + a["dur"] and a["at"] < t1 for s, t0, t1 in spans):
                report["ambient"].append({**a, "used": False, "reason": "same source as an overlapping voice line"})
                continue
            ss = a.get("ss", 0.0)
            pre = min(pad, ss)
            x = decode(base / a["file"], ss=ss - pre, dur=a["dur"] + pre + pad, af="highpass=f=60,lowpass=f=12000")
            if len(x) < SR * 0.2:
                continue
            g = float(np.clip(a.get("level_db", -32.0) - rms_db(x), -30, 12))
            place(amb, ramp(x * 10 ** (g / 20), pre + 0.1, pad + 0.1), a["at"] - pre)
            report["ambient"].append({**a, "used": True, "gain_db": round(g, 1)})
    playable = tracks["playable"]
    for c in sheet["cues"]:
        x = decode(playable[c["track"]]["file"], ch=2, ss=c["track_in"], dur=c["dur"])
        if "level_db" in c:
            mono = x.mean(1)
            act = mono[np.abs(mono) > 1e-4]
            g = float(np.clip(p["music_ref"] + c["level_db"] - rms_db(act if len(act) else mono), -30, 18))
        else:
            g = float(c.get("gain_db", c.get("gain", 0.0)))
        x = x * 10 ** (g / 20)
        if c.get("env"):
            pts = np.array(c["env"], dtype=np.float64)
            env = np.interp(np.arange(len(x)) / SR, pts[:, 0], pts[:, 1])
            x = (x.T * (10 ** (env / 20)).astype(np.float32)).T
        place(music, ramp(x, c.get("fade_in", 1.5), c.get("fade_out", 2.5)), c["at"])
        report["music"].append({"id": c.get("id"), "track": c["track"], "at": c["at"], "gain_db": round(g, 1)})
    voice, gr = ducking.peak_limit(voice, p["voice_limit"])
    report["voice_limiter_max_gr_db"] = round(gr, 1)
    duck_db, band_cut_db = depth_curves(sheet, n, p)
    music, env = ducking.duck(music, voice, duck_db, band_cut_db)
    amb = amb * 10 ** ((duck_db * 0.5) * env / 20)
    report["mix_intents"] = sheet.get("mix_intents", [])
    return voice, amb, music, env, report


def master(mixed, work, target, tp_ceiling):
    """Linear master: limit peaks, measure, one static gain; retry with a lower ceiling if TP is over."""
    pre = work / "premix.wav"
    write_wav(pre, mixed)
    i0, _ = measure_i_tp(pre)
    ceiling = tp_ceiling - (target - i0) - 0.7
    for attempt in range(1, 6):
        lim, gr = ducking.peak_limit(mixed, ceiling, lookahead_ms=3.0, release_ms=120.0)
        write_wav(pre, lim)
        i, tp = measure_i_tp(pre)
        gain = target - i
        over = tp + gain - tp_ceiling
        print(f"master try {attempt}: ceiling {ceiling:.2f} dBFS, GR {gr:.1f} dB, I {i:.2f}, TP {tp:.2f} "
              f"-> gain {gain:+.2f}, TP after {tp + gain:.2f}")
        if over <= 0:
            break
        ceiling -= over + 0.15
    info = {"mode": "linear static gain", "limiter_ceiling_dbfs": round(ceiling, 2), "limiter_max_gr_db": round(gr, 1),
            "pre_I": round(i, 2), "pre_TP": round(tp, 2), "gain_db": round(gain, 2), "attempts": attempt}
    return lim * 10 ** (gain / 20), info


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_mix_args(ap)
    ap.add_argument("--out-dir", required=True, help="writes final-mix.wav and mix-report.json here")
    ap.add_argument("--target-lufs", type=float, default=-16.0)
    ap.add_argument("--tp-ceiling", type=float, default=-3.0,
                    help="master true-peak ceiling, dBTP; keep headroom for AAC overshoot (default -3)")
    ap.add_argument("--stems", action="store_true", help="also write stem-voice/ambient/music.wav for diagnosis")
    args = ap.parse_args()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    sheet, tracks = load_json(args.cues), load_json(args.tracks)
    p = mix_params(args, sheet)
    voice, amb, music, _, report = build_buses(args.voice, sheet, tracks, p)
    if args.stems:
        for name, arr in (("voice", voice), ("ambient", amb), ("music", music)):
            write_wav(out / f"stem-{name}.wav", arr)
    mixed = music + np.stack([voice + amb, voice + amb], 1)
    with tempfile.TemporaryDirectory() as tmp:
        final, report["master"] = master(mixed, Path(tmp), args.target_lufs, args.tp_ceiling)
    path = out / "final-mix.wav"
    write_wav(path, final)
    i, tp = measure_i_tp(path)
    ok = abs(i - args.target_lufs) <= 0.5 and tp <= args.tp_ceiling + 0.05
    report["final"] = {"file": str(path), "I": i, "TP": tp, "target_lufs": args.target_lufs,
                       "tp_ceiling": args.tp_ceiling, "pass": ok}
    (out / "mix-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{'PASS' if ok else 'FAIL'} {path}  I {i:.2f} LUFS  TP {tp:.2f} dBTP")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
