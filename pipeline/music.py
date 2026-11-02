"""Egen, rettighedsfri lo-fi-beat til reels: trommer, bas, el-klaver og vinylknas.

Alt er syntetiseret her, så der er ingen licens at tage stilling til. Hver reel får sin
egen variant (tempo, toneart og akkordrundgang vælges ud fra opslagets id).
"""
import hashlib
import wave
from pathlib import Path

import numpy as np

SR = 44100

# Akkorder som halvtoner over grundtonen (7-akkorder giver den bløde lo-fi-farve).
PROGS = [
    [(0, [0, 3, 7, 10]), (8, [0, 4, 7, 11]), (3, [0, 4, 7, 11]), (10, [0, 4, 7, 9])],   # i7 VImaj7 IIImaj7 VII6
    [(0, [0, 3, 7, 10]), (5, [0, 3, 7, 10]), (10, [0, 4, 7, 10]), (3, [0, 4, 7, 11])],  # i7 iv7 VII7 IIImaj7
    [(0, [0, 4, 7, 11]), (9, [0, 3, 7, 10]), (5, [0, 4, 7, 11]), (7, [0, 4, 7, 10])],   # Imaj7 vi7 IVmaj7 V7
    [(0, [0, 4, 7, 11]), (4, [0, 3, 7, 10]), (9, [0, 3, 7, 10]), (5, [0, 4, 7, 11])],   # Imaj7 iii7 vi7 IVmaj7
]


def _freq(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def _env(n, attack, decay):
    t = np.arange(n) / SR
    return np.minimum(1, t / max(attack, 1e-4)) * np.exp(-t / decay)


def _lowpass(x, cutoff):
    a = np.exp(-2 * np.pi * cutoff / SR)
    try:
        from scipy.signal import lfilter
        return lfilter([1 - a], [1, -a], x)
    except ImportError:  # langsom reserve uden scipy
        y = np.empty_like(x)
        acc = 0.0
        for i in range(len(x)):
            acc = (1 - a) * x[i] + a * acc
            y[i] = acc
        return y


def _add(buf, sig, start):
    s = int(start)
    if s >= len(buf):
        return
    e = min(len(buf), s + len(sig))
    buf[s:e] += sig[: e - s]


def _kick():
    n = int(0.35 * SR)
    t = np.arange(n) / SR
    f = 50 + 90 * np.exp(-t * 28)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9) * 0.95


def _snare(rng):
    n = int(0.25 * SR)
    t = np.arange(n) / SR
    noise = _lowpass(rng.standard_normal(n), 3500) * np.exp(-t * 18)
    tone = np.sin(2 * np.pi * 185 * t) * np.exp(-t * 30)
    return (noise * 0.55 + tone * 0.35)


def _hat(rng, open_=False):
    n = int((0.18 if open_ else 0.05) * SR)
    t = np.arange(n) / SR
    x = rng.standard_normal(n)
    x = x - _lowpass(x, 7000)  # højpas
    return x * np.exp(-t * (14 if open_ else 70)) * 0.22


def _keys(midi, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = _freq(midi)
    wob = 1 + 0.003 * np.sin(2 * np.pi * 5 * t)  # let båndsvaj
    x = (np.sin(2 * np.pi * f * t * wob) + 0.35 * np.sin(4 * np.pi * f * t * wob)
         + 0.12 * np.sin(6 * np.pi * f * t * wob))
    return x * _env(n, 0.01, 1.4) * 0.11


def _bass(midi, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = _freq(midi)
    x = np.sin(2 * np.pi * f * t) + 0.25 * np.sin(4 * np.pi * f * t)
    return x * _env(n, 0.005, 0.9) * 0.32


def beat(duration, seed_text, out_path):
    """Skriver en stereo-WAV på `duration` sekunder til out_path og returnerer stien."""
    seed = int(hashlib.sha1(seed_text.encode()).hexdigest()[:8], 16)
    rng = np.random.default_rng(seed)
    bpm = int(rng.integers(76, 92))
    root = 45 + int(rng.integers(0, 7))  # A2 til D#3
    prog = PROGS[seed % len(PROGS)]
    beat_s = 60 / bpm
    bar = 4 * beat_s
    total = int((duration + 0.5) * SR)
    drums = np.zeros(total)
    music = np.zeros(total)
    kick, snare = _kick(), _snare(rng)
    swing = beat_s / 2 * 0.12
    nbars = int(np.ceil(duration / bar)) + 1

    for b in range(nbars):
        t0 = b * bar * SR
        deg, chord = prog[b % len(prog)]
        # Klaver: akkord på slag 1 og en lille gentagelse på 2 og en halv.
        for k, iv in enumerate(chord):
            _add(music, _keys(root + 12 + deg + iv, bar), t0 + k * 0.012 * SR)
            _add(music, _keys(root + 12 + deg + iv, bar / 2) * 0.55, t0 + 2.5 * beat_s * SR + k * 0.01 * SR)
        # Bas: grundtone på 1, kvint på 3 og et lille løb ind i næste takt.
        _add(music, _bass(root - 12 + deg, beat_s * 1.8), t0)
        _add(music, _bass(root - 12 + deg + 7, beat_s * 0.9), t0 + 2 * beat_s * SR)
        _add(music, _bass(root - 12 + deg + 12, beat_s * 0.45), t0 + 3.5 * beat_s * SR)
        if b == 0:
            continue  # første takt uden trommer, så det bygger op
        _add(drums, kick, t0)
        _add(drums, kick * 0.8, t0 + 2.5 * beat_s * SR)
        if b % 2:
            _add(drums, kick * 0.6, t0 + 1.75 * beat_s * SR)
        _add(drums, snare, t0 + 1 * beat_s * SR)
        _add(drums, snare, t0 + 3 * beat_s * SR)
        for e in range(8):
            off = e * beat_s / 2 + (swing if e % 2 else 0)
            _add(drums, _hat(rng, open_=(e == 7 and b % 4 == 3)) * (1.0 if e % 2 == 0 else 0.65), t0 + off * SR)

    # Pumpende effekt: musikken dukker sig let for hver stortromme.
    duck = np.ones(total)
    for b in range(1, nbars):
        for pos in (0, 2.5):
            s = int((b * bar + pos * beat_s) * SR)
            n = int(0.25 * SR)
            if s < total:
                e = min(total, s + n)
                duck[s:e] = np.minimum(duck[s:e], 0.55 + 0.45 * np.linspace(0, 1, e - s))
    music = _lowpass(music * duck, 5200)
    drums = _lowpass(drums, 9000)

    crackle = np.zeros(total)
    pops = rng.integers(0, total, size=int(duration * 6))
    crackle[pops] = rng.uniform(-0.25, 0.25, size=len(pops))
    hiss = _lowpass(rng.standard_normal(total), 4000) * 0.006

    mix = music + drums * 0.8 + crackle + hiss
    fade = int(1.2 * SR)
    mix[:fade] *= np.linspace(0, 1, fade)
    mix[-fade:] *= np.linspace(1, 0, fade)
    mix = np.tanh(mix * 1.4) / np.tanh(1.4)  # blød mætning, varm og uden klip
    mix = mix / (np.max(np.abs(mix)) + 1e-9) * 0.89

    # Lidt stereobredde: en kort forsinkelse på højre kanal for klaveret.
    d = int(0.011 * SR)
    right = mix.copy()
    right[d:] = 0.85 * mix[d:] + 0.15 * mix[:-d]
    stereo = np.stack([mix, right], axis=1)
    pcm = (stereo * 32767).astype(np.int16)
    out_path = Path(out_path)
    with wave.open(str(out_path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return out_path
