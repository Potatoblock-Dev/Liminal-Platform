#!/usr/bin/env python3
"""从「火车经过」长录音中裁出可无缝循环的行驶 rumble 段。

优先选取低频轰隆、少铃铛/叮当的区间，并做低通以去掉叮叮当当。

用法:
  python3 scripts/process_train_move_loop.py \\
    --input "/path/火车经过（需要处理）.mp3" \\
    --output game/Liminal_Platform/static/audio/train-move-loop.m4a
"""

from __future__ import annotations

import argparse
import math
import struct
import subprocess
import wave
from pathlib import Path


def to_mono_int16(raw: bytes, channels: int) -> bytes:
    """交错 PCM 下混为 mono int16。"""
    count = len(raw) // 2
    samples = struct.unpack(f"<{count}h", raw)
    if channels == 1:
        return raw
    mono: list[int] = []
    for i in range(0, count, channels):
        acc = sum(samples[i : i + channels])
        mono.append(int(acc / channels))
    return struct.pack(f"<{len(mono)}h", *mono)


def read_wav_mono(path: Path) -> tuple[list[int], int]:
    """读取 WAV 并下混为 mono int16 样本。"""
    with wave.open(str(path), "rb") as wf:
        channels = wf.getnchannels()
        width = wf.getsampwidth()
        rate = wf.getframerate()
        raw = wf.readframes(wf.getnframes())
    if width != 2:
        raise SystemExit(f"仅支持 16-bit WAV，当前 width={width}")
    mono = to_mono_int16(raw, channels)
    samples = struct.unpack(f"<{len(mono) // 2}h", mono)
    return list(samples), rate


