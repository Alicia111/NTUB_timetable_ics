"""NTUB 課表 / 行事曆 ICS 產生器。

介面走 Material Design 3，配色由 theme.py 從桌布擷取的種子色即時生成（Monet），
套用的細節都在 md3.py，這支檔案只管版面與流程。
"""

import datetime
import os
import tkinter as tk
import zlib
from tkinter import colorchooser, filedialog, ttk

from tkcalendar import DateEntry

import md3
import theme
from table import get_mix_class_table, get_single_class_table

WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")
DEFAULT_WEEKS = 18          # 一學期大約的長度，當作結束日期的預設值
CHIP_PADDING = 4            # 課程卡片與格線之間留的空隙
CHIP_RADIUS = 12


class TimetableCanvas:
    """畫課表的 Canvas。

    課程用圓角卡片呈現（M3 沒有「表格」這種元件，最接近的是一堆 container），
    底色在三組 container role 之間輪替，讓相鄰課程分得開。
    """

    def __init__(self, master, scheme, width=960, height=520):
        self.scheme = scheme
        self.width = width
        self.height = height

        self.frame = ttk.Frame(master, style="M3.TFrame")
        self.frame.pack(padx=16, pady=(0, 8), fill="both", expand=True)

        self.v_scrollbar = ttk.Scrollbar(self.frame, orient="vertical",
                                         style="M3.Vertical.TScrollbar")
        self.v_scrollbar.pack(side="right", fill="y")
        self.h_scrollbar = ttk.Scrollbar(self.frame, orient="horizontal",
                                         style="M3.Horizontal.TScrollbar")
        self.h_scrollbar.pack(side="bottom", fill="x")

        self.canvas = tk.Canvas(
            self.frame, width=width, height=height,
            bg=scheme.surface, highlightthickness=0, bd=0,
            yscrollcommand=self.v_scrollbar.set,
            xscrollcommand=self.h_scrollbar.set,
        )
        self.canvas.pack(fill="both", expand=True)
        self.v_scrollbar.config(command=self.canvas.yview)
        self.h_scrollbar.config(command=self.canvas.xview)

        # 記住最後畫過什麼，換主題時才能原樣重畫
        self._last_render = None
        self._set_adaptive_sizes()

    # ── 尺寸 ──────────────────────────────────────────────
    def _set_adaptive_sizes(self):
        """依畫布大小推算欄寬列高。"""
        self.left_margin = int(self.width * 0.12)
        self.top_margin = int(self.height * 0.09)
        self.cell_width = int((self.width - self.left_margin) / len(WEEKDAYS))
        self.cell_height = int((self.height - self.top_margin) / 8)
        self.days = []
        self.time_slots = []

    # ── 主題 ──────────────────────────────────────────────
    def retheme(self, scheme):
        """換色後照原本的內容重畫一次。"""
        self.scheme = scheme
        self.canvas.config(bg=scheme.surface)
        if self._last_render is None:
            return
        mode, payload = self._last_render
        if mode == "single":
            self.display_single_timetable(payload)
        elif mode == "mix":
            self.display_mix_timetable(payload)
        else:
            self.display_error(payload)

    def _chip_colors(self, course_name):
        """同一門課永遠拿到同一個顏色；用 crc32 而不是 hash()，
        因為 str 的 hash 每次執行都會變，課表顏色會跳來跳去。"""
        roles = theme.course_container_roles(self.scheme)
        return roles[zlib.crc32(course_name.encode("utf-8")) % len(roles)]

    # ── 繪製基本結構 ───────────────────────────────────────
    def clear_canvas(self):
        self.canvas.delete("all")

    def _total_size(self):
        return (self.left_margin + (len(self.days) - 1) * self.cell_width,
                self.top_margin + len(self.time_slots) * self.cell_height)

    def _draw_frame(self):
        """畫表頭與格線。"""
        total_width, total_height = self._total_size()
        self.canvas.config(scrollregion=(0, 0, total_width, total_height))

        # 表頭列
        self.canvas.create_rectangle(
            0, 0, total_width, self.top_margin,
            fill=self.scheme.surface_container_high, outline="",
        )
        header_font = (md3.type_scale("label_large")[0],
                       max(11, min(14, int(self.top_margin / 3))), "bold")
        self.canvas.create_text(
            self.left_margin / 2, self.top_margin / 2,
            text=self.days[0], font=header_font, fill=self.scheme.on_surface,
        )
        for index, day in enumerate(self.days[1:], 1):
            x = self.left_margin + (index - 1) * self.cell_width + self.cell_width / 2
            self.canvas.create_text(x, self.top_margin / 2, text=day,
                                    font=header_font, fill=self.scheme.on_surface)

        # 格線：M3 的分隔線很輕，用 outline_variant 就好，不要黑線
        for index in range(len(self.days)):
            x = self.left_margin + index * self.cell_width
            self.canvas.create_line(x, self.top_margin, x, total_height,
                                    fill=self.scheme.outline_variant, width=1)
        for index in range(len(self.time_slots) + 1):
            y = self.top_margin + index * self.cell_height
            self.canvas.create_line(0, y, total_width, y,
                                    fill=self.scheme.outline_variant, width=1)

    def _draw_time_column(self):
        time_font = (md3.type_scale("body_small")[0],
                     max(9, min(11, int(self.left_margin / 10))))
        for index, time_slot in enumerate(self.time_slots):
            y = self.top_margin + index * self.cell_height + self.cell_height / 2
            self.canvas.create_text(
                self.left_margin / 2, y, text=time_slot, font=time_font,
                fill=self.scheme.on_surface_variant, width=self.left_margin - 12,
            )

    def _draw_course_chip(self, start_row, end_row, col, content):
        """畫一張課程卡片；單一時段與合併時段共用同一段邏輯。"""
        x1 = self.left_margin + (col - 1) * self.cell_width + CHIP_PADDING
        y1 = self.top_margin + start_row * self.cell_height + CHIP_PADDING
        x2 = x1 + self.cell_width - CHIP_PADDING * 2
        y2 = self.top_margin + (end_row + 1) * self.cell_height - CHIP_PADDING

        background, foreground = self._chip_colors(content)
        md3.rounded_rect(self.canvas, x1, y1, x2, y2, CHIP_RADIUS,
                         fill=background, outline="")
        self.canvas.create_text(
            (x1 + x2) / 2, (y1 + y2) / 2, text=content,
            font=self._chip_font(content), fill=foreground,
            width=x2 - x1 - 8,
        )

    @staticmethod
    def _chip_font(content):
        """文字多就縮字級，免得卡片塞不下。"""
        family = md3.type_scale("body_medium")[0]
        lines = content.count("\n") + 1
        if len(content) > 30 or lines > 2:
            return (family, 9)
        if len(content) > 15 or lines > 1:
            return (family, 10)
        return (family, 11)

    # ── 資料整理 ───────────────────────────────────────────
    @staticmethod
    def _collect_days_and_times(result):
        """找出「這禮拜哪幾天有課、有哪些時段」，空的日子直接不畫。"""
        days = ["Time"]
        for day in WEEKDAYS:
            if any(slot.get(day.lower()) for slot in result):
                days.append(day)

        times = {slot.get("time", "") for slot in result
                 if any(slot.get(day.lower(), "") for day in days[1:])}
        return days, sorted(times, key=TimetableCanvas.time_to_minutes)

    def _prepare(self, result):
        self.clear_canvas()
        self.days, self.time_slots = self._collect_days_and_times(result)
        self._draw_frame()
        self._draw_time_column()

    # ── 兩種課表 ───────────────────────────────────────────
    def display_single_timetable(self, result):
        """一般課表：每個時段各自一張卡片。"""
        self._last_render = ("single", result)
        self._prepare(result)

        for time_slot in result:
            time_text = time_slot.get("time", "")
            if time_text not in self.time_slots:
                continue
            row = self.time_slots.index(time_text)
            for col, day in enumerate(self.days[1:], 1):
                content = time_slot.get(day.lower(), "")
                if content:
                    self._draw_course_chip(row, row, col, content)

    def display_mix_timetable(self, result):
        """行事曆用課表：連續同一門課的時段合併成一張長卡片。"""
        self._last_render = ("mix", result)
        self._prepare(result)

        for col, day in enumerate(self.days[1:], 1):
            for start_row, end_row, course in self._runs_for_day(result, day.lower()):
                self._draw_course_chip(start_row, end_row, col, course)

    def _runs_for_day(self, result, day_key):
        """把某一天的課切成 (起始列, 結束列, 課名) 這種連續區段。"""
        by_row = {}
        for time_slot in result:
            course = time_slot.get(day_key, "")
            time_text = time_slot.get("time", "")
            if course and time_text in self.time_slots:
                by_row[self.time_slots.index(time_text)] = course

        runs = []
        start_row = None
        current = None
        for row in range(len(self.time_slots)):
            course = by_row.get(row)
            if course == current:
                continue
            if current is not None:
                runs.append((start_row, row - 1, current))
            start_row, current = (row, course) if course else (None, None)
        if current is not None:
            runs.append((start_row, len(self.time_slots) - 1, current))
        return runs

    def display_error(self, message):
        self._last_render = ("error", message)
        self.clear_canvas()
        self.canvas.config(scrollregion=(0, 0, self.width, self.height))
        self.canvas.create_text(
            self.width / 2, self.height / 2, text=message,
            font=md3.type_scale("title_medium"), fill=self.scheme.error,
        )

    @staticmethod
    def time_to_minutes(time_str):
        """把 '08:10-09:00' 轉成分鐘數，純粹給排序用。"""
        if not time_str or "-" not in time_str:
            return 0
        start = time_str.split("-")[0].strip()
        try:
            hours, minutes = map(int, start.split(":"))
        except ValueError:
            return 0
        return hours * 60 + minutes


