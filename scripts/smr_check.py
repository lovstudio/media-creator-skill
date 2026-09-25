#!/usr/bin/env python3
"""Speech-to-music ratio (SMR) per voice line, simulated with exactly the buses score_mix.py builds.

For every voice line: voice-active 100 ms frames, energy in 500-3000 Hz of the voice bus vs the
ducked music bus -> SMR median and p10 (dB). SMR is a floor against unintelligible speech, not a rule
that music must disappear, so the floor follows the mix intent at that line (cues.json mix_intents):
  clear   median >= 16 dB and p10 >= 8 dB (calibrated on an accepted Kailash mix)
  blend   median >= 10 dB (music stays present under the voice; provisional calibration)
  feature reported only; the intelligibility.py CER floor still applies
Also reports how loud the music under each line is relative to the level_db=0 bed.
Run it before rendering; a failing line means move, lower or re-automate the cue under it, or
choose a different intent for that moment on purpose.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import score_mix  # noqa: E402

SR = score_mix.SR
HOP = SR // 10


def band_db(x):
    n = len(x) // HOP
    fr = x[: n * HOP].reshape(n, HOP) * np.hanning(HOP)
    sp = np.abs(np.fft.rfft(fr, axis=1)) ** 2
    f = np.fft.rfftfreq(HOP, 1 / SR)
    m = (f >= 500) & (f <= 3000)
    return 10 * np.log10(sp[:, m].sum(1) + 1e-12)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    score_mix.add_mix_args(ap)
    ap.add_argument("--median-min", type=float, default=16.0, help="clear lines: SMR median floor, dB")
    ap.add_argument("--p10-min", type=float, default=8.0, help="clear lines: SMR 10th-percentile floor, dB")
    ap.add_argument("--blend-median-min", type=float, default=10.0, help="blend lines: SMR median floor, dB")
    ap.add_argument("--output", help="write rows and failures as JSON")
    args = ap.parse_args()
    sheet, tracks = score_mix.load_json(args.cues), score_mix.load_json(args.tracks)
    p = score_mix.mix_params(args, sheet)
    voice, _, music, _, report = score_mix.build_buses(args.voice, sheet, tracks, p, ambient=False)
    md = music.mean(1)
    vb, mb = band_db(voice), band_db(md)
    vact = vb > (np.percentile(vb, 95) - 30)
    rows, fails = [], []
    for v in report["voice"]:
        a, b = int(v["at"] * 10), int((v["at"] + v["dur"]) * 10)
        idx = [i for i in range(a, min(b, len(vb))) if vact[i]]
        if not idx:
            continue
        smr = vb[idx] - mb[idx]
        med, p10 = float(np.median(smr)), float(np.percentile(smr, 10))
        seg = md[int(v["at"] * SR):int((v["at"] + v["dur"]) * SR)]
        under = score_mix.rms_db(seg) - p["music_ref"] if len(seg) else float("nan")
        intent = score_mix.intent_at(sheet, v["at"], v["at"] + v["dur"])
        if intent == "clear":
            ok = med >= args.median_min and p10 >= args.p10_min
        elif intent == "blend":
            ok = med >= args.blend_median_min
        else:
            ok = None
        rows.append({"line": v["id"], "t0": v["at"], "intent": intent, "smr_median": round(med, 1),
                     "smr_p10": round(p10, 1), "music_under_re_bed": round(under, 1), "pass": ok})
        if ok is False:
            fails.append(v["id"])
    for r in rows:
        tag = {True: "PASS", False: "FAIL", None: "NOTE"}[r["pass"]]
        print(f"{tag} {str(r['line']):14s} @{r['t0']:7.1f} {r['intent']:7s} SMR med {r['smr_median']:5.1f}"
              f"  p10 {r['smr_p10']:5.1f}  music {r['music_under_re_bed']:+5.1f} dB re bed")
    print(f"RESULT {'PASS' if not fails else 'FAIL'}  failing lines: {fails}  (clear median>={args.median_min}, "
          f"p10>={args.p10_min}; blend median>={args.blend_median_min}; feature not gated)")
    if args.output:
        gate = {"clear": {"median_min": args.median_min, "p10_min": args.p10_min},
                "blend": {"median_min": args.blend_median_min}, "feature": None}
        Path(args.output).write_text(json.dumps({"params": p, "gate": gate, "rows": rows, "fails": fails},
                                                ensure_ascii=False, indent=1), encoding="utf-8")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
