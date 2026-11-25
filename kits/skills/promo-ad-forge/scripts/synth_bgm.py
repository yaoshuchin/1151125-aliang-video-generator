#!/usr/bin/env python3
"""
synth_bgm.py — 自行合成「沒有第三方授權限制」的廣告配樂，並輸出節拍表 beats.json。

畫面動作要跟著音樂走，所以音樂與節拍表必須同源產生：
  - bgm.wav   ：44.1kHz 立體聲配樂（鼓組＋貝斯＋和弦＋上升音效＋重擊）
  - beats.json：BPM、每拍時間、每小節重拍、段落（intro/build/drop/outro）、重擊點 hits

用法：
  python synth_bgm.py --out assets/bgm.wav --beats beats.json --bpm 120 --duration 30 --style pop-bounce --project starfire-code-club
  風格：pop-bounce（明亮彈跳）｜tech-pulse（科技脈衝）｜warm-pluck（溫暖撥弦）｜hype-trap（熱血重低音）

每支影片配樂不同、同一支可重現：
  - 種子優先序：--seed（手動指定）> --project 名稱 > 輸出檔所在專案資料夾名稱（自動）
  - 種子決定：調性、和弦進行（每風格 4 組）、琶音型、主音色、鼓的變化、2 小節旋律動機（A A' B A）
  - 同專案重跑＝完全相同音檔（改畫面不會換歌）；想換一首就加 --variant 2、3…
  - 實際抽中的組合寫入 beats.json 的 "variation"
只用 numpy / scipy。
"""
import argparse
import hashlib
import json
import math
import os

import sys

import numpy as np
from scipy.io import wavfile
from scipy.signal import lfilter

for _s in (sys.stdout, sys.stderr):  # cp950 主控台也要正確顯示中文與「—」
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

SR = 44100

# 每個風格：根音範圍、和弦進行候選（相對半音, 大/小）、鼓型、主音色候選、亮度
STYLES = {
    "pop-bounce": dict(root=(55, 62), kit="four", leads=["square", "pluck", "saw"], bright=1.0, progs=[
        [(0, "M"), (7, "M"), (9, "m"), (5, "M")],     # I V vi IV
        [(0, "M"), (9, "m"), (5, "M"), (7, "M")],     # I vi IV V
        [(0, "m"), (-4, "M"), (-9, "M"), (-2, "M")],  # i VI III VII
        [(0, "M"), (5, "M"), (9, "m"), (7, "M")],     # I IV vi V
    ]),
    "tech-pulse": dict(root=(50, 57), kit="four", leads=["saw", "square"], bright=0.8, progs=[
        [(0, "m"), (0, "m"), (-4, "M"), (-2, "M")],
        [(0, "m"), (-2, "M"), (-4, "M"), (-5, "m")],
        [(0, "m"), (3, "M"), (-2, "M"), (-4, "M")],
        [(0, "m"), (-4, "M"), (3, "M"), (-2, "M")],
    ]),
    "warm-pluck": dict(root=(57, 64), kit="soft", leads=["pluck", "sine"], bright=0.6, progs=[
        [(0, "M"), (-5, "M"), (-3, "m"), (-7, "M")],
        [(0, "M"), (4, "m"), (5, "M"), (7, "M")],     # I iii IV V
        [(0, "M"), (2, "m"), (5, "M"), (0, "M")],     # I ii IV I
        [(0, "M"), (9, "m"), (2, "m"), (7, "M")],     # I vi ii V
    ]),
    "hype-trap": dict(root=(48, 55), kit="trap", leads=["saw", "square"], bright=0.9, progs=[
        [(0, "m"), (-4, "M"), (-2, "M"), (-5, "m")],
        [(0, "m"), (1, "M"), (0, "m"), (-2, "M")],    # 弗里吉亞色彩
        [(0, "m"), (-4, "M"), (-7, "m"), (-2, "M")],
        [(0, "m"), (3, "M"), (-4, "M"), (-2, "M")],
    ]),
}
ARP_PATTERNS = [[0, 1, 2, 1], [0, 2, 1, 2], [0, 1, 2, 3], [2, 1, 0, 1], [0, 2, 3, 2]]
# 旋律節奏型（一小節 8 個八分格：1=起音、0=休止）
RHYTHMS = [
    [1, 0, 1, 0, 1, 1, 0, 0], [1, 0, 0, 1, 0, 1, 1, 0], [1, 1, 0, 1, 0, 0, 1, 0],
    [1, 0, 1, 1, 0, 1, 0, 0], [0, 1, 1, 0, 1, 0, 1, 0], [1, 0, 0, 0, 1, 1, 1, 0],
]


def seed_from(text):
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:8], 16)


