from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


VALIDATE = load("validate_cues")
INTEL = load("intelligibility")
CUT = load("cut_metrics")
try:
    import numpy as np
    DUCKING = load("ducking")
    SCORE_MIX = load("score_mix")
except ImportError:  # the DSP tests need numpy; the gate logic tests do not
    np = None
    DUCKING = None
    SCORE_MIX = None


def track(duration=200.0, sung=(), instrumental=True):
    return {"duration": duration, "loudness_db_per_s": [-30.0] * int(duration), "median_loudness_db": -30.0,
            "sung_lines": list(sung), "instrumental": instrumental}


def cue(cid, name, at, dur, track_in=0.0, **extra):
    return {"id": cid, "track": name, "track_in": track_in, "at": at, "dur": dur,
            "fade_in": 2.0, "fade_out": 2.0, "rationale": "scene reason", **extra}


FILM = {"duration": 60.0, "dialogue_language": "zh", "voice_spans": [{"t0": 10.0, "t1": 20.0}],
        "text_spans": [{"t0": 40.0, "t1": 45.0, "text": "card"}]}
TRACKS = {"playable": {
    "instr": track(),
    "instr2": track(),
    "instr3": track(),
    "zh_song": track(sung=[{"t0": 0.0, "t1": 8.0, "text": "我们一起走", "lang": "zh"}], instrumental=False),
    "ja_song": track(sung=[{"t0": 0.0, "t1": 8.0, "text": "そらへ", "lang": "ja"}], instrumental=False),
    "unknown": {**track(), "instrumental": None},
}, "unplayable": {"locked": {"reason": "Invalid data found when processing input"}}}


def run(cues, silences=None, min_tracks=1, intents=None, film=FILM):
    sheet = {"cues": cues, "silences": silences or [], "mix_intents": intents or []}
    return VALIDATE.validate(sheet, TRACKS, film, min_tracks=min_tracks)


