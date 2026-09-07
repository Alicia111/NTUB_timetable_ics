"""Material Design 3 (Material You) 配色引擎。

吃一顆種子色，吐出一整套 M3 color scheme。零第三方依賴，
只有「從桌布取色」這條路徑會 optional import Pillow。

色彩模型用 CIELAB / LCh 近似 Google 的 HCT：
tone 直接對應 L*，hue 固定，chroma 則做 gamut mapping。
視覺上非常接近官方 M3，但不用整套 CAM16。
"""

from __future__ import annotations

import json
import math
import os
import subprocess
from dataclasses import dataclass, fields
from functools import lru_cache

# M3 baseline 種子色，桌布取色失敗時的退路
DEFAULT_SEED = "#6750A4"

# 主題設定小視窗用的內建色票
BUILTIN_SEEDS = (
    ("紫", "#6750A4"),
    ("藍", "#0061A4"),
    ("青", "#006A60"),
    ("綠", "#3F6B2E"),
    ("橘", "#8B5000"),
    ("紅", "#9C4146"),
)

SETTINGS_PATH = os.path.join(
    os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"),
    "ntub_timetable_ics",
    "settings.json",
)


# ─────────────────────────── 色彩空間轉換 ───────────────────────────
# 全部是小的純函式，數值都用 0~1 的 float，只有 hex 進出時才換算 0~255。

