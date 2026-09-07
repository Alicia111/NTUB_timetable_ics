"""把 Material Design 3 的 color scheme 套到 tkinter / ttk 上。

顏色跟 widget 的耦合全部關在這裡，gui.py 只呼叫高階函式。
tkinter 沒有 M3 的圓角與 elevation，所以：
  - 按鈕、輸入框用 ttk 'clam' theme 改造成扁平填色
  - state layer（hover / pressed / disabled）用 blend() 疊色模擬
  - 需要圓角的地方（課程卡片）在 Canvas 上自己畫
"""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

from theme import Scheme, blend

# M3 state layer 的不透明度
_HOVER_ALPHA = 0.08
_PRESSED_ALPHA = 0.12
_DISABLED_BG_ALPHA = 0.12
_DISABLED_FG_ALPHA = 0.38

# 字型優先序：專案自帶的 Iansui 最優先，再退回各平台的常見中文字型
_FONT_CANDIDATES = (
    "Iansui", "Noto Sans CJK TC", "Noto Sans TC", "Source Han Sans TC",
    "Microsoft JhengHei", "PingFang TC", "DejaVu Sans",
)

# M3 type scale（只取這支程式用得到的幾級）
_TYPE_SCALE = {
    "title_large": (20, "bold"),
    "title_medium": (16, "bold"),
    "body_large": (14, "normal"),
    "label_large": (12, "bold"),
    "body_medium": (12, "normal"),
    "body_small": (11, "normal"),
}

_font_family = "TkDefaultFont"


def resolve_font_family(root: tk.Misc) -> str:
    """挑一個實際裝得到的字型。

    取代舊寫法 `option_add("*Font", name)` + `font create` —— 那個順序反了，
    而且字型不存在時 Tk 會安靜地用預設值，看不出來哪裡怪。
    """
    global _font_family
    try:
        available = {name.lower() for name in tkfont.families(root)}
    except tk.TclError:
        available = set()
    for candidate in _FONT_CANDIDATES:
        if candidate.lower() in available:
            _font_family = candidate
            break
    else:
        _font_family = "TkDefaultFont"
    return _font_family


def type_scale(name: str) -> tuple[str, int, str]:
    """回傳可直接丟給 font= 的 tuple。"""
    size, weight = _TYPE_SCALE.get(name, _TYPE_SCALE["body_medium"])
    return (_font_family, size, weight)


def _state_colors(base: str, on_base: str, scheme: Scheme) -> dict:
    """一組填色元件在各 state 下的顏色。"""
    return {
        "hover": blend(on_base, base, _HOVER_ALPHA),
        "pressed": blend(on_base, base, _PRESSED_ALPHA),
        "disabled_bg": blend(scheme.on_surface, scheme.surface, _DISABLED_BG_ALPHA),
        "disabled_fg": blend(scheme.on_surface, scheme.surface, _DISABLED_FG_ALPHA),
    }


def _configure_filled_button(style: ttk.Style, name: str, base: str, on_base: str,
                             scheme: Scheme) -> None:
    """設定一顆扁平填色按鈕（M3 filled / tonal button）。

    clam 的按鈕邊框是 bordercolor / lightcolor / darkcolor 三層畫出來的，
    三個都跟著背景走才會真的看起來是扁的。
    """
    state = _state_colors(base, on_base, scheme)
    style.configure(
        name,
        background=base, foreground=on_base,
        bordercolor=base, lightcolor=base, darkcolor=base,
        focuscolor=on_base, relief="flat", borderwidth=0,
        padding=(20, 10), font=type_scale("label_large"), anchor="center",
    )
    style.map(
        name,
        background=[("disabled", state["disabled_bg"]), ("pressed", state["pressed"]),
                    ("active", state["hover"])],
        foreground=[("disabled", state["disabled_fg"])],
        bordercolor=[("disabled", state["disabled_bg"]), ("pressed", state["pressed"]),
                     ("active", state["hover"])],
        lightcolor=[("disabled", state["disabled_bg"]), ("pressed", state["pressed"]),
                    ("active", state["hover"])],
        darkcolor=[("disabled", state["disabled_bg"]), ("pressed", state["pressed"]),
                   ("active", state["hover"])],
        relief=[("pressed", "flat"), ("active", "flat")],
    )