class CueValidationTests(unittest.TestCase):
    def test_clean_three_track_score_passes(self) -> None:
        out = run([cue("a", "instr", 0, 22), cue("b", "instr2", 20, 22), cue("c", "instr3", 40, 20)], min_tracks=3)
        self.assertEqual(out["errors"], [])
        self.assertEqual(out["warnings"], [])

    def test_same_language_lyrics_under_dialogue_is_an_error(self) -> None:
        out = run([cue("a", "zh_song", 10, 50)])
        self.assertTrue(any("lyrics under 'zh' dialogue" in e for e in out["errors"]))

    def test_other_language_singing_under_dialogue_is_a_warning(self) -> None:
        out = run([cue("a", "ja_song", 10, 50)])
        self.assertEqual(out["errors"], [])
        self.assertTrue(any("another language" in w for w in out["warnings"]))

    def test_unknown_lyrics_under_dialogue_is_a_warning(self) -> None:
        out = run([cue("a", "unknown", 0, 60)])
        self.assertTrue(any("unknown" in w for w in out["warnings"]))

    def test_lyrics_on_text_card_need_lyric_feature(self) -> None:
        plain = run([cue("a", "instr", 0, 40), cue("b", "ja_song", 40, 20)])
        self.assertTrue(any("on-screen text" in w for w in plain["warnings"]))
        featured = run([cue("a", "instr", 0, 40), cue("b", "ja_song", 40, 20, lyric_feature=True)])
        self.assertFalse(any("on-screen text" in w for w in featured["warnings"]))

    def test_missing_rationale_is_an_error(self) -> None:
        c = cue("a", "instr", 0, 60)
        c["rationale"] = " "
        self.assertTrue(any("rationale" in e for e in run([c])["errors"]))

    def test_unplayable_track_reports_reason(self) -> None:
        out = run([cue("a", "locked", 0, 60)])
        self.assertTrue(any("Invalid data" in e for e in out["errors"]))

    def test_three_concurrent_cues_is_an_error(self) -> None:
        out = run([cue("a", "instr", 0, 60), cue("b", "instr2", 5, 50), cue("c", "instr3", 10, 40)])
        self.assertTrue(any("sound at once" in e for e in out["errors"]))

    def test_short_overlap_is_not_a_cross_fade(self) -> None:
        out = run([cue("a", "instr", 0, 30.5), cue("b", "instr2", 30, 30)])
        self.assertTrue(any("too short for a cross-fade" in w for w in out["warnings"]))

    def test_undeclared_silence_warns_and_declared_silence_passes(self) -> None:
        cues = [cue("a", "instr", 0, 20), cue("b", "instr2", 40, 20)]
        self.assertTrue(any("not declared" in w for w in run(cues)["warnings"]))
        declared = run(cues, silences=[{"t0": 20, "t1": 40, "reason": "summit, breath only"}])
        self.assertFalse(any("not declared" in w for w in declared["warnings"]))

    def test_single_track_score_warns_below_min_tracks(self) -> None:
        out = run([cue("a", "instr", 0, 60)], min_tracks=3)
        self.assertTrue(any("distinct tracks" in w for w in out["warnings"]))

    def test_mix_intents_are_checked(self) -> None:
        full = [cue("a", "instr", 0, 60)]
        ok = run(full, intents=[{"t0": 10, "t1": 20, "intent": "blend", "reason": "arrival peak"}])
        self.assertEqual(ok["errors"], [])
        self.assertFalse(any("mix intent" in w for w in ok["warnings"]))
        bad = run(full, intents=[{"t0": 10, "t1": 20, "intent": "loud"}])
        self.assertTrue(any("unknown intent" in e for e in bad["errors"]))
        overlap = run(full, intents=[{"t0": 10, "t1": 20, "intent": "blend", "reason": "x"},
                                     {"t0": 15, "t1": 25, "intent": "feature", "reason": "y"}])
        self.assertTrue(any("overlap" in e for e in overlap["errors"]))
        no_reason = run(full, intents=[{"t0": 10, "t1": 20, "intent": "feature"}])
        self.assertTrue(any("no reason" in w for w in no_reason["warnings"]))

    def test_feature_intent_does_not_excuse_same_language_lyrics(self) -> None:
        out = run([cue("a", "zh_song", 10, 50)], intents=[{"t0": 10, "t1": 20, "intent": "feature", "reason": "x"}])
        self.assertTrue(any("lyrics under 'zh' dialogue" in e for e in out["errors"]))

    def test_music_inside_declared_silence_past_the_tail_is_an_error(self) -> None:
        silence = [{"t0": 20, "t1": 40, "reason": "summit"}]
        tail = run([cue("a", "instr", 0, 21.5), cue("b", "instr2", 40, 20)], silences=silence)
        self.assertFalse(any("inside declared silence" in e for e in tail["errors"]))
        late = run([cue("a", "instr", 0, 30), cue("b", "instr2", 40, 20)], silences=silence)
        self.assertTrue(any("inside declared silence" in e for e in late["errors"]))

    def test_pacing_checks(self) -> None:
        film = {"duration": 60.0, "voice_spans": [{"t0": 1.0, "t1": 4.6}, {"t0": 20.0, "t1": 22.0}],
                "text_spans": [{"t0": 30.0, "t1": 32.0, "text": "十二个字的一张字卡要读够时间"}],
                "chapters": [{"t": 0.0}, {"t": 12.0, "title": "二"}],
                "beats": [{"t0": 0.0, "t1": 5.0}, {"t0": 5.0, "t1": 8.0}, {"t0": 8.0, "t1": 10.0},
                          {"t0": 10.0, "t1": 12.0}, {"t0": 12.0, "t1": 25.0, "transition_in": "cut"}]}
        out = " | ".join(VALIDATE.pacing(film))
        self.assertIn("shorter than their reading time", out)
        self.assertIn("less than 1.0s after their last word", out)
        self.assertIn("3 beats under 4.0s in a row", out)
        self.assertIn("opens on a hard cut", out)

    def test_short_text_card_chain_warns(self) -> None:
        cards = [(0.0, 4.0), (4.5, 8.0), (8.2, 12.0), (20.0, 30.0), (30.5, 34.0)]
        self.assertEqual(VALIDATE.card_runs(cards), [[(0.0, 4.0), (4.5, 8.0), (8.2, 12.0)]])
        film = {**FILM, "text_spans": [{"t0": a, "t1": b, "text": "card"} for a, b in cards]}
        out = run([cue("a", "instr", 0, 60)], film=film)
        self.assertTrue(any("short text cards back to back" in w for w in out["warnings"]))

    def test_lyric_override_releases_same_language_clash_as_info(self) -> None:
        override = {"reason": "author asked for this song under the opening lines",
                    "author_quote": "不必为了口播而刻意停止 bgm"}
        out = run([cue("a", "zh_song", 10, 50, lyric_override=override)])
        self.assertEqual(out["errors"], [])
        self.assertTrue(any("released by the author" in i and "不必为了口播" in i for i in out["info"]))
        self.assertEqual(out["released"], [{"cue": "a", "track": "zh_song", "seconds": 8.0,
                                            "spans": [[10.0, 18.0]], "reason": override["reason"],
                                            "author_quote": override["author_quote"]}])

    def test_incomplete_lyric_override_stays_an_error(self) -> None:
        for override in ({"reason": "author likes it"}, {"reason": " ", "author_quote": "ok"}, True):
            out = run([cue("a", "zh_song", 10, 50, lyric_override=override)])
            self.assertTrue(any("needs both reason and author_quote" in e for e in out["errors"]), override)
            self.assertEqual(out["released"], [])

    def test_sheet_without_overrides_reports_no_releases(self) -> None:
        out = run([cue("a", "zh_song", 10, 50)])
        self.assertEqual(out["released"], [])
        self.assertFalse(any("needs both" in e for e in out["errors"]))

    def test_narrative_preset_tightens_the_music_gap(self) -> None:
        cues = [cue("a", "instr", 0, 20), cue("b", "instr2", 23, 37)]
        self.assertFalse(any("music-free" in w for w in run(cues)["warnings"]))
        sheet = {"cues": cues}
        narrative = VALIDATE.validate(sheet, TRACKS, FILM, min_tracks=1,
                                      max_gap=VALIDATE.PRESETS["narrative"]["max_gap"])
        self.assertTrue(any("music-free span 20.0-23.0s" in w for w in narrative["warnings"]))

    def test_cli_preset_sets_the_default_gap_and_max_gap_still_wins(self) -> None:
        import json
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            sheet = {"cues": [cue("a", "instr", 0, 20), cue("b", "instr2", 23, 37), cue("c", "instr3", 40, 20)]}
            for name, data in (("cues", sheet), ("tracks", TRACKS), ("film", FILM)):
                (d / f"{name}.json").write_text(json.dumps(data), encoding="utf-8")

            def gaps(*extra):
                subprocess.run([sys.executable, str(SCRIPTS / "validate_cues.py"), "--cues", str(d / "cues.json"),
                                "--tracks", str(d / "tracks.json"), "--film", str(d / "film.json"),
                                "--json", str(d / "out.json"), *extra], check=True, capture_output=True)
                out = json.loads((d / "out.json").read_text(encoding="utf-8"))
                return [w for w in out["warnings"] if "music-free" in w]
            self.assertEqual(gaps(), [])
            self.assertEqual(len(gaps("--preset", "narrative")), 1)
            self.assertEqual(gaps("--preset", "narrative", "--max-gap", "6"), [])