def project_name_from(out_path):
    """assets/bgm.wav → 取專案資料夾名；否則取輸出檔所在資料夾名。"""
    d = os.path.dirname(os.path.abspath(out_path))
    if os.path.basename(d).lower() in ("assets", "audio", "media"):
        d = os.path.dirname(d)
    return os.path.basename(d)


def make_motif(rng, bars=2):
    """一段 2 小節旋律動機：[(八分格位置, 音階級數, 長度格數), ...]"""
    notes = []
    deg = int(rng.integers(2, 5))
    for b in range(bars):
        rhy = RHYTHMS[int(rng.integers(len(RHYTHMS)))]
        for i, on in enumerate(rhy):
            if not on:
                continue
            deg = int(np.clip(deg + rng.choice([-2, -1, -1, 0, 1, 1, 2]), 0, 7))
            length = 1
            while i + length < 8 and not rhy[i + length] and length < 3:
                length += 1
            notes.append((b * 8 + i, deg, length))
    return notes


def midi_hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def env(n, a=0.005, d=0.2, s=0.0, r=0.05, hold=None):
    """簡易 ADSR（秒）→ 長度 n 的包絡。"""
    t = np.arange(n) / SR
    e = np.zeros(n)
    a_n = max(1, int(a * SR))
    e[:a_n] = np.linspace(0, 1, a_n)[: len(e[:a_n])]
    rest = t[a_n:] - a
    e[a_n:] = s + (1 - s) * np.exp(-rest / max(d, 1e-4))
    if r and n > int(r * SR):
        r_n = int(r * SR)
        e[-r_n:] *= np.linspace(1, 0, r_n)
    return e


def osc(kind, f, n, rng):
    t = np.arange(n) / SR
    ph = 2 * np.pi * f * t
    if kind == "sine":
        return np.sin(ph)
    if kind == "square":
        return np.sign(np.sin(ph)) * 0.6 + np.sin(ph) * 0.4
    if kind == "saw":
        # 兩支微失諧鋸齒波，較厚
        return (2 * ((f * t) % 1) - 1) * 0.5 + (2 * ((f * 1.006 * t) % 1) - 1) * 0.5
    if kind == "pluck":
        return np.sin(ph) * 0.7 + np.sin(ph * 2) * 0.2 + np.sin(ph * 3) * 0.1
    return np.sin(ph)


def lowpass(x, cutoff):
    """一階低通（scipy lfilter，快速且可重現）。"""
    if cutoff >= SR / 2:
        return x
    rc = 1.0 / (2 * np.pi * cutoff)
    alpha = (1 / SR) / (rc + 1 / SR)
    return lfilter([alpha], [1, alpha - 1], x)


def kick(n):
    t = np.arange(n) / SR
    f = 50 + 110 * np.exp(-t * 28)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph) * np.exp(-t * 7.5)


def snare(n, rng):
    t = np.arange(n) / SR
    noise = rng.standard_normal(n) * np.exp(-t * 18)
    body = np.sin(2 * np.pi * 190 * t) * np.exp(-t * 25)
    return noise * 0.55 + body * 0.45


def hat(n, rng, open_=False):
    t = np.arange(n) / SR
    noise = rng.standard_normal(n)
    noise = noise - lowpass(noise, 6000)  # 高通
    return noise * np.exp(-t * (9 if open_ else 55))


def place(buf, sig, start, gain=1.0, pan=0.0):
    i = int(start * SR)
    if i >= buf.shape[0]:
        return
    j = min(buf.shape[0], i + len(sig))
    s = sig[: j - i] * gain
    buf[i:j, 0] += s * (1 - max(0, pan))
    buf[i:j, 1] += s * (1 + min(0, pan))