# ═══════════════════════════ 主視窗 ═══════════════════════════

settings = theme.load_settings()
seed, seed_source = theme.resolve_seed(settings)
scheme = theme.build_scheme(seed, settings.get("dark", False))

window = tk.Tk()
window.title("NTUB Timetable ICS Generator by Nekolia")
window.geometry("1000x760")
md3.apply_theme(window, scheme)

# ── Top app bar ──
app_bar = ttk.Frame(window, style="M3Bar.TFrame")
app_bar.pack(fill="x")

title_label = ttk.Label(app_bar, text="NTUB 課表 ICS 產生器", style="M3Title.TLabel")
title_label.pack(side="left", padx=20, pady=14)

theme_button = ttk.Button(app_bar, text="◐", width=3, style="M3Icon.TButton")
theme_button.pack(side="right", padx=(4, 16), pady=10)

dark_button = ttk.Button(app_bar, text="☀" if scheme.is_dark else "☾",
                         width=3, style="M3Icon.TButton")
dark_button.pack(side="right", padx=4, pady=10)

# ── 控制卡片 ──
card = ttk.Frame(window, style="M3Card.TFrame", padding=16)
card.pack(fill="x", padx=16, pady=16)

main_row = ttk.Frame(card, style="M3Card.TFrame")
main_row.pack(fill="x")