def _configure_segmented(style: ttk.Style, scheme: Scheme) -> None:
    """M3 segmented button：兩顆 Radiobutton，選中的那顆填 secondary container。

    作法是把 Radiobutton 的圓點 indicator 從 layout 拿掉、換成 Button.border，
    這樣背景色才吃得到。萬一某個 Tk 版本不吃這種 layout，就退回原本的圓點外觀。
    """
    name = "M3Segment.TRadiobutton"
    try:
        style.layout(name, [
            ("Button.border", {"sticky": "nswe", "border": "1", "children": [
                ("Radiobutton.padding", {"sticky": "nswe", "children": [
                    ("Radiobutton.label", {"sticky": "nswe"}),
                ]}),
            ]}),
        ])
    except tk.TclError:
        pass  # 這個 Tk 版本不吃自訂 layout，就留著預設的圓點外觀，顏色照樣套

    unselected_bg = scheme.surface_container_low
    style.configure(
        name,
        background=unselected_bg, foreground=scheme.on_surface_variant,
        bordercolor=scheme.outline, lightcolor=unselected_bg, darkcolor=unselected_bg,
        indicatorbackground=unselected_bg, indicatorforeground=scheme.on_secondary_container,
        focuscolor=scheme.on_surface, relief="flat", borderwidth=1,
        padding=(16, 8), font=type_scale("label_large"), anchor="center",
    )
    style.map(
        name,
        background=[("selected", scheme.secondary_container),
                    ("active", blend(scheme.on_surface, unselected_bg, _HOVER_ALPHA))],
        foreground=[("selected", scheme.on_secondary_container),
                    ("disabled", blend(scheme.on_surface, scheme.surface, _DISABLED_FG_ALPHA))],
        lightcolor=[("selected", scheme.secondary_container)],
        darkcolor=[("selected", scheme.secondary_container)],
        indicatorbackground=[("selected", scheme.secondary_container)],
    )


