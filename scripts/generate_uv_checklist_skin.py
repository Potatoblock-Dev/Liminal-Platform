"""生成「功能自检」UV 贴图：导入编辑器或直接当皮套用，可肉眼核对各项要求。

覆盖检测：
- 683×512 版式与各部位槽是否对齐
- 头部/头发整身画布 + 长发越过 safeRect
- 肢体朝向（顶部=关节侧，底部=远端）与平移网格
- 部位色块区分、朝右默认

用法：
  python scripts/generate_uv_checklist_skin.py
  → samples/uv-checklist.png（方便本地导入编辑器）
  → var/uploads/skins/uvchecklist/（大厅皮套列表可直接选）
"""

from __future__ import annotations

import json
import struct
import time
import zlib
from pathlib import Path

ATLAS_WIDTH = 683
ATLAS_HEIGHT = 512
CONTENT_WIDTH = 512

# 与 uv-layout.js PARTS 同步（LAYOUT_VERSION 5，4:3 画幅）
PARTS = {
    "head": {
        "rect": [4, 4, 250, 250],
        "color": (250, 204, 21, 255),
        "tag": "HD",
        "draw_rect": [-36, -36, 72, 72],
        "safe_rect": [-9, -33, 18, 15],
    },
    "body": {"rect": [262, 4, 246, 250], "color": (34, 197, 94, 255), "tag": "BD"},
    "frontArmUpper": {"rect": [4, 258, 122, 118], "color": (249, 115, 22, 255), "tag": "RA1"},
    "frontArmLower": {"rect": [130, 258, 122, 118], "color": (251, 146, 60, 255), "tag": "RA2"},
    "backArmUpper": {"rect": [256, 258, 122, 118], "color": (239, 68, 68, 255), "tag": "LA1"},
    "backArmLower": {"rect": [382, 258, 122, 118], "color": (248, 113, 113, 255), "tag": "LA2"},
    "frontLegUpper": {"rect": [4, 380, 122, 118], "color": (139, 92, 246, 255), "tag": "RL1"},
    "frontLegLower": {"rect": [130, 380, 122, 118], "color": (167, 139, 250, 255), "tag": "RL2"},
    "backLegUpper": {"rect": [256, 380, 122, 118], "color": (59, 130, 246, 255), "tag": "LL1"},
    "backLegLower": {"rect": [382, 380, 122, 118], "color": (96, 165, 250, 255), "tag": "LL2"},
}

# 5×7 点阵，覆盖标签用字母与数字
GLYPHS = {
    " ": [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00],
    "A": [0x0E, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11],
    "B": [0x1E, 0x11, 0x11, 0x1E, 0x11, 0x11, 0x1E],
    "D": [0x1E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x1E],
    "E": [0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x1F],
    "F": [0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x10],
    "H": [0x11, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11],
    "J": [0x01, 0x01, 0x01, 0x01, 0x11, 0x11, 0x0E],
    "L": [0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x1F],
    "O": [0x0E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E],
    "R": [0x1E, 0x11, 0x11, 0x1E, 0x14, 0x12, 0x11],
    "T": [0x1F, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04],
    "U": [0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E],
    "Y": [0x11, 0x11, 0x0A, 0x04, 0x04, 0x04, 0x04],
    "0": [0x0E, 0x11, 0x13, 0x15, 0x19, 0x11, 0x0E],
    "1": [0x04, 0x0C, 0x04, 0x04, 0x04, 0x04, 0x0E],
    "2": [0x0E, 0x11, 0x01, 0x06, 0x08, 0x10, 0x1F],
    "4": [0x02, 0x06, 0x0A, 0x12, 0x1F, 0x02, 0x02],
    "5": [0x1F, 0x10, 0x1E, 0x01, 0x01, 0x11, 0x0E],
    "X": [0x11, 0x11, 0x0A, 0x04, 0x0A, 0x11, 0x11],
    "+": [0x00, 0x04, 0x04, 0x1F, 0x04, 0x04, 0x00],
    "-": [0x00, 0x00, 0x00, 0x1F, 0x00, 0x00, 0x00],
    ">": [0x08, 0x04, 0x02, 0x01, 0x02, 0x04, 0x08],
    "V": [0x11, 0x11, 0x11, 0x11, 0x11, 0x0A, 0x04],
}