def build(args):
    if args.seed is not None:
        seed, seed_src = args.seed, "--seed"
    else:
        name = args.project or project_name_from(args.out)
        seed, seed_src = seed_from(f"{name}|{args.style}|v{args.variant}"), f"project:{name}"
    rng = np.random.default_rng(seed)
    st = STYLES[args.style]
    # --- 依種子抽出本首的變化 ---
    key_root = int(rng.integers(st["root"][0], st["root"][1] + 1))
    prog = st["progs"][int(rng.integers(len(st["progs"])))]
    arp_pat = ARP_PATTERNS[int(rng.integers(len(ARP_PATTERNS)))]
    lead = st["leads"][int(rng.integers(len(st["leads"])))]
    hat_off = bool(rng.integers(2))          # 只打反拍 hi-hat，或正反拍都打
    kick_extra = bool(rng.integers(2))       # drop 內加一個切分大鼓
    scale = [0, 3, 5, 7, 10] if prog[0][1] == "m" else [0, 2, 4, 7, 9]
    motif_a, motif_b = make_motif(rng), make_motif(rng)
    variation = dict(key_root_midi=key_root, progression=prog, arp=arp_pat, lead=lead,
                     hat_offbeat_only=hat_off, kick_syncopation=kick_extra, scale=scale)
    bpm = args.bpm
    beat = 60.0 / bpm
    bar = beat * 4
    total = args.duration
    n_total = int(total * SR)
    buf = np.zeros((n_total, 2))

    n_bars = int(math.ceil(total / bar))
    # 段落切分：intro 前 ~15%、build 到 ~35%、drop 到結尾前 1 小節、outro 最後 1 小節
    b_intro = max(1, round(n_bars * 0.15))
    b_build = max(b_intro + 1, round(n_bars * 0.35))
    b_outro = n_bars - 1
    sections = []
    for name, a, b in [("intro", 0, b_intro), ("build", b_intro, b_build), ("drop", b_build, b_outro), ("outro", b_outro, n_bars)]:
        sections.append({"name": name, "start": round(a * bar, 3), "end": round(min(b * bar, total), 3)})

    k_n, s_n, h_n = int(0.45 * SR), int(0.3 * SR), int(0.35 * SR)
    K, S = kick(k_n), snare(s_n, rng)
    H, HO = hat(int(0.06 * SR), rng), hat(h_n, rng, open_=True)

    beats, downbeats, hits = [], [], []
    for bi in range(n_bars):
        sec = "intro" if bi < b_intro else "build" if bi < b_build else "outro" if bi >= b_outro else "drop"
        t0 = bi * bar
        downbeats.append(round(t0, 3))
        chord_rel, quality = prog[bi % len(prog)]
        root = key_root + chord_rel
        while root > key_root + 6:
            root -= 12
        third = 3 if quality == "m" else 4
        chord = [root, root + third, root + 7, root + 12]

        # --- 鼓 ---
        for q in range(4):
            tq = t0 + q * beat
            if tq >= total:
                break
            beats.append(round(tq, 3))
            if sec == "intro":
                if q == 0:
                    place(buf, K, tq, 0.55)
                continue
            if st["kit"] == "trap":
                if q in (0,) or (q == 2 and bi % 2):
                    place(buf, K, tq, 0.95)
                if q == 2:
                    place(buf, S, tq, 0.5)
                for s16 in range(4):  # 16 分 hi-hat
                    place(buf, H, tq + s16 * beat / 4, 0.12 + 0.05 * (s16 % 2), 0.3)
            elif st["kit"] == "soft":
                if q in (0, 2):
                    place(buf, K, tq, 0.6)
                if q in (1, 3) and sec != "build":
                    place(buf, S, tq, 0.22)
                place(buf, H, tq + beat / 2, 0.08, 0.25)
            else:  # four-on-the-floor
                place(buf, K, tq, 0.9 if sec == "drop" else 0.7)
                if kick_extra and sec == "drop" and q == 2:
                    place(buf, K, tq + beat * 0.75, 0.5)
                if q in (1, 3) and sec == "drop":
                    place(buf, S, tq, 0.42)
                place(buf, HO if sec == "drop" else H, tq + beat / 2, 0.09 if sec == "drop" else 0.1, -0.25)
                if not hat_off:
                    place(buf, H, tq, 0.06, 0.25)
            if sec == "build" and bi == b_build - 1:  # 軍鼓滾奏加速
                for r in range(4):
                    place(buf, S, tq + r * beat / 4, 0.12 + 0.08 * q + 0.02 * r)

        # --- 貝斯（八分音符，drop 才全開）---
        if sec in ("build", "drop"):
            for e8 in range(8):
                te = t0 + e8 * beat / 2
                if te >= total:
                    break
                n = int(beat / 2 * SR * 0.9)
                note = root - 12 + (12 if (sec == "drop" and e8 % 4 == 3) else 0)
                sig = osc("saw", midi_hz(note), n, rng)
                sig = lowpass(sig, 380 if sec == "build" else 700) * env(n, 0.003, 0.18, 0.35, 0.02)
                place(buf, sig, te, 0.28 if sec == "drop" else 0.18)

        # --- 和弦 pad（全段）---
        n = int(bar * SR)
        pad = sum(osc("saw" if lead != "pluck" else "sine", midi_hz(m), n, rng) for m in chord) / len(chord)
        cut = {"intro": 900, "build": 1400, "drop": 2600 * st["bright"], "outro": 1000}[sec]
        pad = lowpass(pad, cut) * env(n, 0.08, 3.0, 0.7, 0.2)
        place(buf, pad, t0, 0.13, 0.0)

        # --- 主旋律琶音（drop 才出現，十六分跳動＝彈性感）---
        if sec == "drop":
            arp = [chord[i] + 12 for i in arp_pat]
            for s16 in range(16):
                ts = t0 + s16 * beat / 4
                if ts >= total:
                    break
                if s16 % 4 == 2 and st["kit"] == "trap":
                    continue
                n = int(beat / 4 * SR)
                m = arp[s16 % 4]
                sig = osc(lead, midi_hz(m), n, rng)
                sig = lowpass(sig, 3200 * st["bright"]) * env(n, 0.002, 0.07, 0.0, 0.01)
                place(buf, sig, ts, 0.05, 0.35 if s16 % 2 else -0.35)

        # --- 旋律（drop 內，2 小節動機依 A A' B A 循環）---
        if sec == "drop":
            k = bi - b_build                   # drop 內第幾小節
            phrase = (k // 2) % 4              # 0:A 1:A' 2:B 3:A
            motif = motif_b if phrase == 2 else motif_a
            half = k % 2
            for pos, deg, length in motif:
                if pos // 8 != half:
                    continue
                if phrase == 1 and pos == motif[-1][0]:
                    deg = max(0, deg - 2)      # A' 句尾換音
                tm = t0 + (pos % 8) * beat / 2
                if tm >= total:
                    continue
                octave, idx = divmod(deg, len(scale))
                m = key_root + 12 + scale[idx] + 12 * octave
                n = int(length * beat / 2 * SR)
                sig = osc("sine" if lead == "saw" else lead, midi_hz(m), n, rng) * 0.7 + osc("sine", midi_hz(m + 12), n, rng) * 0.15
                sig = lowpass(sig, 4200 * st["bright"]) * env(n, 0.006, 0.35, 0.45, 0.05)
                place(buf, sig, tm, 0.11, 0.1)

    # --- 上升音效（build 最後一小節）＋ drop 重擊 ---
    drop_t = b_build * bar
    rise_n = int(bar * SR)
    t = np.arange(rise_n) / SR
    noise = rng.standard_normal(rise_n)
    riser = (noise - lowpass(noise, 1500)) * (t / t[-1]) ** 2
    place(buf, riser, drop_t - bar, 0.22)
    hits.append({"t": round(drop_t, 3), "kind": "drop"})
    imp_n = int(1.2 * SR)
    ti = np.arange(imp_n) / SR
    impact = np.sin(2 * np.pi * (40 + 60 * np.exp(-ti * 6)) * ti) * np.exp(-ti * 3) + rng.standard_normal(imp_n) * np.exp(-ti * 14) * 0.4
    place(buf, impact, drop_t, 0.7)
    # 片尾收束重擊
    end_hit = sections[-1]["start"]
    place(buf, impact, end_hit, 0.55)
    hits.append({"t": round(end_hit, 3), "kind": "outro"})
    # 每 2 小節（drop 內）一個次重拍，給畫面切場用
    for bi in range(b_build + 2, b_outro, 2):
        hits.append({"t": round(bi * bar, 3), "kind": "accent"})

    # --- 母帶：淡入淡出＋軟削波＋正規化 ---
    fade_in, fade_out = int(0.05 * SR), int(1.5 * SR)
    buf[:fade_in] *= np.linspace(0, 1, fade_in)[:, None]
    buf[-fade_out:] *= np.linspace(1, 0, fade_out)[:, None]
    buf = np.tanh(buf * 1.4)
    buf = buf / (np.max(np.abs(buf)) + 1e-9) * 0.89
    wavfile.write(args.out, SR, (buf * 32767).astype(np.int16))

    meta = {
        "generator": "promo-ad-forge/synth_bgm.py",
        "royalty_free": True,
        "style": args.style,
        "seed": seed,
        "seed_source": seed_src,
        "variant": args.variant,
        "variation": variation,
        "bpm": bpm,
        "beat_sec": round(beat, 4),
        "bar_sec": round(bar, 4),
        "duration": total,
        "beats": [b for b in beats if b < total],
        "downbeats": [d for d in downbeats if d < total],
        "sections": sections,
        "hits": sorted(hits, key=lambda h: h["t"]),
    }
    with open(args.beats, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(json.dumps({k: meta[k] for k in ("style", "seed", "seed_source", "variation", "bpm")}, ensure_ascii=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--beats", required=True)
    ap.add_argument("--bpm", type=float, default=120)
    ap.add_argument("--duration", type=float, default=30)
    ap.add_argument("--style", choices=list(STYLES), default="pop-bounce")
    ap.add_argument("--project", help="專案名；決定這首歌的種子（預設取輸出檔所在專案資料夾名）")
    ap.add_argument("--variant", type=int, default=1, help="同專案想換一首就改成 2、3…")
    ap.add_argument("--seed", type=int, default=None, help="手動指定種子（覆蓋 --project）")
    build(ap.parse_args())