def frag_film(**extra):
    shots = [{"t0": 0, "t1": 20, "source": "A", "captured_at": "20260918_100000"},
             {"t0": 20, "t1": 22, "source": "A", "captured_at": "20260918_100000"},
             {"t0": 22, "t1": 24, "black": True},
             {"t0": 24, "t1": 26, "source": "B", "captured_at": "20260918_120000"},
             {"t0": 26, "t1": 60, "source": "C", "captured_at": "20260918_090000"}]
    return {"duration": 60.0, "shots": shots, "text_spans": [], "chapters": [{"t": 0}, {"t": 30}],
            "throughline": ["one", "two"], **extra}


class CutMetricsTests(unittest.TestCase):
    def test_picture_metrics_merge_jump_cuts_and_count_time_jumps(self) -> None:
        pic = CUT.measure(frag_film(), {"cues": []})["picture"]
        self.assertEqual(pic["layers"], 3)
        self.assertEqual(pic["jump_cuts"], 1)
        self.assertEqual(pic["shots_under_3s"], 1)
        self.assertEqual(pic["clip_switches"], 3)
        self.assertEqual(pic["time_jumps_back"], 1)
        self.assertAlmostEqual(pic["asl_s"], 20.0)

    def test_track_changes_count_first_entry_and_flag_mid_scene_changes(self) -> None:
        sheet = {"cues": [cue("a", "instr", 0, 31), cue("b", "instr2", 28, 10), cue("c", "instr", 45, 15)]}
        mu = CUT.measure(frag_film(), sheet)["music"]
        self.assertEqual(mu["track_changes"], 3)
        self.assertEqual(mu["tracks"], 2)
        self.assertEqual(mu["tracks_per_chapter"], [2, 2])
        self.assertEqual(len(mu["changes_off_boundary"]), 1)
        self.assertEqual(len(mu["short_change_xfades"]), 0)

    def test_caps_and_baseline(self) -> None:
        caps = dict(CUT.CAPS, min_change_xfade_s=3.0)
        m = CUT.measure(frag_film(throughline=[]), {"cues": [cue("a", "instr", 0, 10)]})
        names = [o["metric"] for o in CUT.check(m, caps)]
        self.assertIn("median_cue_s", names)
        self.assertIn("through-line sentences", names)
        base = {"picture": {"layers": 2, "clip_switches": 3}, "music": {"cues": 1}}
        self.assertEqual([r["metric"] for r in CUT.raised(m, base)], ["picture.layers"])

    def test_flashback_shots_are_not_time_jumps(self) -> None:
        def film(flag, after="20260918_103000"):
            shots = [{"t0": 0, "t1": 20, "source": "A", "captured_at": "20260918_100000"},
                     {"t0": 20, "t1": 30, "source": "F1", "captured_at": "20181002_100734", "flashback": flag},
                     {"t0": 30, "t1": 40, "source": "F2", "captured_at": "20181002_212402", "flashback": flag},
                     {"t0": 40, "t1": 60, "source": "B", "captured_at": after}]
            return {"duration": 60.0, "shots": shots, "throughline": ["one"]}
        plain = CUT.measure(film(False), {"cues": []})["picture"]
        self.assertEqual((plain["time_jumps_back"], plain["flashbacks"]), (1, 0))
        memory = CUT.measure(film(True), {"cues": []})["picture"]
        self.assertEqual((memory["time_jumps_back"], memory["flashbacks"]), (0, 1))
        self.assertEqual(memory["clip_switches"], 4)
        # the count resumes from the last present-day shot, so a real jump after the memory still counts
        back = CUT.measure(film(True, after="20260918_080000"), {"cues": []})["picture"]
        self.assertEqual(back["time_jumps_back"], 1)

    def test_default_change_xfade_accepts_the_kailash_handoffs(self) -> None:
        # handoffs of the accepted Kailash final ran 1-3 s (median 1.5 s)
        sheet = {"cues": [cue("a", "instr", 0, 31), cue("b", "instr2", 30, 16.5),
                          cue("c", "instr3", 45, 15)]}
        self.assertEqual(CUT.MIN_CHANGE_XFADE_S, 1.0)
        self.assertEqual(CUT.measure(frag_film(), sheet)["music"]["short_change_xfades"], [])
        self.assertEqual(len(CUT.measure(frag_film(), sheet, min_xfade=3.0)["music"]["short_change_xfades"]), 2)
        abrupt = {"cues": [cue("a", "instr", 0, 30.4), cue("b", "instr2", 30, 30)]}
        self.assertEqual(CUT.measure(frag_film(), abrupt)["music"]["short_change_xfades"], ["a->b 0.4s"])