def write_wav_mono(path: Path, samples: list[int], rate: int) -> None:
    """写出 mono int16 WAV。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(struct.pack(f"<{len(samples)}h", *samples))


def rms_window(values: list[int]) -> float:
    """计算窗口 RMS。"""
    if not values:
        return 0.0
    acc = sum(v * v for v in values)
    return math.sqrt(acc / len(values))


def hf_proxy(values: list[int]) -> float:
    """高频代理：平均绝对一阶差分（铃铛/叮当偏高）。"""
    if len(values) < 2:
        return 0.0
    step = 4
    acc = 0.0
    n = 0
    for i in range(0, len(values) - 1, step):
        acc += abs(values[i + 1] - values[i])
        n += 1
    return acc / max(1, n)


def zero_crossing_rate(values: list[int]) -> float:
    """过零率：金属叮当通常更高。"""
    if len(values) < 2:
        return 0.0
    flips = 0
    for i in range(len(values) - 1):
        if (values[i] >= 0) != (values[i + 1] >= 0):
            flips += 1
    return flips / len(values)


def rumble_score(rms: float, hf: float, zc: float) -> float:
    """越高越像稳定轰隆（大声 + 低频主导）。"""
    return rms / (1.0 + hf / 80.0) / (1.0 + zc * 40.0)


def find_rumble_loop_region(
    samples: list[int],
    rate: int,
    loop_seconds: float = 4.0,
) -> tuple[int, int]:
    """在少叮当、多轰隆的稳定段中选取循环区间（样本索引）。"""
    win = int(rate * 0.25)
    hop = int(rate * 0.125)
    metrics: list[tuple[float, float, float]] = []
    for i in range(0, len(samples) - win, hop):
        seg = samples[i : i + win]
        metrics.append(
            (
                rms_window(seg),
                hf_proxy(seg),
                zero_crossing_rate(seg),
            )
        )

    if len(metrics) < 8:
        raise SystemExit("音频太短，无法分析")

    peak_rms = max(m[0] for m in metrics)
    loop_windows = max(1, int(loop_seconds / 0.125))
    best_idx = 0
    best_score = None
    for i in range(0, len(metrics) - loop_windows):
        seg = metrics[i : i + loop_windows]
        mean_rms = sum(m[0] for m in seg) / len(seg)
        if mean_rms < peak_rms * 0.45:
            continue
        scores = [rumble_score(r, h, z) for r, h, z in seg]
        mean_score = sum(scores) / len(scores)
        var = sum((s - mean_score) ** 2 for s in scores) / len(scores)
        # 稳定 + 高 rumble 分
        total = mean_score - math.sqrt(var) * 0.15
        if best_score is None or total > best_score:
            best_score = total
            best_idx = i

    loop_len = int(rate * loop_seconds)
    loop_start = best_idx * hop
    return loop_start, loop_start + loop_len


def lowpass_one_pole(samples: list[int], rate: int, cutoff_hz: float) -> list[int]:
    """单极低通，压掉叮叮当当等高频金属声。"""
    rc = 1.0 / (2.0 * math.pi * cutoff_hz)
    dt = 1.0 / rate
    alpha = dt / (rc + dt)
    out: list[int] = []
    y = 0.0
    for x in samples:
        y += alpha * (float(x) - y)
        out.append(int(max(-32767, min(32767, round(y)))))
    return out


def normalize_peak(samples: list[int], peak: float = 0.88) -> list[int]:
    """峰值归一化，避免低通后过小。"""
    max_abs = max((abs(v) for v in samples), default=1)
    if max_abs < 1:
        return samples
    scale = (32767 * peak) / max_abs
    return [int(max(-32767, min(32767, round(v * scale)))) for v in samples]


def apply_loop_crossfade(segment: list[int], rate: int, fade_ms: int = 100) -> list[int]:
    """首尾交叉淡入淡出，便于 Web Audio 循环。"""
    fade = int(rate * fade_ms / 1000)
    fade = max(1, min(fade, len(segment) // 4))
    out = segment[:]
    for i in range(fade):
        t = i / fade
        out[i] = int(out[i] * t + out[-fade + i] * (1 - t))
        out[-fade + i] = int(out[-fade + i] * t + segment[i] * (1 - t))
    return out


def convert_to_m4a(wav_path: Path, m4a_path: Path) -> None:
    """用 macOS afconvert 导出 AAC（m4a）。"""
    m4a_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "afconvert",
            "-f",
            "mp4f",
            "-d",
            "aac",
            "-b",
            "96000",
            str(wav_path),
            str(m4a_path),
        ],
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="裁切火车行驶循环音效（轰隆、去叮当）")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--work-wav", type=Path, default=None)
    parser.add_argument("--loop-seconds", type=float, default=4.0)
    parser.add_argument("--lowpass-hz", type=float, default=380.0)
    parser.add_argument(
        "--start",
        type=float,
        default=None,
        help="手动指定起点秒数（跳过自动选段）",
    )
    args = parser.parse_args()

    work_wav = args.work_wav or args.output.with_suffix(".work.wav")
    loop_wav = args.output.with_suffix(".loop.wav")

    if args.input.suffix.lower() == ".wav":
        full_wav = args.input
    else:
        work_wav.parent.mkdir(parents=True, exist_ok=True)
        # 部分 mp3 直接转 WAVE 会失败，先走 CAF 再转 WAV
        caf_path = work_wav.with_suffix(".caf")
        subprocess.run(
            ["afconvert", "-f", "caff", "-d", "LEI16", str(args.input), str(caf_path)],
            check=True,
        )
        subprocess.run(
            ["afconvert", "-f", "WAVE", "-d", "LEI16", str(caf_path), str(work_wav)],
            check=True,
        )
        full_wav = work_wav

    samples, rate = read_wav_mono(full_wav)
    if args.start is not None:
        start = int(args.start * rate)
        end = start + int(args.loop_seconds * rate)
        end = min(end, len(samples))
    else:
        start, end = find_rumble_loop_region(samples, rate, args.loop_seconds)

    loop = samples[start:end]
    loop = lowpass_one_pole(loop, rate, args.lowpass_hz)
    loop = normalize_peak(loop)
    loop = apply_loop_crossfade(loop, rate)
    write_wav_mono(loop_wav, loop, rate)
    convert_to_m4a(loop_wav, args.output)

    duration = len(loop) / rate
    print(f"loop: {duration:.2f}s @ {rate}Hz")
    print(f"source slice: {start / rate:.1f}s – {end / rate:.1f}s")
    print(f"lowpass: {args.lowpass_hz:.0f} Hz")
    print(f"written: {args.output}")


if __name__ == "__main__":
    main()
