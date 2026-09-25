#!/usr/bin/env python3
"""Validate a multi-track BGM cue sheet against the film and the analyzed library (stdlib only).

ERROR blocks the mix:
  - unknown or unplayable track; source range outside the track; cue outside the film; fades > cue
  - a cue without a story/emotion rationale
  - more than 2 cues sounding at once
  - > 1.0 s of sung lyrics in the dialogue language under dialogue (Chinese lyrics under Chinese speech);
    this holds for every mix intent, feature moments included
  - a mix_intents range with an unknown intent, outside the film, or overlapping another range
WARN needs a written reason or a fix:
  - other-language singing, or a track with unknown lyrics, under dialogue for > 0.5 s
  - lyrics under an on-screen text card, unless the cue sets "lyric_feature": true (the lyric IS the point)
  - overlapping cues that are not a real cross-fade (overlap >= 1.0 s, both sides faded)
  - entry/exit inside a loud passage of the track with a fade < 2 s
  - a music-free span longer than --max-gap that is not declared in "silences" with a reason
  - fewer distinct tracks than --min-tracks
  - a blend/feature range without a reason (music under the voice is a deliberate choice)
  - a run of >= --card-run short text cards (each <= --card-max s, gaps <= 1 s): transitions need
    breathing room (holds, music-led interludes, J/L-cuts, longer dissolves), not a card chain
INFO: library usage, coverage, declared silences, same track back-to-back.

film.json:  {"duration", "dialogue_language"?: "zh", "voice_spans": [{"t0", "t1"}],
             "text_spans"?: [{"t0", "t1", "text"}]}
cues.json:  {"cues": [{"id", "track", "track_in", "at", "dur", "fade_in", "fade_out", "rationale",
                       "lyric_feature"?}], "silences"?: [{"t0", "t1", "reason"}],
             "mix_intents"?: [{"t0", "t1", "intent": "clear|blend|feature", "reason"}]}
"""
import argparse
import json
import re
import sys
from pathlib import Path


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


def overlap(a0, a1, b0, b1):
    return max(0.0, min(a1, b1) - max(a0, b0))


def lyric_spans(cue, track):
    """Sung lines of a track mapped onto film time and clipped to the cue."""
    out = []
    for s in track.get("sung_lines", []):
        a = cue["at"] + (s["t0"] - cue["track_in"])
        b = cue["at"] + (s["t1"] - cue["track_in"])
        a, b = max(a, cue["at"]), min(b, cue["at"] + cue["dur"])
        if b > a:
            out.append((a, b, s.get("lang") or lang(s["text"])))
    return out


def card_runs(texts, run=3, card_max=5.0, gap=1.0):
    """Runs of >= run consecutive short text cards with small gaps between them."""
    out, cur = [], []
    for t0, t1 in sorted(texts):
        short = t1 - t0 <= card_max
        if short and cur and t0 - cur[-1][1] <= gap:
            cur.append((t0, t1))
            continue
        if len(cur) >= run:
            out.append(cur)
        cur = [(t0, t1)] if short else []
    if len(cur) >= run:
        out.append(cur)
    return out