class IntelligibilityTests(unittest.TestCase):
    def test_cer_ignores_punctuation(self) -> None:
        self.assertEqual(INTEL.cer("你们为什么来转山？", "你们为什么来转山"), 0.0)
        self.assertAlmostEqual(INTEL.cer("一二三四", "一二三"), 0.25)

    def test_repetition_loop_is_flagged_not_scored(self) -> None:
        self.assertTrue(INTEL.asr_loop("还有这个抓绒", "cangoicangoicangoicangoicango"))
        self.assertFalse(INTEL.asr_loop("还有这个抓绒", "还有这个抓绒"))
        rows = [{"sub": "一二三四", "asr": "一二三四", "cer": 0.0},
                {"sub": "一二", "asr": "abababababababab", "cer": 7.0},
                {"sub": "五六七八", "asr": "", "cer": 3.0}]
        self.assertAlmostEqual(INTEL.mean_cer(rows), 0.5)

    def test_parse_srt(self) -> None:
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".srt", delete=False, encoding="utf-8") as f:
            f.write("1\n00:00:01,900 --> 00:00:03,220\n你们为什么\n来转山？\n\n2\n00:01:00,000 --> 00:01:02,500\n好\n")
        cues = INTEL.parse_srt(f.name)
        Path(f.name).unlink()
        self.assertEqual(cues[0], (1.9, 3.22, "你们为什么来转山？"))
        self.assertEqual(cues[1][0], 60.0)


