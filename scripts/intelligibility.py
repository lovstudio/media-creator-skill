#!/usr/bin/env python3
"""Objective proxy for "the music masks the voice": Whisper CER of a mix vs a voice-only floor.

Transcribes the mix, scores every SRT cue by character error rate (CER, capped at 1.0) of the words
heard in that window, and compares the mean with the same score on the voice-only stem (the floor:
Whisper's own error without music). Gate: mean CER of the mix - floor <= --max-delta over the cues
scored in both. Decoding is deterministic (temperature 0) so a rerun gives the same verdict.
Whisper repetition loops ("icangoicango...") are an ASR failure, not masking evidence: such cues are
listed under asr_loops for listening and left out of both means. Per-cue CER is noisy, so the largest
per-cue regressions are only listed for listening, never gated.

--floor accepts an audio file (transcribed now; save it with --floor-output to reuse) or a JSON
written earlier by this script. Backends: mlx-whisper (Apple Silicon) or openai-whisper. Run with a
Python that already has one installed; set HF_HUB_OFFLINE=1 when the model is cached locally.
"""
import argparse
import json
import re
import sys
from pathlib import Path

MODELS = {"mlx": "mlx-community/whisper-large-v3-mlx", "openai": "large-v3"}


def norm(s):
    return re.sub(r"[^一-鿿0-9a-zA-Z]", "", s)


def cer(ref, hyp):
    r, h = norm(ref), norm(hyp)
    if not r:
        return 0.0
    d = list(range(len(h) + 1))
    for i, rc in enumerate(r, 1):
        prev, d[0] = d[0], i
        for j, hc in enumerate(h, 1):
            cur = min(d[j] + 1, d[j - 1] + 1, prev + (rc != hc))
            prev, d[j] = d[j], cur
    return d[len(h)] / len(r)


def asr_loop(ref, hyp):
    r, h = norm(ref), norm(hyp)
    return len(h) > 2 * len(r) + 4 and re.search(r"(.{2,8})\1{3,}", h) is not None


def parse_srt(path):
    def sec(t):
        h, m, s = t.replace(",", ".").split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)
    cues = []
    text = Path(path).read_text(encoding="utf-8-sig")
    for block in re.split(r"\n\s*\n", text.replace("\r\n", "\n").strip()):
        lines = block.strip().split("\n")
        for k, ln in enumerate(lines):
            m = re.match(r"(\d+:\d+:\d+[,.]\d+)\s*-->\s*(\d+:\d+:\d+[,.]\d+)", ln)
            if m:
                cues.append((sec(m.group(1)), sec(m.group(2)), "".join(lines[k + 1:])))
                break
    return cues


def backend_name(choice):
    if choice != "auto":
        return choice
    try:
        import mlx_whisper  # noqa: F401
        return "mlx"
    except ImportError:
        pass
    try:
        import whisper  # noqa: F401
        return "openai"
    except ImportError:
        sys.exit("no Whisper backend: install mlx-whisper or openai-whisper in this Python, "
                 "or run the script with an existing venv that has one")


def transcribe(audio, backend, model, language):
    kw = {"language": language, "word_timestamps": True, "condition_on_previous_text": False, "temperature": 0.0}
    if backend == "mlx":
        import mlx_whisper
        r = mlx_whisper.transcribe(str(audio), path_or_hf_repo=model, **kw)
    else:
        import whisper
        r = whisper.load_model(model).transcribe(str(audio), **kw)
    return [w for s in r["segments"] for w in s.get("words", [])]


def score(audio, cues, backend, model, language):
    words = transcribe(audio, backend, model, language)
    rows = []
    for a, b, text in cues:
        heard = "".join(w["word"].strip() for w in words if a - 0.3 <= (w["start"] + w["end"]) / 2 <= b + 0.3)
        rows.append({"t": round(a, 2), "sub": text, "asr": heard, "cer": round(min(1.0, cer(text, heard)), 3),
                     "asr_loop": asr_loop(text, heard)})
    return {"mix": str(audio), "mean_cer": round(mean_cer(rows), 4), "rows": rows}