# 學號
id_frame = ttk.Frame(main_row, style="M3Card.TFrame")
id_frame.pack(side="left")
ttk.Label(id_frame, text="學號", style="M3Card.TLabel").pack(side="left", padx=(0, 8))
student_id_entry = ttk.Entry(id_frame, width=12, style="M3.TEntry",
                             font=md3.type_scale("body_large"))
student_id_entry.pack(side="left")
student_id_entry.config(
    validate="key",
    validatecommand=(window.register(lambda value: value.isdigit() or value == ""), "%P"),
)
student_id_error_label = ttk.Label(id_frame, text="", style="M3Error.TLabel")
student_id_error_label.pack(side="left", padx=12)

# 課表類型（segmented button）
type_frame = ttk.Frame(main_row, style="M3Card.TFrame")
type_frame.pack(side="left", padx=24)
class_type = tk.StringVar(value="單一課表")


def on_class_type_change():
    """只有行事曆用課表需要設定重複到哪天。"""
    if class_type.get() == "混合課表":
        date_row.pack(fill="x", pady=(12, 0))
    else:
        date_row.pack_forget()


for label, value in (("課表", "單一課表"), ("行事曆用課表", "混合課表")):
    ttk.Radiobutton(type_frame, text=label, variable=class_type, value=value,
                    style="M3Segment.TRadiobutton",
                    command=on_class_type_change).pack(side="left")

# 按鈕
button_frame = ttk.Frame(main_row, style="M3Card.TFrame")
button_frame.pack(side="right")
generate_button = ttk.Button(button_frame, text="產生課表", style="M3Filled.TButton")
generate_button.pack(side="left", padx=4)
ics_button = ttk.Button(button_frame, text="匯出 ICS", style="M3Tonal.TButton",
                        state="disabled")
ics_button.pack(side="left", padx=4)

# ── 重複區間（預設隱藏） ──
date_row = ttk.Frame(card, style="M3Card.TFrame")

ttk.Label(date_row, text="重複至", style="M3Card.TLabel").pack(side="left", padx=(0, 8))