def validate(sheet, tracks, film, min_tracks=3, max_gap=6.0, card_run=3, card_max=5.0):
    errors, warnings, info = [], [], []
    cues = sheet["cues"]
    playable, unplayable = tracks.get("playable", {}), tracks.get("unplayable", {})
    dur = film["duration"]
    speech = film.get("dialogue_language", "zh")
    voice = [(v["t0"], v["t1"]) for v in film.get("voice_spans", [])]
    texts = [(t["t0"], t["t1"]) for t in film.get("text_spans", [])]
    for c in cues:
        cid = c.get("id", "?")
        if not str(c.get("rationale", "")).strip():
            errors.append(f"{cid}: no rationale; every cue needs a story/emotion reason for this track here")
        tr = playable.get(c["track"])
        if not tr:
            why = unplayable.get(c["track"], {}).get("reason", "not in the analyzed library")
            errors.append(f"{cid}: track '{c['track']}' is not playable ({why})")
            continue
        if c["track_in"] < 0 or c["track_in"] + c["dur"] > tr["duration"] + 0.05:
            errors.append(f"{cid}: source range {c['track_in']:.1f}+{c['dur']:.1f}s exceeds track duration {tr['duration']}s")
        if c["at"] < -0.01 or c["at"] + c["dur"] > dur + 0.05:
            errors.append(f"{cid}: film range {c['at']:.1f}-{c['at'] + c['dur']:.1f}s outside 0-{dur}s")
        if c.get("fade_in", 0) + c.get("fade_out", 0) > c["dur"]:
            errors.append(f"{cid}: fades longer than the cue")
        loud = tr.get("loudness_db_per_s") or []
        if loud:
            thr = tr["median_loudness_db"] - 3

            def lv(t):
                return loud[int(max(0, min(len(loud) - 1, t)))]
            if lv(c["track_in"] + 0.5) > thr and c.get("fade_in", 0) < 2:
                warnings.append(f"{cid}: enters inside a loud passage ({lv(c['track_in'] + 0.5)} dB at "
                                f"{c['track_in']:.1f}s) with fade_in {c.get('fade_in', 0)}s")
            end = c["track_in"] + c["dur"]
            if lv(end - 0.5) > thr and c.get("fade_out", 0) < 2 and end < tr["duration"] - 1:
                warnings.append(f"{cid}: exits mid-passage ({lv(end - 0.5)} dB at {end:.1f}s) "
                                f"with fade_out {c.get('fade_out', 0)}s")
        spans = lyric_spans(c, tr)
        same = sum(overlap(a, b, v0, v1) for a, b, lg in spans if lg == speech for v0, v1 in voice)
        other = sum(overlap(a, b, v0, v1) for a, b, lg in spans if lg != speech for v0, v1 in voice)
        if same > 1.0:
            errors.append(f"{cid}: {same:.1f}s of sung '{speech}' lyrics under '{speech}' dialogue "
                          f"(track {c['track']}); move the cue or use an instrumental passage")
        elif other > 0.5:
            warnings.append(f"{cid}: {other:.1f}s of singing/chant in another language under dialogue (track {c['track']})")
        if tr.get("instrumental") is None and not tr.get("sung_lines"):
            unknown = sum(overlap(c["at"], c["at"] + c["dur"], v0, v1) for v0, v1 in voice)
            if unknown > 0.5:
                warnings.append(f"{cid}: lyrics of '{c['track']}' are unknown (no .lrc) and it plays under "
                                f"{unknown:.1f}s of dialogue; confirm it is instrumental or add lyrics")
        on_text = sum(overlap(a, b, t0, t1) for a, b, _ in spans for t0, t1 in texts)
        if on_text > 0.5:
            if c.get("lyric_feature"):
                info.append(f"{cid}: lyrics over text cards for {on_text:.1f}s, marked lyric_feature")
            else:
                warnings.append(f"{cid}: {on_text:.1f}s of lyrics compete with on-screen text; move it, or set "
                                f"lyric_feature=true when the lyric IS the point and say why in the rationale")
    step, n_steps = 0.1, int(round(dur * 10))
    counts = [sum(1 for c in cues if c["at"] <= k * step < c["at"] + c["dur"]) for k in range(n_steps)]
    if counts and max(counts) > 2:
        errors.append(f"up to {max(counts)} cues sound at once (max 2)")
    gaps, start = [], None
    for k, n in enumerate(counts + [1]):
        if n == 0 and start is None:
            start = k * step
        elif n and start is not None:
            if k * step - start > max_gap:
                gaps.append((round(start, 1), round(min(k * step, dur), 1)))
            start = None
    silences = sheet.get("silences", [])
    for s in silences:
        if not str(s.get("reason", "")).strip():
            warnings.append(f"declared silence {s['t0']}-{s['t1']}s has no reason")
    for g0, g1 in gaps:
        declared = sum(overlap(g0, g1, s["t0"], s["t1"]) for s in silences)
        if declared >= 0.5 * (g1 - g0):
            info.append(f"deliberate silence {g0}-{g1}s")
        else:
            warnings.append(f"music-free span {g0}-{g1}s ({g1 - g0:.1f}s) is not declared in 'silences'; "
                            f"cover it or declare why the film stays dry here")
    ordered = sorted(cues, key=lambda c: c["at"])
    for a, b in zip(ordered, ordered[1:]):
        ov = a["at"] + a["dur"] - b["at"]
        if ov > 0:
            if ov < 1.0:
                warnings.append(f"{a['id']}->{b['id']}: overlap {ov:.2f}s is too short for a cross-fade; "
                                f"cross-fade >= 1 s or cut on a beat without overlap")
            elif a.get("fade_out", 0) < 1.0 or b.get("fade_in", 0) < 1.0:
                warnings.append(f"{a['id']}->{b['id']}: overlap {ov:.1f}s but fades are "
                                f"{a.get('fade_out', 0)}/{b.get('fade_in', 0)}s")
        if a["track"] == b["track"] and ov > -3:
            info.append(f"{a['id']}->{b['id']}: same track back-to-back ({a['track']})")
    intents = sorted(sheet.get("mix_intents", []), key=lambda r: r["t0"])
    for r in intents:
        span = f"mix intent {r.get('intent')} {r['t0']}-{r['t1']}s"
        if r.get("intent") not in ("clear", "blend", "feature"):
            errors.append(f"{span}: unknown intent (use clear, blend or feature)")
        if not 0 <= r["t0"] < r["t1"] <= dur + 0.05:
            errors.append(f"{span}: range outside the film or empty")
        if r.get("intent") in ("blend", "feature") and not str(r.get("reason", "")).strip():
            warnings.append(f"{span}: no reason; say why music should stay under the voice here")
    for a, b in zip(intents, intents[1:]):
        if b["t0"] < a["t1"]:
            errors.append(f"mix intents overlap at {b['t0']}-{a['t1']}s")
    if intents:
        info.append("mix intents: " + ", ".join(f"{r.get('intent')} {r['t0']}-{r['t1']}s" for r in intents))
    for run in card_runs(texts, card_run, card_max):
        warnings.append(f"{len(run)} short text cards back to back {run[0][0]:.1f}-{run[-1][1]:.1f}s; give the "
                        f"transition room (hold, music-led interlude, J/L-cut, longer dissolve)")
    used = sorted({c["track"] for c in cues})
    cover = sum(1 for n in counts if n) / max(1, len(counts)) * 100
    info.append(f"distinct tracks {len(used)} of {len(playable)} playable in the library; "
                f"{len(cues)} cues; music coverage {cover:.0f}%")
    if unplayable:
        info.append(f"unplayable library files (report them, do not drop silently): {sorted(unplayable)}")
    if len(used) < min_tracks:
        warnings.append(f"only {len(used)} distinct tracks; a narrative film normally mixes >= {min_tracks} "
                        f"(state why a single score carries the whole film)")
    return {"errors": errors, "warnings": warnings, "info": info}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cues", required=True, help="cue sheet JSON")
    ap.add_argument("--tracks", required=True, help="tracks.json from bgm_tracks.py")
    ap.add_argument("--film", required=True, help="film.json with duration, voice_spans and text_spans")
    ap.add_argument("--min-tracks", type=int, default=3, help="warn below this many distinct tracks (default 3)")
    ap.add_argument("--max-gap", type=float, default=6.0, help="undeclared music-free span limit, s (default 6)")
    ap.add_argument("--card-run", type=int, default=3, help="warn on this many short cards in a row (default 3)")
    ap.add_argument("--card-max", type=float, default=5.0, help="a text card this short counts, s (default 5)")
    ap.add_argument("--json", dest="json_out", help="write the report as JSON")
    args = ap.parse_args()
    load = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))  # noqa: E731
    out = validate(load(args.cues), load(args.tracks), load(args.film), args.min_tracks, args.max_gap,
                   args.card_run, args.card_max)
    for key in ("errors", "warnings", "info"):
        for m in out[key]:
            print(f"{key[:-1].upper() if key != 'info' else 'INFO':7s} {m}")
    print(f"RESULT {'FAIL' if out['errors'] else 'PASS'} ({len(out['errors'])} errors, {len(out['warnings'])} warnings)")
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return 1 if out["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