def set_px(pixels: bytearray, x: int, y: int, rgba: tuple) -> None:
    """写单个像素（越界忽略）。"""
    if x < 0 or y < 0 or x >= ATLAS_WIDTH or y >= ATLAS_HEIGHT:
        return
    offset = (y * ATLAS_WIDTH + x) * 4
    pixels[offset:offset + 4] = bytes(rgba)


def fill_rect(pixels: bytearray, x: int, y: int, w: int, h: int, rgba: tuple) -> None:
    """填充矩形。"""
    for dy in range(h):
        for dx in range(w):
            set_px(pixels, x + dx, y + dy, rgba)


def draw_rect_outline(pixels: bytearray, x: int, y: int, w: int, h: int, rgba: tuple) -> None:
    """画 1px 矩形边框。"""
    for i in range(w):
        set_px(pixels, x + i, y, rgba)
        set_px(pixels, x + i, y + h - 1, rgba)
    for i in range(h):
        set_px(pixels, x, y + i, rgba)
        set_px(pixels, x + w - 1, y + i, rgba)


def draw_checker(
    pixels: bytearray,
    x: int,
    y: int,
    w: int,
    h: int,
    a: tuple,
    b: tuple,
    cell: int = 4,
) -> None:
    """棋盘格，方便平移后看出错位。"""
    for dy in range(h):
        for dx in range(w):
            color = a if ((dx // cell) + (dy // cell)) % 2 == 0 else b
            set_px(pixels, x + dx, y + dy, color)


def blit_glyph(pixels: bytearray, gx: int, gy: int, ch: str, rgba: tuple, scale: int = 1) -> None:
    """画一个 5×7 字符。"""
    rows = GLYPHS.get(ch.upper(), GLYPHS["X"])
    for row, bits in enumerate(rows):
        for col in range(5):
            if bits & (1 << (4 - col)):
                for sy in range(scale):
                    for sx in range(scale):
                        set_px(pixels, gx + col * scale + sx, gy + row * scale + sy, rgba)


def draw_text(pixels: bytearray, x: int, y: int, text: str, rgba: tuple, scale: int = 1) -> None:
    """从左上角开始画一行点阵字。"""
    cursor = x
    for ch in text:
        blit_glyph(pixels, cursor, y, ch, rgba, scale)
        cursor += 6 * scale


def draw_cross(pixels: bytearray, cx: int, cy: int, rgba: tuple, arm: int = 3) -> None:
    """关节十字标记。"""
    for i in range(-arm, arm + 1):
        set_px(pixels, cx + i, cy, rgba)
        set_px(pixels, cx, cy + i, rgba)


def draw_down_arrow(pixels: bytearray, cx: int, y0: int, y1: int, rgba: tuple) -> None:
    """从上到下的方向箭头（远端朝下）。"""
    for y in range(y0, y1):
        set_px(pixels, cx, y, rgba)
    tip = y1 - 1
    for i in range(4):
        set_px(pixels, cx - i, tip - i, rgba)
        set_px(pixels, cx + i, tip - i, rgba)


def world_to_head_atlas(wx: float, wy: float) -> tuple[int, int]:
    """角色坐标 → 头部槽像素（drawRect [-36,-36,72,72] → rect [4,4,250,250]）。"""
    draw = PARTS["head"]["draw_rect"]
    slot = PARTS["head"]["rect"]
    scale_x = slot[2] / draw[2]
    scale_y = slot[3] / draw[3]
    ax = int(round(slot[0] + (wx - draw[0]) * scale_x))
    ay = int(round(slot[1] + (wy - draw[1]) * scale_y))
    return ax, ay


def draw_long_hair(pixels: bytearray) -> None:
    """在头部槽画越过 safeRect 的长发，验证整身画布。"""
    # safeRect 世界坐标 [-11,-35,22,18] → 头部轮廓
    hair = (120, 53, 15, 230)
    highlight = (180, 90, 30, 200)
    scale = PARTS["head"]["rect"][2] / PARTS["head"]["draw_rect"][2]
    # 头顶发量（safe 上方与两侧）
    sx, sy = world_to_head_atlas(-14, -40)
    fill_rect(pixels, sx, sy, int(28 * scale), max(8, int(8 * scale)), hair)
    # 两侧披发落到肩/胸高度（越过头部轮廓）
    for side, ox in ((-1, -18), (1, 8)):
        base_x, base_y = world_to_head_atlas(ox, -28)
        for i in range(22):
            y = base_y + i * 6
            w = 10 + (i % 3) * 2
            x = base_x + side * (i // 2)
            fill_rect(pixels, x, y, w, 7, hair if i % 2 == 0 else highlight)
    # 后发中线落到腰部附近（约 y=0~10 世界坐标）
    mx, my = world_to_head_atlas(-3, -20)
    for i in range(28):
        fill_rect(pixels, mx - 4 + (i % 3), my + i * 5, 10, 6, hair)


def draw_limb_guides(pixels: bytearray, x: int, y: int, w: int, h: int, tag: str, base: tuple) -> None:
    """肢体槽：棋盘 + 顶部关节十字 + 下行箭头 + 标签。"""
    light = tuple(min(255, c + 40) if i < 3 else c for i, c in enumerate(base))
    dark = tuple(max(0, c - 35) if i < 3 else c for i, c in enumerate(base))
    draw_checker(pixels, x, y, w, h, light, dark, cell=4)
    # 顶部=关节侧
    ink = (17, 24, 39, 255)
    draw_cross(pixels, x + w // 2, y + 4, ink, arm=max(2, w // 6))
    # 白边框提示槽边界
    draw_rect_outline(pixels, x, y, w, h, (255, 255, 255, 180))
    if h >= 20:
        draw_down_arrow(pixels, x + w // 2, y + 8, y + h - 3, ink)
    if w >= 20 and h >= 16:
        draw_text(pixels, x + 2, y + h // 2 - 3, tag, ink, scale=1)


def draw_body_slot(pixels: bytearray) -> None:
    """身体槽：网格 + 中线 + BODY 标签。"""
    x, y, w, h = PARTS["body"]["rect"]
    base = PARTS["body"]["color"]
    light = (74, 222, 128, 255)
    dark = (22, 163, 74, 255)
    draw_checker(pixels, x, y, w, h, light, dark, cell=8)
    ink = (17, 24, 39, 255)
    # 竖直中线，便于判断贴图左右是否偏了
    for yy in range(y, y + h):
        set_px(pixels, x + w // 2, yy, ink)
    draw_rect_outline(pixels, x, y, w, h, (255, 255, 255, 200))
    draw_text(pixels, x + 8, y + 8, "BODY", ink, scale=2)
    draw_text(pixels, x + 8, y + h - 16, "FACE>", ink, scale=1)


def draw_head_slot(pixels: bytearray) -> None:
    """头部整身画布：透明底 + 长发 + safe 黄框 + 面部色块。"""
    x, y, w, h = PARTS["head"]["rect"]
    # 淡灰点阵底，方便看出透明区范围（仍半透明）
    for dy in range(0, h, 16):
        for dx in range(0, w, 16):
            set_px(pixels, x + dx, y + dy, (148, 163, 184, 40))

    draw_long_hair(pixels)

    # safeRect 映射到 atlas
    safe = PARTS["head"]["safe_rect"]
    draw = PARTS["head"]["draw_rect"]
    slot = PARTS["head"]["rect"]
    scale_x = slot[2] / draw[2]
    scale_y = slot[3] / draw[3]
    sx, sy = world_to_head_atlas(safe[0], safe[1])
    sw, sh = int(round(safe[2] * scale_x)), int(round(safe[3] * scale_y))
    # 面部色块（略小于 safe，留边）
    face = PARTS["head"]["color"]
    fill_rect(pixels, sx + 4, sy + 4, max(4, sw - 8), max(4, sh - 8), face)
    # 右眼（朝右角色，眼在头右侧偏前）
    ex, ey = world_to_head_atlas(2, -28)
    fill_rect(pixels, ex, ey, 12, 12, (17, 24, 39, 255))
    # safe 黄框
    draw_rect_outline(pixels, sx, sy, sw, sh, (250, 204, 21, 255))
    draw_text(pixels, sx + 4, sy + sh + 4, "SAFE", (250, 204, 21, 255), scale=1)
    draw_text(pixels, x + 8, y + 8, "HAIR+HEAD", (255, 255, 255, 220), scale=2)
    draw_text(pixels, x + 8, y + 28, "V5 4:3", (226, 232, 240, 200), scale=1)
    # 角色脚底参考线（世界 y=40 对应画布底附近）
    foot_y = world_to_head_atlas(0, 40)[1]
    for xx in range(x, x + w, 2):
        set_px(pixels, xx, min(y + h - 1, foot_y), (148, 163, 184, 120))
    draw_text(pixels, x + 8, min(y + h - 12, foot_y - 10), "FOOT", (148, 163, 184, 180), scale=1)
    draw_rect_outline(pixels, x, y, w, h, (255, 255, 255, 100))


def draw_legend(pixels: bytearray) -> None:
    """右侧留白区说明。"""
    ink = (226, 232, 240, 255)
    dim = (100, 116, 139, 255)
    x = CONTENT_WIDTH + 8
    fill_rect(pixels, x, 16, ATLAS_WIDTH - x - 8, 200, (15, 23, 42, 255))
    draw_text(pixels, x + 8, 24, "UV CHECKLIST V5", ink, scale=2)
    lines = [
        "4:3 CANVAS",
        "LEFT = SLOTS",
        "RIGHT = MARGIN",
        "RA/RL = RIGHT",
        "LA/LL = LEFT",
    ]
    for i, line in enumerate(lines):
        draw_text(pixels, x + 8, 52 + i * 12, line, dim if i % 2 else ink, scale=1)


def build_atlas() -> bytearray:
    """合成完整诊断贴图。"""
    pixels = bytearray(ATLAS_WIDTH * ATLAS_HEIGHT * 4)
    # 未占用区必须保持透明；尤其头部槽会覆盖整名角色，不透明背景会遮住身体。

    draw_head_slot(pixels)
    draw_body_slot(pixels)
    for key in (
        "frontArmUpper",
        "frontArmLower",
        "backArmUpper",
        "backArmLower",
        "frontLegUpper",
        "frontLegLower",
        "backLegUpper",
        "backLegLower",
    ):
        part = PARTS[key]
        draw_limb_guides(pixels, *part["rect"], part["tag"], part["color"])

    draw_legend(pixels)
    # 四角十字，验证整图是否被裁切/缩放
    corner = (248, 250, 252, 255)
    for cx, cy in ((2, 2), (ATLAS_WIDTH - 3, 2), (2, ATLAS_HEIGHT - 3), (ATLAS_WIDTH - 3, ATLAS_HEIGHT - 3)):
        draw_cross(pixels, cx, cy, corner, arm=2)
    return pixels


def write_png(path: Path, pixels: bytearray) -> None:
    """RGBA → PNG。"""
    def chunk(tag: bytes, data: bytes) -> bytes:
        payload = tag + data
        return struct.pack(">I", len(data)) + payload + struct.pack(">I", zlib.crc32(payload) & 0xFFFFFFFF)

    stride = ATLAS_WIDTH * 4
    raw = b"".join(b"\x00" + bytes(pixels[y * stride:(y + 1) * stride]) for y in range(ATLAS_HEIGHT))
    header = struct.pack(">IIBBBBB", ATLAS_WIDTH, ATLAS_HEIGHT, 8, 6, 0, 0, 0)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def main() -> None:
    """写出 samples 与 uploads 两份。"""
    project_root = Path(__file__).resolve().parents[1]
    pixels = build_atlas()

    samples_dir = project_root / "samples"
    samples_dir.mkdir(parents=True, exist_ok=True)
    sample_png = samples_dir / "uv-checklist.png"
    write_png(sample_png, pixels)

    skin_id = "uvchecklist"
    skin_dir = project_root / "var" / "uploads" / "skins" / skin_id
    skin_dir.mkdir(parents=True, exist_ok=True)
    write_png(skin_dir / "texture.png", pixels)
    manifest = {
        "id": skin_id,
        "name": "UV功能自检皮套",
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
    print(f"sample: {sample_png}")
    print(f"skin:   {skin_dir}")
    print("import samples/uv-checklist.png in the editor, or pick UV功能自检皮套 in the lobby.")


if __name__ == "__main__":
    main()