default_end_date = datetime.date.today() + datetime.timedelta(weeks=DEFAULT_WEEKS)
end_date_entry = DateEntry(
    date_row, width=12,
    year=default_end_date.year, month=default_end_date.month, day=default_end_date.day,
    date_pattern="yyyy/mm/dd", locale="zh_TW",
)
end_date_entry.pack(side="left")
md3.style_date_entry(end_date_entry, scheme)

infinite_var = tk.BooleanVar(value=False)


def toggle_date_entry():
    end_date_entry.config(state="disabled" if infinite_var.get() else "normal")


ttk.Checkbutton(date_row, text="無限重複", variable=infinite_var,
                style="M3.TCheckbutton",
                command=toggle_date_entry).pack(side="left", padx=12)

# ── 課表畫布 ──
timetable_canvas = TimetableCanvas(window, scheme, width=960, height=520)

# ── Snackbar 狀態列 ──
snackbar = tk.Label(window, text="就緒", anchor="w", padx=16, pady=10,
                    bd=0, highlightthickness=0)
snackbar.pack(fill="x", side="bottom")


def show_status(message, kind="info"):
    """底部訊息條。M3 的 snackbar 用反色 surface，錯誤則用 error container。"""
    if kind == "error":
        background, foreground = scheme.error_container, scheme.on_error_container
    elif kind == "success":
        background, foreground = scheme.inverse_surface, scheme.inverse_on_surface
    else:
        background, foreground = scheme.surface_container, scheme.on_surface_variant
    snackbar.config(text=message, bg=background, fg=foreground,
                    font=md3.type_scale("body_medium"))


# ═══════════════════════════ 主題切換 ═══════════════════════════

def refresh_theme():
    """重新產生 scheme 並套到所有 widget 上。"""
    global scheme
    scheme = theme.build_scheme(settings.get("seed", theme.DEFAULT_SEED),
                                settings.get("dark", False))
    md3.apply_theme(window, scheme)
    md3.style_date_entry(end_date_entry, scheme)
    timetable_canvas.retheme(scheme)
    dark_button.config(text="☀" if scheme.is_dark else "☾")
    show_status(snackbar.cget("text"))


def toggle_dark():
    settings["dark"] = not settings.get("dark", False)
    theme.save_settings(settings)
    refresh_theme()


def set_seed(new_seed, source):
    settings["seed"] = new_seed
    settings["seed_source"] = source
    theme.save_settings(settings)
    refresh_theme()


def open_theme_dialog():
    """選種子色的小視窗：內建色票 / 重抓桌布 / 自訂。"""
    dialog = tk.Toplevel(window)
    dialog.title("主題顏色")
    dialog.configure(bg=scheme.surface)
    dialog.resizable(False, False)
    dialog.transient(window)

    body = ttk.Frame(dialog, style="M3Card.TFrame", padding=16)
    body.pack(fill="both", expand=True)

    ttk.Label(body, text="選一個種子色", style="M3Card.TLabel").pack(anchor="w")

    swatches = ttk.Frame(body, style="M3Card.TFrame")
    swatches.pack(pady=12)
    for name, value in theme.BUILTIN_SEEDS:
        swatch = tk.Button(
            swatches, text=name, width=3, bd=0, relief="flat", cursor="hand2",
            bg=value, fg=theme.build_scheme(value, False).on_primary,
            activebackground=value, highlightthickness=0,
            command=lambda v=value: (set_seed(v, "custom"), dialog.destroy()),
        )
        swatch.pack(side="left", padx=4, ipady=6)

    def pick_from_wallpaper():
        wallpaper_seed, source = theme.seed_from_wallpaper(settings)
        if wallpaper_seed:
            settings["seed"] = wallpaper_seed
            set_seed(wallpaper_seed, "wallpaper")
            show_status(f"已套用 {source}", "success")
        else:
            show_status(f"{source}，先維持原本的顏色", "error")
        dialog.destroy()

    def pick_custom():
        chosen = colorchooser.askcolor(color=settings.get("seed"), parent=dialog)[1]
        if chosen:
            set_seed(chosen, "custom")
        dialog.destroy()

    ttk.Button(body, text="從桌布擷取", style="M3Tonal.TButton",
               command=pick_from_wallpaper).pack(fill="x", pady=(0, 6))
    ttk.Button(body, text="自訂顏色…", style="M3Tonal.TButton",
               command=pick_custom).pack(fill="x")
    ttk.Label(body, text=f"目前: {settings.get('seed')}",
              style="M3Hint.TLabel").pack(anchor="w", pady=(12, 0))