@unittest.skipIf(DUCKING is None, "numpy is not installed")
class DuckingTests(unittest.TestCase):
    def test_peak_limiter_holds_the_ceiling(self) -> None:
        sr = DUCKING.SR
        t = np.arange(sr) / sr
        x = (0.2 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
        x[sr // 2] = 0.99
        y, gr = DUCKING.peak_limit(x, ceiling_db=-6.0)
        self.assertLessEqual(float(np.abs(y).max()), 10 ** (-6.0 / 20) + 1e-4)
        self.assertLess(gr, 0.0)

    def test_duck_cuts_the_speech_band_more_than_the_lows(self) -> None:
        sr = DUCKING.SR
        t = np.arange(2 * sr) / sr
        music = (0.1 * np.sin(2 * np.pi * 100 * t) + 0.1 * np.sin(2 * np.pi * 1000 * t)).astype(np.float32)
        voice = np.zeros_like(music)
        voice[sr // 2:] = 0.1 * np.sin(2 * np.pi * 300 * t[sr // 2:])
        out, env = DUCKING.duck(music, voice, duck_db=-13.0, band_cut_db=-8.0)
        seg = slice(int(1.5 * sr), 2 * sr - 1000)

        def level(sig, hz):
            spec = np.abs(np.fft.rfft(sig[seg]))
            freqs = np.fft.rfftfreq(len(sig[seg]), 1 / sr)
            return spec[np.argmin(np.abs(freqs - hz))]
        low_cut = 20 * np.log10(level(out, 100) / level(music, 100))
        band_cut = 20 * np.log10(level(out, 1000) / level(music, 1000))
        self.assertGreater(float(env[seg].min()), 0.99)
        self.assertAlmostEqual(low_cut, -13.0, delta=0.5)
        self.assertAlmostEqual(band_cut, -21.0, delta=0.5)

    def test_intent_ranges_set_lighter_duck_depths(self) -> None:
        sheet = {"mix_intents": [{"t0": 1.0, "t1": 3.0, "intent": "blend", "reason": "x"}]}
        self.assertEqual(SCORE_MIX.intent_at(sheet, 1.5, 2.5), "blend")
        self.assertEqual(SCORE_MIX.intent_at(sheet, 2.8, 4.0), "clear")
        p = {"duck_db": -13.0, "band_cut_db": -8.0}
        duck, band = SCORE_MIX.depth_curves(sheet, [], 4 * DUCKING.SR, p)
        sr = DUCKING.SR
        self.assertAlmostEqual(float(duck[int(0.5 * sr)]), -13.0, places=3)
        self.assertAlmostEqual(float(duck[int(2.0 * sr)]), SCORE_MIX.INTENTS["blend"][0], places=3)
        self.assertAlmostEqual(float(band[int(2.0 * sr)]), SCORE_MIX.INTENTS["blend"][1], places=3)
        glide = duck[int(0.5 * sr):int(1.5 * sr)]
        self.assertLess(float(np.abs(np.diff(glide)).max()), 0.1)
        mid = (-13.0 + SCORE_MIX.INTENTS["blend"][0]) / 2
        self.assertAlmostEqual(float(duck[int(1.0 * sr)]), mid, delta=0.1)
        self.assertEqual(SCORE_MIX.depth_curves({}, [], 10, p), (-13.0, -8.0))

    def test_line_intent_wins_over_ranges(self) -> None:
        sheet = {"mix_intents": [{"t0": 0.0, "t1": 10.0, "intent": "feature", "reason": "x"}]}
        lines = [{"at": 4.0, "dur": 2.0, "intent": "clear"}]
        duck, _ = SCORE_MIX.depth_curves(sheet, lines, 10 * DUCKING.SR, {"duck_db": -13.0, "band_cut_db": -8.0})
        self.assertAlmostEqual(float(duck[5 * DUCKING.SR]), -13.0, places=3)
        self.assertAlmostEqual(float(duck[8 * DUCKING.SR]), SCORE_MIX.INTENTS["feature"][0], places=3)

    def test_smooth_is_centred_and_length_preserving(self) -> None:
        x = np.array([0.0] * 50 + [10.0] * 50)
        y = SCORE_MIX.smooth(x, 10)
        self.assertEqual(len(y), len(x))
        self.assertAlmostEqual(float(y[0]), 0.0)
        self.assertAlmostEqual(float(y[-1]), 10.0)
        self.assertAlmostEqual(float(y[50] + y[49]), 10.0, places=6)

    def test_same_source_ambience_is_muted_only_around_the_line(self) -> None:
        sr = DUCKING.SR
        x = np.ones(4 * sr, np.float32)
        y, muted = SCORE_MIX.mute_spans(x, 10.0, [(11.0, 12.0)])
        self.assertAlmostEqual(muted, 1.0, places=2)
        self.assertEqual(float(y[int(1.5 * sr)]), 0.0)
        self.assertEqual(float(y[int(0.5 * sr)]), 1.0)
        self.assertEqual(float(y[int(3.0 * sr)]), 1.0)
        self.assertGreater(float(y[int(0.97 * sr)]), 0.0)


@unittest.skipIf(SCORE_MIX is None, "numpy is not installed")
class LevelRefTests(unittest.TestCase):
    """A track with a 5 s intro at -40 dBFS and a 15 s body at -20 dBFS (constant samples, exact RMS)."""

    P = {"voice_lufs": -20.0, "max_voice_boost": 14.0, "voice_limit": -6.0, "music_ref": -27.0,
         "ambient_limit": -10.0, "duck_db": -13.0, "band_cut_db": -8.0, "level_ref": "cue"}
    TRACK = {"file": "song.wav", "duration": 20.0}

    def fake_decode(self, path, ch=1, ss=None, dur=None, af=None):
        self.decoded.append((ss, dur))
        sr = SCORE_MIX.SR
        full = np.concatenate([np.full(5 * sr, 0.01), np.full(15 * sr, 0.1)]).astype(np.float32)
        i = int(round((ss or 0.0) * sr))
        x = full[i:] if dur is None else full[i:i + int(round(dur * sr))]
        return np.stack([x, x], 1) if ch == 2 else x

    def gains(self, cues, **sheet):
        import json
        import tempfile
        from unittest import mock
        self.decoded = []
        with tempfile.TemporaryDirectory() as tmp:
            voice = Path(tmp) / "voice.json"
            voice.write_text(json.dumps({"duration": 5.0, "lines": []}), encoding="utf-8")
            p = dict(self.P, level_ref=sheet.pop("level_ref", "cue"))
            with mock.patch.object(SCORE_MIX, "decode", self.fake_decode):
                report = SCORE_MIX.build_buses(voice, {"cues": cues, **sheet}, {"playable": {"song": self.TRACK}},
                                               p, ambient=False)[4]
        return {m["id"]: m["gain_db"] for m in report["music"]}

    def test_level_window(self) -> None:
        self.assertIsNone(SCORE_MIX.level_window("cue", self.TRACK))
        self.assertEqual(SCORE_MIX.level_window("track", self.TRACK), (0.0, 20.0))
        self.assertEqual(SCORE_MIX.level_window([5, 20], self.TRACK), (5.0, 15.0))
        for bad in ("loud", [20, 5], [0, 99], [1], ["a", "b"]):
            with self.assertRaises(SystemExit, msg=bad):
                SCORE_MIX.level_window(bad, self.TRACK)

    def test_quiet_intro_keeps_the_track_dynamics(self) -> None:
        intro = {"track": "song", "track_in": 0.0, "at": 0.0, "dur": 4.0, "level_db": 0.0}
        g = self.gains([{**intro, "id": "cue"}, {**intro, "id": "track", "level_ref": "track"},
                        {**intro, "id": "window", "level_ref": [5, 20]},
                        {**{k: v for k, v in intro.items() if k != "level_db"}, "id": "abs", "gain_db": -9.0}])
        self.assertEqual(g["cue"], 13.0)  # the old behaviour: the -40 dBFS intro is lifted to -27
        self.assertEqual(g["track"], -5.8)  # whole-track RMS is -21.2 dBFS
        self.assertEqual(g["window"], -7.0)  # the -20 dBFS body
        self.assertEqual(g["abs"], -9.0)

    def test_sheet_level_ref_applies_to_cues_without_their_own(self) -> None:
        intro = {"track": "song", "track_in": 0.0, "at": 0.0, "dur": 4.0, "level_db": 0.0}
        g = self.gains([{**intro, "id": "a"}, {**intro, "id": "b", "track_in": 1.0},
                        {**intro, "id": "c", "level_ref": "cue"}], level_ref="track")
        self.assertEqual((g["a"], g["b"], g["c"]), (-5.8, -5.8, 13.0))
        self.assertEqual(self.decoded.count((0.0, 20.0)), 1)  # the whole track is measured once

    def test_level_ref_precedence(self) -> None:
        import argparse
        ap = argparse.ArgumentParser()
        SCORE_MIX.add_mix_args(ap)
        base = ["--voice", "v.json", "--cues", "c.json", "--tracks", "t.json"]
        pick = lambda argv, sheet: SCORE_MIX.mix_params(ap.parse_args(base + argv), sheet)["level_ref"]  # noqa: E731
        self.assertEqual(pick([], {}), "cue")
        self.assertEqual(pick([], {"level_ref": "track"}), "track")
        self.assertEqual(pick(["--level-ref", "cue"], {"level_ref": "track"}), "cue")


if __name__ == "__main__":
    unittest.main()
