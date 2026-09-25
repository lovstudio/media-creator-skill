"""Voice-keyed music ducking and a look-ahead peak limiter, shared by score_mix.py and smr_check.py.

Ducking has two stages, both keyed by the voice bus with a 150 ms look-ahead:
  1. broadband duck (duck_db) while someone speaks;
  2. frequency-conscious duck: an extra band_cut_db on the music's 500-3000 Hz speech band only,
     so the bed keeps its lows and air instead of disappearing.
Library module; it has no command line.
"""
import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

SR = 48000


def voice_envelope(voice, hop=480, lookahead=15, thr_db=-42.0):
    """0..1 speech-activity envelope: 10 ms hops, 150 ms look-ahead, ~60 ms attack, ~500 ms release."""
    e = np.sqrt(np.convolve(voice ** 2, np.ones(hop) / hop, "same"))[::hop]
    act = (20 * np.log10(e + 1e-9) > thr_db).astype(np.float32)
    act = np.maximum(act, np.concatenate([act[lookahead:], np.zeros(lookahead, np.float32)]))
    sm = np.zeros_like(act)
    a_c, r_c = np.exp(-1 / 6.0), np.exp(-1 / 50.0)
    for i in range(1, len(act)):
        c = a_c if act[i] > sm[i - 1] else r_c
        sm[i] = c * sm[i - 1] + (1 - c) * act[i]
    full = np.repeat(sm, hop)[: len(voice)]
    return np.pad(full, (0, len(voice) - len(full)))


def split_speech_band(x):
    """Zero-phase FFT split of a mono signal into (speech band 500-3000 Hz, rest)."""
    n = len(x)
    spec = np.fft.rfft(x.astype(np.float64))
    f = np.fft.rfftfreq(n, 1 / SR)
    m = np.zeros_like(f)
    m[(f >= 500) & (f <= 3000)] = 1.0
    lo = (f > 300) & (f < 500)
    m[lo] = 0.5 - 0.5 * np.cos(np.pi * (f[lo] - 300) / 200)
    hi = (f > 3000) & (f < 4000)
    m[hi] = 0.5 + 0.5 * np.cos(np.pi * (f[hi] - 3000) / 1000)
    band = np.fft.irfft(spec * m, n).astype(np.float32)
    return band, (x - band).astype(np.float32)


def duck(music, voice, duck_db=-13.0, band_cut_db=-8.0):
    """music: (N,) or (N, 2) float32; voice: (N,); depths are dB scalars or (N,) arrays (per-moment
    mix intent). Returns the ducked music and the 0..1 voice envelope."""
    sm = voice_envelope(voice)
    g_full = (10 ** (duck_db * sm / 20)).astype(np.float32)
    g_band = (10 ** (band_cut_db * sm / 20)).astype(np.float32)
    chans = [music] if music.ndim == 1 else [music[:, c] for c in range(music.shape[1])]
    out = []
    for ch in chans:
        band, rest = split_speech_band(ch)
        out.append((rest + band * g_band) * g_full)
    y = out[0] if music.ndim == 1 else np.stack(out, 1)
    return y, sm


def peak_limit(x, ceiling_db=-6.0, lookahead_ms=5.0, release_ms=80.0):
    """Look-ahead sample-peak limiter for a mono or stereo bus; |x| never exceeds the ceiling.

    Returns the limited signal and the maximum gain reduction in dB.
    """
    thr = 10 ** (ceiling_db / 20)
    la = max(1, int(SR * lookahead_ms / 1000))
    mag = np.abs(x) if x.ndim == 1 else np.abs(x).max(axis=1)
    x = x.astype(np.float32)
    need = np.minimum(1.0, thr / (mag + 1e-12)).astype(np.float32)
    # Forward minimum over 2*la, then a backward moving average over la: every averaged window
    # around a peak contains that peak's requirement, so the gain is low enough AT the peak while
    # ramping down smoothly over the look-ahead instead of stepping (no clicks).
    padded = np.concatenate([need, np.ones(2 * la, np.float32)])
    gmin = sliding_window_view(padded, 2 * la + 1).min(axis=1)[: len(x)]
    c = np.concatenate([[0.0], np.cumsum(gmin, dtype=np.float64)])
    idx = np.arange(len(x))
    lo = np.maximum(0, idx - la + 1)
    g = ((c[idx + 1] - c[lo]) / (idx + 1 - lo)).astype(np.float32)
    # Release: gain may fall instantly (already smoothed above) but recovers with a one-pole release.
    r = np.exp(-1.0 / (SR * release_ms / 1000))
    out = np.empty_like(g)
    cur = 1.0
    for i in range(0, len(g), 4800):
        blk = g[i:i + 4800]
        o = np.empty_like(blk)
        for j, v in enumerate(blk):
            cur = v if v < cur else r * cur + (1 - r) * v
            o[j] = cur
        out[i:i + 4800] = o
    y = x * out if x.ndim == 1 else x * out[:, None]
    return y.astype(np.float32), float(20 * np.log10(out.min() + 1e-12))