def hex_to_rgb(value: str) -> tuple[float, float, float]:
    """'#RRGGBB' -> (r, g, b)，每個通道 0~1。"""
    text = value.lstrip("#")
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    if len(text) != 6:
        raise ValueError(f"不是合法的色碼: {value!r}")
    return tuple(int(text[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def rgb_to_hex(rgb: tuple[float, float, float]) -> str:
    """(r, g, b) 0~1 -> '#RRGGBB'，超出範圍的值會被夾住。"""
    return "#" + "".join(f"{round(max(0.0, min(1.0, c)) * 255):02X}" for c in rgb)


def srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def linear_to_srgb(c: float) -> float:
    return c * 12.92 if c <= 0.0031308 else 1.055 * (c ** (1 / 2.4)) - 0.055


# sRGB D65 矩陣
_RGB_TO_XYZ = (
    (0.4124564, 0.3575761, 0.1804375),
    (0.2126729, 0.7151522, 0.0721750),
    (0.0193339, 0.1191920, 0.9503041),
)
_XYZ_TO_RGB = (
    (3.2404542, -1.5371385, -0.4985314),
    (-0.9692660, 1.8760108, 0.0415560),
    (0.0556434, -0.2040259, 1.0572252),
)
_WHITE = (0.95047, 1.00000, 1.08883)


def rgb_to_xyz(rgb: tuple[float, float, float]) -> tuple[float, float, float]:
    lin = [srgb_to_linear(c) for c in rgb]
    return tuple(sum(m[i] * lin[i] for i in range(3)) for m in _RGB_TO_XYZ)


def xyz_to_rgb(xyz: tuple[float, float, float]) -> tuple[float, float, float]:
    """回傳的 sRGB 可能超出 0~1（代表在色域外），由呼叫端判斷。"""
    lin = [sum(m[i] * xyz[i] for i in range(3)) for m in _XYZ_TO_RGB]
    return tuple(linear_to_srgb(c) if c > 0 else linear_to_srgb(max(c, 0.0)) for c in lin)


def _f_lab(t: float) -> float:
    return t ** (1 / 3) if t > 216 / 24389 else (24389 / 27 * t + 16) / 116


def _f_lab_inv(t: float) -> float:
    return t ** 3 if t ** 3 > 216 / 24389 else (116 * t - 16) / (24389 / 27)


def xyz_to_lab(xyz: tuple[float, float, float]) -> tuple[float, float, float]:
    fx, fy, fz = (_f_lab(v / w) for v, w in zip(xyz, _WHITE))
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def lab_to_xyz(lab: tuple[float, float, float]) -> tuple[float, float, float]:
    lightness, a, b = lab
    fy = (lightness + 16) / 116
    fx = fy + a / 500
    fz = fy - b / 200
    return tuple(_f_lab_inv(f) * w for f, w in zip((fx, fy, fz), _WHITE))


def lab_to_lch(lab: tuple[float, float, float]) -> tuple[float, float, float]:
    lightness, a, b = lab
    return (lightness, math.hypot(a, b), math.degrees(math.atan2(b, a)) % 360)


def lch_to_lab(lch: tuple[float, float, float]) -> tuple[float, float, float]:
    lightness, chroma, hue = lch
    rad = math.radians(hue)
    return (lightness, chroma * math.cos(rad), chroma * math.sin(rad))


def hex_to_lch(value: str) -> tuple[float, float, float]:
    return lab_to_lch(xyz_to_lab(rgb_to_xyz(hex_to_rgb(value))))


def blend(fg: str, bg: str, alpha: float) -> str:
    """把 fg 以 alpha 透明度疊在 bg 上，M3 的 state layer 就是這樣算的。"""
    f, b = hex_to_rgb(fg), hex_to_rgb(bg)
    return rgb_to_hex(tuple(f[i] * alpha + b[i] * (1 - alpha) for i in range(3)))


def relative_luminance(value: str) -> float:
    r, g, b = (srgb_to_linear(c) for c in hex_to_rgb(value))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a: str, b: str) -> float:
    """WCAG 對比度，1.0 ~ 21.0。"""
    la, lb = relative_luminance(a), relative_luminance(b)
    lighter, darker = max(la, lb), min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


# ─────────────────────────── Tonal palette ───────────────────────────

_GAMUT_EPSILON = 1e-4

# 每個 tone 允許的 chroma 上限（分段線性內插）。
#
# 為什麼需要這條曲線：Lab 的 chroma 不是感知均勻的，在青綠色域，
# sRGB 允許 tone 90 帶到 C≈48，畫出來會是螢光色；紫藍紅則會被色域
# 自然夾到 C≈15 左右。這條 ceiling 把各色相的亮端拉齊，行為才會像
# 真正的 HCT——越靠近黑白兩端，顏色越收斂。
_TONE_CHROMA_CEILING = (
    (0, 0.0), (10, 32.0), (20, 44.0), (30, 52.0), (40, 60.0), (50, 60.0),
    (60, 56.0), (70, 46.0), (80, 36.0), (90, 20.0), (95, 10.0), (100, 0.0),
)


def _chroma_ceiling(tone: float) -> float:
    for (t0, c0), (t1, c1) in zip(_TONE_CHROMA_CEILING, _TONE_CHROMA_CEILING[1:]):
        if t0 <= tone <= t1:
            span = t1 - t0
            return c0 + (c1 - c0) * ((tone - t0) / span if span else 0.0)
    return 0.0


def _fits_in_srgb(lch: tuple[float, float, float]) -> bool:
    rgb = xyz_to_rgb(lab_to_xyz(lch_to_lab(lch)))
    return all(-_GAMUT_EPSILON <= c <= 1 + _GAMUT_EPSILON for c in rgb)


class TonalPalette:
    """固定 hue，沿著 L* 走出 tone 0~100 的色階。

    每個 tone 都會用二分搜尋把 chroma 降到剛好落在 sRGB 色域內，
    這樣色階才會平順、不會在亮端暗端爆掉。
    """

    def __init__(self, hue: float, chroma: float):
        self.hue = hue % 360
        self.chroma = max(chroma, 0.0)

    @lru_cache(maxsize=256)
    def _solve(self, tone: float) -> str:
        target = min(self.chroma, _chroma_ceiling(tone))
        if not _fits_in_srgb((tone, target, self.hue)):
            low, high = 0.0, target
            for _ in range(24):  # 24 次就能收斂到肉眼看不出的精度
                mid = (low + high) / 2
                if _fits_in_srgb((tone, mid, self.hue)):
                    low = mid
                else:
                    high = mid
            usable = low
        else:
            usable = target
        rgb = xyz_to_rgb(lab_to_xyz(lch_to_lab((tone, usable, self.hue))))
        return rgb_to_hex(rgb)

    def tone(self, tone: float) -> str:
        return self._solve(max(0.0, min(100.0, float(tone))))

    def __hash__(self) -> int:
        return hash((round(self.hue, 4), round(self.chroma, 4)))

    def __eq__(self, other: object) -> bool:
        return isinstance(other, TonalPalette) and hash(self) == hash(other)


def key_palettes(seed_hex: str) -> dict[str, TonalPalette]:
    """照 M3 規範，從種子色展開五組 key palette（外加 error）。"""
    _, chroma, hue = hex_to_lch(seed_hex)
    return {
        "primary": TonalPalette(hue, max(chroma, 48.0)),
        "secondary": TonalPalette(hue, 16.0),
        "tertiary": TonalPalette(hue + 60.0, 24.0),
        "neutral": TonalPalette(hue, 4.0),
        "neutral_variant": TonalPalette(hue, 8.0),
        "error": TonalPalette(25.0, 84.0),
    }


# ─────────────────────────── Color scheme ───────────────────────────

@dataclass(frozen=True)
class Scheme:
    """一整套 M3 color role，欄位名就是規範上的 role 名稱。"""

    primary: str
    on_primary: str
    primary_container: str
    on_primary_container: str
    secondary: str
    on_secondary: str
    secondary_container: str
    on_secondary_container: str
    tertiary: str
    on_tertiary: str
    tertiary_container: str
    on_tertiary_container: str
    error: str
    on_error: str
    error_container: str
    on_error_container: str
    surface: str
    on_surface: str
    surface_variant: str
    on_surface_variant: str
    surface_container_low: str
    surface_container: str
    surface_container_high: str
    surface_container_highest: str
    outline: str
    outline_variant: str
    inverse_surface: str
    inverse_on_surface: str
    is_dark: bool
    seed: str


# role -> (palette 名稱, tone)。兩張對照表取代散落各處的 if/else。
_LIGHT_TONES = {
    "primary": ("primary", 40), "on_primary": ("primary", 100),
    "primary_container": ("primary", 90), "on_primary_container": ("primary", 10),
    "secondary": ("secondary", 40), "on_secondary": ("secondary", 100),
    "secondary_container": ("secondary", 90), "on_secondary_container": ("secondary", 10),
    "tertiary": ("tertiary", 40), "on_tertiary": ("tertiary", 100),
    "tertiary_container": ("tertiary", 90), "on_tertiary_container": ("tertiary", 10),
    "error": ("error", 40), "on_error": ("error", 100),
    "error_container": ("error", 90), "on_error_container": ("error", 10),
    "surface": ("neutral", 98), "on_surface": ("neutral", 10),
    "surface_variant": ("neutral_variant", 90), "on_surface_variant": ("neutral_variant", 30),
    "surface_container_low": ("neutral", 96), "surface_container": ("neutral", 94),
    "surface_container_high": ("neutral", 92), "surface_container_highest": ("neutral", 90),
    "outline": ("neutral_variant", 50), "outline_variant": ("neutral_variant", 80),
    "inverse_surface": ("neutral", 20), "inverse_on_surface": ("neutral", 95),
}

_DARK_TONES = {
    "primary": ("primary", 80), "on_primary": ("primary", 20),
    "primary_container": ("primary", 30), "on_primary_container": ("primary", 90),
    "secondary": ("secondary", 80), "on_secondary": ("secondary", 20),
    "secondary_container": ("secondary", 30), "on_secondary_container": ("secondary", 90),
    "tertiary": ("tertiary", 80), "on_tertiary": ("tertiary", 20),
    "tertiary_container": ("tertiary", 30), "on_tertiary_container": ("tertiary", 90),
    "error": ("error", 80), "on_error": ("error", 20),
    "error_container": ("error", 30), "on_error_container": ("error", 90),
    "surface": ("neutral", 6), "on_surface": ("neutral", 90),
    "surface_variant": ("neutral_variant", 30), "on_surface_variant": ("neutral_variant", 80),
    "surface_container_low": ("neutral", 10), "surface_container": ("neutral", 12),
    "surface_container_high": ("neutral", 17), "surface_container_highest": ("neutral", 22),
    "outline": ("neutral_variant", 60), "outline_variant": ("neutral_variant", 30),
    "inverse_surface": ("neutral", 90), "inverse_on_surface": ("neutral", 20),
}


def build_scheme(seed_hex: str, dark: bool = False) -> Scheme:
    """種子色 + 深淺色 -> 完整 scheme。色碼不合法就退回 DEFAULT_SEED。"""
    try:
        hex_to_rgb(seed_hex)
    except (ValueError, AttributeError):
        seed_hex = DEFAULT_SEED

    palettes = key_palettes(seed_hex)
    tones = _DARK_TONES if dark else _LIGHT_TONES
    colors = {role: palettes[name].tone(tone) for role, (name, tone) in tones.items()}
    return Scheme(is_dark=dark, seed=seed_hex.upper(), **colors)


def course_container_roles(scheme: Scheme) -> tuple[tuple[str, str], ...]:
    """課程卡片輪替用的 (底色, 文字色)，取三組 container 讓課表有層次。"""
    return (
        (scheme.primary_container, scheme.on_primary_container),
        (scheme.secondary_container, scheme.on_secondary_container),
        (scheme.tertiary_container, scheme.on_tertiary_container),
    )


# ─────────────────────────── 桌布取色（Monet 本體） ───────────────────────────
# 這整段的原則：抓不到就安靜退回預設色，絕不能讓主程式起不來。

def _run(args: list[str]) -> str | None:
    try:
        out = subprocess.run(args, capture_output=True, text=True, timeout=1.0)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def _clean_path(raw: str | None) -> str | None:
    """把 gsettings / config 檔裡的 'file://...'、引號、跳脫字元清乾淨。"""
    if not raw:
        return None
    path = raw.strip().strip("'\"")
    if path.startswith("file://"):
        from urllib.parse import unquote, urlparse
        path = unquote(urlparse(path).path)
    path = os.path.expanduser(path)
    return path if os.path.isfile(path) else None


def _from_config_key(rel_path: str, key: str) -> str | None:
    """從 ini 風格設定檔裡撈 `key=value`（取最後一筆非空值）。"""
    full = os.path.expanduser(rel_path)
    if not os.path.isfile(full):
        return None
    found = None
    try:
        with open(full, "r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                stripped = line.strip()
                if stripped.lower().startswith(key.lower() + "="):
                    value = stripped.split("=", 1)[1].strip()
                    if value:
                        found = value
    except OSError:
        return None
    return found


def detect_wallpaper_path() -> str | None:
    """依序試各家桌面環境，回傳桌布檔案路徑。"""
    candidates = (
        lambda: _run(["gsettings", "get", "org.gnome.desktop.background", "picture-uri"]),
        lambda: _run(["gsettings", "get", "org.gnome.desktop.background", "picture-uri-dark"]),
        lambda: _from_config_key("~/.config/pcmanfm/LXDE-pi/desktop-items-0.conf", "wallpaper"),
        lambda: _from_config_key("~/.config/wayfire.ini", "image"),
        lambda: _run(["xfconf-query", "-c", "xfce4-desktop",
                      "-p", "/backdrop/screen0/monitor0/workspace0/last-image"]),
        lambda: _from_config_key("~/.config/plasma-org.kde.plasma.desktop-appletsrc", "Image"),
    )
    for probe in candidates:
        try:
            path = _clean_path(probe())
        except Exception:
            path = None
        if path:
            return path
    return None


def seed_from_image(path: str) -> str | None:
    """從圖片挑一顆有活力的主色。沒有 Pillow 或讀不到圖就回 None。"""
    try:
        from PIL import Image
    except ImportError:
        return None

    try:
        with Image.open(path) as image:
            small = image.convert("RGB").resize((64, 64), Image.Resampling.BILINEAR)
            quantized = small.quantize(colors=16)
            palette = quantized.getpalette() or []
            counts = quantized.getcolors() or []
    except Exception:
        return None

    best_score, best_hex = 0.0, None
    for count, index in counts:
        rgb = tuple(c / 255.0 for c in palette[index * 3:index * 3 + 3])
        if len(rgb) != 3:
            continue
        lightness, chroma, _ = lab_to_lch(xyz_to_lab(rgb_to_xyz(rgb)))
        # 太灰、太黑、太白的都不適合當種子色
        if chroma < 8 or not 12 <= lightness <= 92:
            continue
        score = count * chroma
        if score > best_score:
            best_score, best_hex = score, rgb_to_hex(rgb)
    return best_hex


# ─────────────────────────── 設定持久化 ───────────────────────────

def default_settings() -> dict:
    return {"seed": DEFAULT_SEED, "seed_source": "wallpaper", "dark": False, "cache": {}}


def load_settings() -> dict:
    settings = default_settings()
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as handle:
            stored = json.load(handle)
        if isinstance(stored, dict):
            settings.update({k: v for k, v in stored.items() if k in settings})
    except (OSError, ValueError):
        pass  # 沒設定檔或內容壞掉，用預設值就好
    return settings


def save_settings(settings: dict) -> None:
    try:
        os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
        with open(SETTINGS_PATH, "w", encoding="utf-8") as handle:
            json.dump(settings, handle, ensure_ascii=False, indent=2)
    except OSError:
        pass  # 存不起來頂多下次要重挑顏色，不值得打斷使用者


def seed_from_wallpaper(settings: dict) -> tuple[str | None, str]:
    """抓桌布主色，並用「路徑 + mtime」做快取，避免每次開啟都重算。

    回傳 (色碼 或 None, 給人看的來源說明)。
    """
    path = detect_wallpaper_path()
    if not path:
        return None, "找不到桌布"

    try:
        mtime = os.path.getmtime(path)
    except OSError:
        mtime = 0.0

    cache = settings.get("cache") or {}
    if cache.get("path") == path and cache.get("mtime") == mtime and cache.get("seed"):
        return cache["seed"], f"桌布（快取）: {os.path.basename(path)}"

    seed = seed_from_image(path)
    if not seed:
        return None, "桌布取色失敗"

    settings["cache"] = {"path": path, "mtime": mtime, "seed": seed}
    return seed, f"桌布: {os.path.basename(path)}"


def resolve_seed(settings: dict) -> tuple[str, str]:
    """依設定決定這次要用的種子色，回傳 (色碼, 來源說明)。"""
    if settings.get("seed_source") == "wallpaper":
        seed, source = seed_from_wallpaper(settings)
        if seed:
            settings["seed"] = seed
            return seed, source
        return settings.get("seed") or DEFAULT_SEED, source + "，改用上次的顏色"
    return settings.get("seed") or DEFAULT_SEED, "自訂顏色"


# ─────────────────────────── 自我檢查 ───────────────────────────

def _selftest() -> int:
    """印出色階與對比度表；on_X / X 有任何一組低於 4.5:1 就回傳非 0。"""
    seed = DEFAULT_SEED
    print(f"種子色: {seed}  LCh={tuple(round(v, 1) for v in hex_to_lch(seed))}\n")

    for name, palette in key_palettes(seed).items():
        ramp = " ".join(palette.tone(t) for t in (0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 99, 100))
        print(f"{name:>16}  {ramp}")

    failures = 0
    for dark in (False, True):
        scheme = build_scheme(seed, dark)
        print(f"\n── {'dark' if dark else 'light'} scheme 對比度 ──")
        pairs = [(f.name, f.name[3:]) for f in fields(scheme)
                 if f.name.startswith("on_") and f.name[3:] in {g.name for g in fields(scheme)}]
        pairs.append(("on_surface_variant", "surface_variant"))
        for on_role, role in sorted(set(pairs)):
            ratio = contrast_ratio(getattr(scheme, on_role), getattr(scheme, role))
            mark = "ok " if ratio >= 4.5 else "低 "
            if ratio < 4.5:
                failures += 1
            print(f"  {mark}{on_role:>26} / {role:<24} {ratio:5.2f}:1")

    path = detect_wallpaper_path()
    print(f"\n桌布偵測: {path or '（沒抓到，會退回預設色）'}")
    print("自我檢查結果:", "全部通過" if failures == 0 else f"{failures} 組對比度不足")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(_selftest())
