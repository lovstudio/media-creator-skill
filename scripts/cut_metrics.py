#!/usr/bin/env python3
"""Measure and gate fragmentation of a narrative cut and its score together (stdlib only).

A film can pass every local gate (breath, readability, intelligibility) and still feel like a mosaic:
each added cutaway, gap patch or sting cue looks fine alone. This counts how often picture, story time
and music change, compares the counts with caps, and (with --baseline) refuses fixes that raise them.

Picture  layers (consecutive shots with the same shot/source key merged), ASL = duration / layers,
         shots under 3 s, clip switches per minute, capture-time jumps back of more than 30 min
         (shots marked "flashback": true are a deliberate memory segment: they are left out of the
         jump count, which resumes from the last present-day shot, and reported as "flashbacks")
Words    text cards, chapters, a through-line of at most five sentences
Music    cues, tracks, track changes (each time a different track takes over, the first entry
         included), median cue length, tracks per chapter, track changes away from a chapter or scene
         boundary, cross-fades shorter than --min-change-xfade-s at a track change

The default caps come from the Kailash v0.4 plan for a film of about 8 minutes, set after the author
judged v0.3 too fragmented. They are provisional: over-cap values print as WARN and exit 0 unless
--strict is given. The track-change cross-fade floor is 1 s, the shortest handoff in the accepted
Kailash final (1-3 s, median 1.5 s) and the cross-fade floor validate_cues.py already applies.

film.json: {"duration", "shots": [{"t0", "t1", "source", "shot"?, "captured_at"?, "black"?,
            "transition_in"?, "flashback"?}], "text_spans"?, "chapters"?: [{"t"}],
            "scenes"?: [{"t0", "t1"}], "throughline"?: ["sentence", ...]}
captured_at is ISO 8601 or YYYYMMDD_HHMMSS. cues.json is the cue sheet validate_cues.py reads.
"""
import argparse
import json
import re
import statistics
import sys
from datetime import datetime
from pathlib import Path

CAPS = {
    "asl_min_s": 9.0, "short_shots_max": 3, "time_jumps_back_max": 1, "clip_switches_per_min_max": 3.5,
    "text_cards_max": 18, "chapters_max": 5, "tracks_max": 4, "cues_max": 9, "track_changes_max": 7,
    "median_cue_min_s": 40.0,
}
MIN_CHANGE_XFADE_S = 1.0
RAISE_CHECK = [("picture", "layers"), ("picture", "shots_under_3s"), ("picture", "clip_switches"),
               ("picture", "time_jumps_back"), ("words", "text_cards"), ("music", "cues"),
               ("music", "tracks"), ("music", "track_changes")]


def minutes(stamp):
    if not stamp:
        return None
    s = str(stamp)
    m = re.match(r"(\d{8})_(\d{6})$", s)
    dt = datetime.strptime("".join(m.groups()), "%Y%m%d%H%M%S") if m else datetime.fromisoformat(s)
    return dt.timestamp() / 60


def picture(film):
    dur = film["duration"]
    shots = sorted(film.get("shots", []), key=lambda s: s["t0"])
    merged, jump_cuts = [], 0
    for s in shots:
        key = ("black",) if s.get("black") else (s.get("shot") or s.get("source"),)
        if merged and merged[-1]["key"] == key and key != ("black",):
            merged[-1]["t1"] = s["t1"]
            jump_cuts += 1
        else:
            merged.append({**s, "key": key})
    pics = [m for m in merged if m["key"] != ("black",)]
    lens = [m["t1"] - m["t0"] for m in pics]
    switches, back, prev_src, prev_min = 0, 0, None, None
    for m in pics:
        src = m.get("source")
        if src and src != prev_src:
            switches += 1
            k = None if m.get("flashback") else minutes(m.get("captured_at"))
            if prev_min is not None and k is not None and prev_min - k > 30:
                back += 1
            prev_min = k if k is not None else prev_min
        prev_src = src or prev_src
    flashbacks = sum(1 for a, b in zip([{}] + pics, pics) if b.get("flashback") and not a.get("flashback"))
    trans = {}
    for s in shots[1:]:
        t = s.get("transition_in", "cut")
        trans[t] = trans.get(t, 0) + 1
    return {"layers": len(pics), "asl_s": round(dur / max(1, len(pics)), 2),
            "median_shot_s": round(statistics.median(lens), 2) if lens else 0,
            "shots_under_3s": sum(1 for x in lens if x < 3), "jump_cuts": jump_cuts,
            "clip_switches": switches, "clip_switches_per_min": round(switches / (dur / 60), 2),
            "time_jumps_back": back, "flashbacks": flashbacks, "transitions": trans}


def music(sheet, film, min_xfade):
    dur = film["duration"]
    cues = sorted(sheet.get("cues", []), key=lambda c: c["at"])
    bounds = [c.get("t", c.get("t0")) for c in film.get("chapters", [])] + [s["t0"] for s in film.get("scenes", [])]
    changes, off_boundary, short_xfade, last = 0, [], [], None
    for c in cues:
        if c["track"] == last:
            continue
        changes += 1
        prev = next((p for p in reversed(cues) if p["at"] < c["at"] and p["track"] == last), None) if last else None
        last = c["track"]
        if prev is None:
            continue
        end = prev["at"] + prev["dur"]
        w0, w1 = min(c["at"], end), max(c["at"], end)
        if not any(w0 - 2 <= b <= w1 + 2 for b in bounds):
            off_boundary.append(f"{prev.get('id')}->{c.get('id')}@{c['at']:.1f}s")
        overlap = end - c["at"]
        if overlap > -1.0 and overlap < min_xfade:
            short_xfade.append(f"{prev.get('id')}->{c.get('id')} {max(0.0, overlap):.1f}s")
    lens = [c["dur"] for c in cues]
    edges = [0.0] + sorted(b for b in (c.get("t", c.get("t0")) for c in film.get("chapters", [])) if b) + [dur]
    per_ch = [len({c["track"] for c in cues if c["at"] < b and c["at"] + c["dur"] > a}) for a, b in zip(edges, edges[1:])]
    return {"cues": len(cues), "tracks": len({c["track"] for c in cues}), "track_changes": changes,
            "median_cue_s": round(statistics.median(lens), 1) if lens else 0,
            "changes_per_min": round(changes / (dur / 60), 2), "tracks_per_chapter": per_ch,
            "changes_off_boundary": off_boundary, "short_change_xfades": short_xfade}