# ═══════════════════════════ 功能 ═══════════════════════════

student_id_check = ""


def _downloads_dir():
    """找使用者的下載資料夾；找不到就退回家目錄。"""
    home = os.path.expanduser("~")
    for name in ("Downloads", "downloads", "下載"):
        candidate = os.path.join(home, name)
        if os.path.isdir(candidate):
            return candidate
    return home


def generate_timetable():
    global student_id_check

    student_id = student_id_entry.get()
    selected_type = class_type.get()
    student_id_check = student_id
    student_id_error_label.config(text="")

    if not student_id:
        student_id_error_label.config(text="請輸入學號")
        ics_button.config(state="disabled")
        return
    if not student_id.isdigit():
        student_id_error_label.config(text="不是你咋做到的")
        ics_button.config(state="disabled")
        return

    ics_button.config(state="disabled")
    show_status("查詢中…")
    try:
        result = get_single_class_table(student_id)
        if result == "無此人":
            raise Exception("此學號不存在或沒選課")
        if not result:
            raise Exception("查不到課表資料")

        if selected_type == "單一課表":
            timetable_canvas.display_single_timetable(result)
            show_status("課表已產生，切到「行事曆用課表」就能匯出 ICS", "success")
        else:
            timetable_canvas.display_mix_timetable(result)
            ics_button.config(state="normal")
            show_status("課表已產生，可以匯出 ICS 了", "success")

    except Exception as error:
        timetable_canvas.display_error(f"錯誤: {error}")
        show_status(str(error), "error")


def generate_ics():
    student_id = student_id_entry.get()

    try:
        if not student_id:
            raise Exception("偷刪學號是會被發現的喔")
        if not student_id.isdigit():
            raise Exception("通報阿茲卡班，有魔法師逃出來了")
        if student_id != student_id_check:
            raise Exception("你以為我不知道你換學號了嗎")

        result = get_mix_class_table(student_id)
        if result == "無此人":
            raise Exception("告訴下Nekolia你怎麼找到漏洞的")

        file_path = filedialog.asksaveasfilename(
            initialdir=_downloads_dir(),
            initialfile=f"{student_id}_timetable.ics",
            defaultextension=".ics",
            filetypes=[("iCalendar files", "*.ics"), ("All files", "*.*")],
        )
        if not file_path:
            return  # 使用者按取消

        today = datetime.date.today()
        weekday = today.weekday()
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")

        with open(file_path, "w", encoding="utf-8") as handle:
            handle.write("BEGIN:VCALENDAR\n")
            handle.write("VERSION:2.0\n")
            handle.write("PRODID:-//NTUB Timetable Generator//EN\n")
            handle.write("CALSCALE:GREGORIAN\n")
            handle.write("METHOD:PUBLISH\n")
            for index in range(len(result["class"])):
                class_name = result["class"][index]
                class_day = result["day"][index] - 1
                class_place = result["place"][index]
                class_start = result["start"][index]
                class_end = result["end"][index]

                days_ahead = (class_day - weekday + 7) % 7
                class_date = (today + datetime.timedelta(days=days_ahead)).strftime("%Y%m%d")

                handle.write("BEGIN:VEVENT\n")
                handle.write(f"SUMMARY:{class_name}\n")
                handle.write(f"DTSTART;TZID=Asia/Taipei:{class_date}T{class_start.replace(':', '')}00\n")
                handle.write(f"DTEND;TZID=Asia/Taipei:{class_date}T{class_end.replace(':', '')}00\n")
                handle.write(f"LOCATION:{class_place}\n")
                handle.write(f"UID:{class_date}T{class_start.replace(':', '')}00Z-{class_name}@ntub.tw\n")
                handle.write(f"DTSTAMP:{stamp}\n")
                if infinite_var.get():
                    handle.write("RRULE:FREQ=WEEKLY\n")
                else:
                    until = end_date_entry.get_date().strftime("%Y%m%d")
                    handle.write(f"RRULE:FREQ=WEEKLY;UNTIL={until}T235959Z\n")
                handle.write("END:VEVENT\n")
            handle.write("END:VCALENDAR\n")

        show_status(f"成功匯出到 {file_path}", "success")

    except Exception as error:
        show_status(str(error), "error")


generate_button.config(command=generate_timetable)
ics_button.config(command=generate_ics)
dark_button.config(command=toggle_dark)
theme_button.config(command=open_theme_dialog)

show_status(f"就緒（配色來源：{seed_source}）")
window.mainloop()
