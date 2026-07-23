"""生成默认的彩色色块 UV 皮套（与占位小人配色一致）。

用法：python scripts/generate_default_uv_skin.py [skin_id]
不传 skin_id 时新建 defaultuvblocks；传入已有 id 则原地替换其贴图。

版式必须与 static/js/uv-layout.js 的 PARTS 保持一致（683×512 4:3，LAYOUT_VERSION 5）。
默认皮套只在推荐区（core）填色，右侧留白透明。
"""

from __future__ import annotations

import json
import struct
import sys
import time
import zlib
from pathlib import Path

ATLAS_WIDTH = 683
ATLAS_HEIGHT = 512

# 与 uv-layout.js PARTS 同步：推荐区 [x, y, 宽, 高] 与配色。
PART_CORES = {
    "head": ([98, 14, 63, 52], "#facc15"),
    "body": ([341, 14, 88, 104], "#22c55e"),
    "frontArmUpper": ([51, 287, 28, 60], "#f97316"),
    "frontArmLower": ([177, 285, 28, 64], "#fb923c"),
    "backArmUpper": ([303, 287, 28, 60], "#ef4444"),
    "backArmLower": ([429, 285, 28, 64], "#f87171"),
    "frontLegUpper": ([49, 407, 32, 64], "#8b5cf6"),
    "frontLegLower": ([175, 405, 32, 68], "#a78bfa"),
    "backLegUpper": ([301, 407, 32, 64], "#3b82f6"),
    "backLegLower": ([427, 405, 32, 68], "#60a5fa"),
}

HEAD_EYE = (140, 30, 11, 11, "#111827")


def hex_to_rgba(value: str) -> tuple:
    """'#rrggbb' 转为不透明 RGBA 元组。"""
    return (int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16), 255)


def fill_rect(pixels: bytearray, x: int, y: int, w: int, h: int, rgba: tuple) -> None:
    """在 RGBA 像素缓冲上填充矩形。"""
    row = bytes(rgba) * w
    for dy in range(h):
        offset = ((y + dy) * ATLAS_WIDTH + x) * 4
        pixels[offset:offset + w * 4] = row


def write_png(path: Path, pixels: bytearray) -> None:
    """把 RGBA 缓冲编码为最简 PNG（无滤波）写入文件。"""
    def chunk(tag: bytes, data: bytes) -> bytes:
        payload = tag + data
        return struct.pack(">I", len(data)) + payload + struct.pack(">I", zlib.crc32(payload) & 0xFFFFFFFF)

    stride = ATLAS_WIDTH * 4
    raw = b"".join(
        b"\x00" + bytes(pixels[y * stride:(y + 1) * stride]) for y in range(ATLAS_HEIGHT)
    )
    header = struct.pack(">IIBBBBB", ATLAS_WIDTH, ATLAS_HEIGHT, 8, 6, 0, 0, 0)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def build_atlas() -> bytearray:
    """按版式在推荐区画出各部位色块，返回 RGBA 缓冲。"""
    pixels = bytearray(ATLAS_WIDTH * ATLAS_HEIGHT * 4)
    for rect, color in PART_CORES.values():
        fill_rect(pixels, *rect, hex_to_rgba(color))
    fill_rect(pixels, *HEAD_EYE[:4], hex_to_rgba(HEAD_EYE[4]))
    return pixels


def main() -> None:
    """生成贴图并写入皮套目录（含 manifest）。"""
    skin_id = sys.argv[1] if len(sys.argv) > 1 else "defaultuvblocks"
    project_root = Path(__file__).resolve().parents[1]
    skin_dir = project_root / "var" / "uploads" / "skins" / skin_id
    skin_dir.mkdir(parents=True, exist_ok=True)

    write_png(skin_dir / "texture.png", build_atlas())
    manifest = {
        "id": skin_id,
        "name": "默认色块皮套",
        "uploader_id": "system",
        "texture": "texture.png",
        "kind": "uv",
        "height_scale": 1.0,
        "format_version": 0,
        "created_at": int(time.time()),
    }
    (skin_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"written: {skin_dir}")


if __name__ == "__main__":
    main()