def measure(film, sheet, min_xfade=MIN_CHANGE_XFADE_S):
    return {"duration_s": film["duration"], "picture": picture(film),
            "words": {"text_cards": len(film.get("text_spans", [])), "chapters": len(film.get("chapters", [])),
                      "throughline_sentences": len(film.get("throughline", []))},
            "music": music(sheet, film, min_xfade)}


def check(m, caps):
    p, w, mu = m["picture"], m["words"], m["music"]
    over = []

    def cap(name, value, limit, low=False):
        if (value < limit) if low else (value > limit):
            over.append({"metric": name, "value": value, "cap": ("min " if low else "max ") + str(limit)})
    cap("asl_s", p["asl_s"], caps["asl_min_s"], low=True)
    cap("shots_under_3s", p["shots_under_3s"], caps["short_shots_max"])
    cap("time_jumps_back", p["time_jumps_back"], caps["time_jumps_back_max"])
    cap("clip_switches_per_min", p["clip_switches_per_min"], caps["clip_switches_per_min_max"])
    cap("text_cards", w["text_cards"], caps["text_cards_max"])
    cap("chapters", w["chapters"], caps["chapters_max"])
    cap("tracks", mu["tracks"], caps["tracks_max"])
    cap("cues", mu["cues"], caps["cues_max"])
    cap("track_changes", mu["track_changes"], caps["track_changes_max"])
    if mu["cues"]:
        cap("median_cue_s", mu["median_cue_s"], caps["median_cue_min_s"], low=True)
    if mu["changes_off_boundary"]:
        over.append({"metric": "track changes away from a chapter/scene boundary",
                     "value": mu["changes_off_boundary"], "cap": "0"})
    if mu["short_change_xfades"]:
        over.append({"metric": "track-change cross-fades too short", "value": mu["short_change_xfades"],
                     "cap": f"min {caps['min_change_xfade_s']}s"})
    if not 1 <= w["throughline_sentences"] <= 5:
        over.append({"metric": "through-line sentences", "value": w["throughline_sentences"],
                     "cap": "1-5 (write the story a viewer could retell)"})
    return over


def raised(m, base):
    out = []
    for group, key in RAISE_CHECK:
        before, after = base.get(group, {}).get(key), m[group][key]
        if before is not None and after > before:
            out.append({"metric": f"{group}.{key}", "before": before, "after": after})
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--film", required=True, help="film.json with shots, text_spans, chapters, scenes, throughline")
    ap.add_argument("--cues", required=True, help="cue sheet JSON")
    ap.add_argument("--baseline", help="metrics JSON of the previous cut; a fix must not raise any fragment count")
    ap.add_argument("--json", dest="json_out", help="write metrics and findings as JSON")
    ap.add_argument("--strict", action="store_true", help="exit 1 on any over-cap value or raised count")
    for k, v in CAPS.items():
        ap.add_argument("--" + k.replace("_", "-"), type=type(v), default=v, help=f"provisional cap (default {v})")
    ap.add_argument("--min-change-xfade-s", type=float, default=MIN_CHANGE_XFADE_S,
                    help=f"cross-fade at a track change, s (default {MIN_CHANGE_XFADE_S:g})")
    args = ap.parse_args()
    load = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))  # noqa: E731
    caps = dict({k: getattr(args, k) for k in CAPS}, min_change_xfade_s=args.min_change_xfade_s)
    m = measure(load(args.film), load(args.cues), args.min_change_xfade_s)
    over = check(m, caps)
    up = raised(m, load(args.baseline)) if args.baseline else []
    p, mu = m["picture"], m["music"]
    print(f"picture  layers {p['layers']}  ASL {p['asl_s']}s  <3s {p['shots_under_3s']}  switches "
          f"{p['clip_switches']} ({p['clip_switches_per_min']}/min)  jumps back {p['time_jumps_back']}  "
          f"flashbacks {p['flashbacks']}")
    print(f"words    text cards {m['words']['text_cards']}  chapters {m['words']['chapters']}  "
          f"through-line {m['words']['throughline_sentences']} sentences")
    print(f"music    cues {mu['cues']}  tracks {mu['tracks']}  changes {mu['track_changes']}  median cue "
          f"{mu['median_cue_s']}s  tracks per chapter {mu['tracks_per_chapter']}")
    for o in over:
        print(f"WARNING  {o['metric']}: {o['value']} (provisional cap {o['cap']})")
    for r in up:
        print(f"WARNING  fix raised {r['metric']}: {r['before']} -> {r['after']} (fixes may only subtract)")
    bad = bool(over or up)
    print(f"RESULT {'FAIL' if bad and args.strict else ('WARN' if bad else 'PASS')} "
          f"({len(over)} over cap, {len(up)} raised)")
    if args.json_out:
        Path(args.json_out).write_text(json.dumps({**m, "caps": caps, "over_cap": over, "raised": up},
                                                  ensure_ascii=False, indent=1), encoding="utf-8")
    return 1 if bad and args.strict else 0


if __name__ == "__main__":
    sys.exit(main())