def mean_cer(rows):
    kept = [min(1.0, r["cer"]) for r in rows if not asr_loop(r["sub"], r["asr"])]
    return sum(kept) / max(1, len(kept))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mix", required=True, help="final mix (WAV or any decodable audio/video)")
    ap.add_argument("--srt", required=True, help="subtitles on the same timeline")
    ap.add_argument("--output", required=True, help="JSON report")
    ap.add_argument("--floor", help="voice-only stem to transcribe, or a JSON from an earlier run")
    ap.add_argument("--floor-output", help="save the floor transcription JSON for reuse")
    ap.add_argument("--max-delta", type=float, default=0.02, help="allowed mean CER above the floor (default 0.02)")
    ap.add_argument("--language", default="zh")
    ap.add_argument("--backend", choices=["auto", "mlx", "openai"], default="auto")
    ap.add_argument("--model", help="model id (default per backend: large-v3)")
    args = ap.parse_args()
    backend = backend_name(args.backend)
    model = args.model or MODELS[backend]
    cues = parse_srt(args.srt)
    rep = score(args.mix, cues, backend, model, args.language)
    rep.update({"srt": args.srt, "backend": backend, "model": model, "language": args.language})
    floor = None
    if args.floor:
        if args.floor.endswith(".json"):
            floor = json.loads(Path(args.floor).read_text(encoding="utf-8"))
        else:
            floor = score(args.floor, cues, backend, model, args.language)
            if args.floor_output:
                Path(args.floor_output).write_text(json.dumps(floor, ensure_ascii=False, indent=1), encoding="utf-8")
    if floor:
        by_t = {r["t"]: r for r in floor["rows"]}
        loops = [r for r in rep["rows"] if asr_loop(r["sub"], r["asr"])
                 or (r["t"] in by_t and asr_loop(by_t[r["t"]]["sub"], by_t[r["t"]]["asr"]))]
        paired = [(r, by_t[r["t"]]) for r in rep["rows"] if r["t"] in by_t and r not in loops]
        mix_mean = mean_cer([m for m, _ in paired])
        floor_mean = mean_cer([f for _, f in paired])
        delta = mix_mean - floor_mean
        worse = sorted(({"t": m["t"], "sub": m["sub"], "asr": m["asr"],
                         "delta": round(min(1.0, m["cer"]) - min(1.0, f["cer"]), 3)} for m, f in paired),
                       key=lambda r: -r["delta"])
        rep.update({"floor": {"source": args.floor, "mean_cer": round(mean_cer(floor["rows"]), 4)},
                    "paired_cues": len(paired), "paired_mix_cer": round(mix_mean, 4),
                    "paired_floor_cer": round(floor_mean, 4), "delta": round(delta, 4),
                    "max_delta": args.max_delta, "pass": delta <= args.max_delta,
                    "asr_loops": [{"t": r["t"], "sub": r["sub"], "asr": r["asr"][:60]} for r in loops],
                    "largest_regressions": [r for r in worse if r["delta"] > 0][:8]})
    Path(args.output).write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"mix mean CER {rep['mean_cer']:.3f} over {len(rep['rows'])} cues")
    if not floor:
        print("RESULT NO-GATE (pass --floor with the voice-only stem to gate masking)")
        return 0
    print(f"paired {rep['paired_cues']} cues: mix {rep['paired_mix_cer']:.3f}  floor {rep['paired_floor_cer']:.3f}  "
          f"delta {rep['delta']:+.3f}  (max {args.max_delta})")
    for r in rep["asr_loops"]:
        print(f"  asr loop {r['t']:7.2f}s (excluded; listen) | {r['sub']} | {r['asr']}")
    for r in rep["largest_regressions"]:
        print(f"  listen {r['t']:7.2f}s  +{r['delta']:.2f} | {r['sub']} | {r['asr']}")
    print(f"RESULT {'PASS' if rep['pass'] else 'FAIL'}")
    return 0 if rep["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