def apply_theme(root: tk.Misc, scheme: Scheme) -> ttk.Style:
    """把整套 scheme 套上去。切換深淺色 / 換種子色時重複呼叫即可。"""
    style = ttk.Style(root)
    try:
        style.theme_use("clam")  # 內建 theme 裡最好改造的一個
    except tk.TclError:
        pass

    resolve_font_family(root)
    root.option_add("*Font", type_scale("body_medium"))
    try:
        root.configure(background=scheme.surface)
    except tk.TclError:
        pass

    # ── 容器 ──
    style.configure("M3.TFrame", background=scheme.surface)
    style.configure("M3Card.TFrame", background=scheme.surface_container_low)
    style.configure("M3Bar.TFrame", background=scheme.surface_container)

    # ── 文字 ──
    for name, bg in (("M3.TLabel", scheme.surface),
                     ("M3Card.TLabel", scheme.surface_container_low),
                     ("M3Bar.TLabel", scheme.surface_container)):
        style.configure(name, background=bg, foreground=scheme.on_surface,
                        font=type_scale("body_large"))
    style.configure("M3Title.TLabel", background=scheme.surface_container,
                    foreground=scheme.on_surface, font=type_scale("title_large"))
    style.configure("M3Error.TLabel", background=scheme.surface_container_low,
                    foreground=scheme.error, font=type_scale("body_small"))
    style.configure("M3Hint.TLabel", background=scheme.surface_container_low,
                    foreground=scheme.on_surface_variant, font=type_scale("body_small"))

    # ── 按鈕 ──
    _configure_filled_button(style, "M3Filled.TButton", scheme.primary, scheme.on_primary, scheme)
    _configure_filled_button(style, "M3Tonal.TButton",
                             scheme.secondary_container, scheme.on_secondary_container, scheme)
    # icon 按鈕：圓形填色做不出來，改用 surface container 上的小方塊
    _configure_filled_button(style, "M3Icon.TButton",
                             scheme.surface_container, scheme.on_surface_variant, scheme)
    style.configure("M3Icon.TButton", padding=(10, 6), font=type_scale("title_medium"))

    # ── 輸入框（M3 outlined text field 的近似） ──
    style.configure(
        "M3.TEntry",
        fieldbackground=scheme.surface_container_highest,
        background=scheme.surface_container_highest,
        foreground=scheme.on_surface, insertcolor=scheme.primary,
        bordercolor=scheme.outline, lightcolor=scheme.outline, darkcolor=scheme.outline,
        borderwidth=1, relief="flat", padding=(10, 8),
    )
    style.map(
        "M3.TEntry",
        bordercolor=[("focus", scheme.primary), ("disabled", scheme.outline_variant)],
        lightcolor=[("focus", scheme.primary)],
        darkcolor=[("focus", scheme.primary)],
        foreground=[("disabled", blend(scheme.on_surface, scheme.surface, _DISABLED_FG_ALPHA))],
    )

    # ── 選擇類 ──
    _configure_segmented(style, scheme)
    style.configure(
        "M3.TCheckbutton",
        background=scheme.surface_container_low, foreground=scheme.on_surface,
        indicatorbackground=scheme.surface_container_low,
        indicatorforeground=scheme.on_primary,
        focuscolor=scheme.on_surface, font=type_scale("body_medium"), padding=(4, 4),
    )
    style.map(
        "M3.TCheckbutton",
        indicatorbackground=[("selected", scheme.primary),
                             ("disabled", blend(scheme.on_surface, scheme.surface,
                                                _DISABLED_BG_ALPHA))],
        background=[("active", blend(scheme.on_surface, scheme.surface_container_low,
                                     _HOVER_ALPHA))],
        foreground=[("disabled", blend(scheme.on_surface, scheme.surface, _DISABLED_FG_ALPHA))],
    )

    # ── 捲軸 ──
    style.configure(
        "M3.Vertical.TScrollbar",
        background=scheme.outline_variant, troughcolor=scheme.surface,
        bordercolor=scheme.surface, arrowcolor=scheme.on_surface_variant,
        relief="flat", borderwidth=0,
    )
    style.map("M3.Vertical.TScrollbar", background=[("active", scheme.outline)])
    style.configure(
        "M3.Horizontal.TScrollbar",
        background=scheme.outline_variant, troughcolor=scheme.surface,
        bordercolor=scheme.surface, arrowcolor=scheme.on_surface_variant,
        relief="flat", borderwidth=0,
    )
    style.map("M3.Horizontal.TScrollbar", background=[("active", scheme.outline)])

    return style


def style_date_entry(entry, scheme: Scheme) -> None:
    """tkcalendar 的 DateEntry 不吃 ttk style，顏色只能一個一個餵。"""
    options = {
        "background": scheme.primary,
        "foreground": scheme.on_primary,
        "headersbackground": scheme.primary_container,
        "headersforeground": scheme.on_primary_container,
        "selectbackground": scheme.primary,
        "selectforeground": scheme.on_primary,
        "normalbackground": scheme.surface_container_low,
        "normalforeground": scheme.on_surface,
        "weekendbackground": scheme.surface_container_low,
        "weekendforeground": scheme.on_surface_variant,
        "othermonthforeground": scheme.outline,
        "othermonthbackground": scheme.surface,
        "othermonthweforeground": scheme.outline,
        "othermonthwebackground": scheme.surface,
        "bordercolor": scheme.outline,
        "fieldbackground": scheme.surface_container_highest,
        "font": type_scale("body_medium"),
    }
    for key, value in options.items():
        try:
            entry.configure(**{key: value})
        except tk.TclError:
            continue  # 不同 tkcalendar 版本支援的選項不完全一樣，跳過就好


def rounded_rect(canvas: tk.Canvas, x1: float, y1: float, x2: float, y2: float,
                 radius: float = 12, **kwargs) -> int:
    """在 Canvas 上畫圓角矩形。

    Canvas 沒有原生圓角，用平滑多邊形模擬：在每個角落放兩個貼齊的控制點，
    smooth=True 會把它們拉成圓弧。
    """
    radius = max(0.0, min(radius, (x2 - x1) / 2, (y2 - y1) / 2))
    points = [
        x1 + radius, y1, x2 - radius, y1, x2, y1,
        x2, y1 + radius, x2, y2 - radius, x2, y2,
        x2 - radius, y2, x1 + radius, y2, x1, y2,
        x1, y2 - radius, x1, y1 + radius, x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)
