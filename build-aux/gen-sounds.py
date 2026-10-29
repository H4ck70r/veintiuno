#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Synthesize the sound effects in src/veintiuno/sounds (deterministic, no samples)."""

import math
import os
import random
import struct
import wave

RATE = 44100
OUT = os.path.join(os.path.dirname(__file__), "..", "src", "veintiuno", "sounds")


def write(name, samples):
    peak = max(1e-9, max(abs(s) for s in samples))
    gain = 0.85 / peak
    with wave.open(os.path.join(OUT, name + ".wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(struct.pack("<h", int(s * gain * 32767)) for s in samples))


def silence(seconds):
    return [0.0] * int(RATE * seconds)


def mix(*tracks):
    length = max(len(t) for t in tracks)
    return [sum(t[i] for t in tracks if i < len(t)) for i in range(length)]


def offset(track, seconds):
    return silence(seconds) + track


def noise_burst(seconds, decay, rng, lowpass=0.35):
    out, prev = [], 0.0
    n = int(RATE * seconds)
    for i in range(n):
        prev += lowpass * (rng.uniform(-1, 1) - prev)
        attack = min(1.0, i / (RATE * 0.002))
        out.append(prev * attack * math.exp(-i / (RATE * decay)))
    return out


def tone(freq, seconds, decay=None, partials=((1, 1.0),), attack=0.005):
    out = []
    n = int(RATE * seconds)
    for i in range(n):
        t = i / RATE
        env = min(1.0, t / attack) * (math.exp(-t / decay) if decay else 1.0)
        release = min(1.0, (n - i) / (RATE * 0.02))
        out.append(env * release * sum(a * math.sin(2 * math.pi * freq * k * t) for k, a in partials))
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    rng = random.Random(21)

    # A card sliding onto the felt: soft swish then a little snap.
    write("card", mix(noise_burst(0.12, 0.035, rng, 0.22),
                      offset(noise_burst(0.03, 0.006, rng, 0.8), 0.045)))

    # Two clay chips clicking together.
    click = lambda f: tone(f, 0.06, 0.012, ((1, 1.0), (2.7, 0.5), (5.1, 0.25)), 0.0005)
    write("chip", mix(click(3100), offset(click(3600), 0.028),
                      [0.4 * s for s in noise_burst(0.02, 0.004, rng, 0.9)]))

    # Riffle shuffle: a run of tiny card flicks.
    shuffle = silence(0.9)
    t = 0.0
    while t < 0.75:
        burst = noise_burst(0.02, 0.004, rng, 0.6)
        start = int(t * RATE)
        for i, s in enumerate(burst):
            shuffle[start + i] += s * (0.6 + 0.4 * math.sin(math.pi * t / 0.75))
        t += rng.uniform(0.012, 0.022)
    write("shuffle", shuffle)

    bell = ((1, 1.0), (2, 0.35), (3, 0.12))
    write("win", mix(*[offset(tone(f, 0.45, 0.18, bell), i * 0.07)
                       for i, f in enumerate((523.25, 659.25, 783.99))]))
    write("blackjack", mix(*[offset(tone(f, 0.7, 0.3, bell), i * 0.08)
                             for i, f in enumerate((523.25, 659.25, 783.99, 1046.5, 1318.5))]))
    write("lose", mix(tone(392.0, 0.35, 0.15, ((1, 1.0), (2, 0.2))),
                      offset(tone(293.66, 0.5, 0.2, ((1, 1.0), (2, 0.2))), 0.16)))
    write("push", tone(587.33, 0.3, 0.12, bell))


if __name__ == "__main__":
    main()
