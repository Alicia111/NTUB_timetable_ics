from tkinter import *
from tkinter import ttk
from table import get_single_class_table, get_mix_class_table
import datetime

class TimetableCanvas:
    def __init__(self, master, width=1100, height=600):
        self.master = master
        self.width = width
        self.height = height
        
        # 創建框架和畫布
        self.frame = Frame(master)
        self.frame.pack(pady=20, fill='both', expand=True)
        
        # 添加捲軸
        self.v_scrollbar = Scrollbar(self.frame, orient="vertical")
        self.v_scrollbar.pack(side='right', fill='y')
        
        self.h_scrollbar = Scrollbar(self.frame, orient="horizontal")
        self.h_scrollbar.pack(side='bottom', fill='x')
        
        # 創建畫布
        self.canvas = Canvas(
            self.frame, 
            width=width, 
            height=height, 
            bg="white",
            yscrollcommand=self.v_scrollbar.set,
            xscrollcommand=self.h_scrollbar.set
        )
        self.canvas.pack(fill='both', expand=True)
        
        # 配置捲軸
        self.v_scrollbar.config(command=self.canvas.yview)
        self.h_scrollbar.config(command=self.canvas.xview)
        
        # 儲存格資料
        self.cells = {}
        self.merged_cells = {}
        
        # 自適應設置
        self.set_adaptive_sizes()
        
    def set_adaptive_sizes(self):
        """根據畫布大小設置自適應的儲存格尺寸"""
        # 設置時間列寬度為畫布寬度的12%
        self.left_margin = int(self.width * 0.12)
        
        # 設置表頭高度為畫布高度的8%
        self.top_margin = int(self.height * 0.08)
        
        # 假設最多有5個工作日和8個時間段
        max_days = 6  # 包含時間列
        max_times = 8
        
        # 計算適合的儲存格尺寸
        self.cell_width = int((self.width - self.left_margin) / (max_days - 1))
        self.cell_height = int((self.height - self.top_margin) / max_times)
        
        # 目前的資料
        self.days = []
        self.time_slots = []
        
    def clear_canvas(self):
        """清除畫布上的所有內容"""
        self.canvas.delete("all")
        self.cells = {}
        self.merged_cells = {}
    
    def set_days(self, days):
        """設置星期幾的標題"""
        self.days = days
        self.draw_headers()
    
    def draw_headers(self):
        """繪製表頭"""
        # 設置畫布捲動區域
        total_width = self.left_margin + (len(self.days) - 1) * self.cell_width
        total_height = self.cell_height * len(self.time_slots) + self.top_margin
        self.canvas.config(scrollregion=(0, 0, total_width, total_height))
        
        # 繪製表頭背景
        self.canvas.create_rectangle(
            0, 0, total_width, self.top_margin, 
            fill="#e0e0e0", outline="black"
        )
        
        # 繪製時間列標題 (調整字體大小)
        header_font_size = max(10, min(12, int(self.top_margin / 3)))
        self.canvas.create_text(
            self.left_margin / 2, self.top_margin / 2,
            text=self.days[0], font=("Iansui", header_font_size, "bold")
        )
        
        # 繪製星期幾標題
        for i, day in enumerate(self.days[1:], 1):
            x = self.left_margin + (i - 1) * self.cell_width + self.cell_width / 2
            self.canvas.create_text(
                x, self.top_margin / 2,
                text=day, font=("Iansui", header_font_size, "bold")
            )
    
    def draw_grid(self):
        """繪製表格網格"""
        # 計算表格總寬度和高度
        total_width = self.left_margin + (len(self.days) - 1) * self.cell_width
        total_height = self.top_margin + len(self.time_slots) * self.cell_height
        
        # 設置畫布捲動區域
        self.canvas.config(scrollregion=(0, 0, total_width, total_height))
        
        # 繪製垂直網格線
        for i in range(len(self.days)):
            x = self.left_margin + i * self.cell_width
            self.canvas.create_line(
                x, self.top_margin, x, total_height,
                fill="black", width=1
            )
        
        # 繪製水平網格線
        for i in range(len(self.time_slots) + 1):
            y = self.top_margin + i * self.cell_height
            self.canvas.create_line(
                0, y, total_width, y,
                fill="black", width=1
            )
            
    def draw_time_slots(self, time_slots):
        """繪製時間槽"""
        self.time_slots = time_slots
        
        # 繪製網格
        self.draw_grid()
        
        # 調整字體大小
        time_font_size = max(8, min(10, int(self.left_margin / 10)))
        
        # 繪製時間欄
        for i, time_slot in enumerate(time_slots):
            y = self.top_margin + i * self.cell_height + self.cell_height / 2
            self.canvas.create_text(
                self.left_margin / 2, y,
                text=time_slot, font=("Iansui", time_font_size),
                width=self.left_margin - 10  # 設置文字換行寬度
            )
            
    def set_cell_content(self, row, col, content):
        """設置儲存格內容"""
        # 計算儲存格位置
        x1 = self.left_margin + (col - 1) * self.cell_width
        y1 = self.top_margin + row * self.cell_height
        x2 = x1 + self.cell_width
        y2 = y1 + self.cell_height
        
        # 創建儲存格 ID
        cell_id = f"cell_{row}_{col}"
        
        # 檢查是否已經有內容
        if cell_id in self.cells:
            # 刪除舊內容
            self.canvas.delete(self.cells[cell_id])
            
        # 調整字體大小
        font_size = self.calculate_font_size(content, self.cell_width - 10, self.cell_height - 10)
            
        # 創建新內容
        text_id = self.canvas.create_text(
            (x1 + x2) / 2, (y1 + y2) / 2,
            text=content, font=("Iansui", font_size),
            width=self.cell_width - 10,  # 設置文字換行寬度
            tags=cell_id
        )
        
        self.cells[cell_id] = text_id
    
    def calculate_font_size(self, text, max_width, max_height):
        """根據文字長度和儲存格大小計算適合的字體大小"""
        # 基礎字體大小
        base_size = 10
        
        # 如果文字較長，減小字體
        text_length = len(text)
        lines = text.count('\n') + 1
        
        if text_length > 30 or lines > 2:
            return max(8, base_size - 2)
        elif text_length > 15 or lines > 1:
            return max(9, base_size - 1)
        else:
            return base_size
        
    def merge_cells(self, start_row, end_row, col, content):
        """合併儲存格"""
        # 計算合併儲存格位置
        x1 = self.left_margin + (col - 1) * self.cell_width
        y1 = self.top_margin + start_row * self.cell_height
        x2 = x1 + self.cell_width
        y2 = self.top_margin + (end_row + 1) * self.cell_height
        
        # 創建合併儲存格 ID
        merge_id = f"merge_{start_row}_{end_row}_{col}"
        
        # 清除要合併的儲存格
        for row in range(start_row, end_row + 1):
            cell_id = f"cell_{row}_{col}"
            if cell_id in self.cells:
                self.canvas.delete(self.cells[cell_id])
                del self.cells[cell_id]
                
        # 創建合併儲存格外框
        rect_id = self.canvas.create_rectangle(
            x1, y1, x2, y2,
            fill="white", outline="black",
            tags=merge_id
        )
        
        # 調整字體大小
        cell_height = y2 - y1
        font_size = self.calculate_font_size(content, self.cell_width - 10, cell_height - 10)
        
        # 創建文字
        text_id = self.canvas.create_text(
            (x1 + x2) / 2, (y1 + y2) / 2,
            text=content, font=("Iansui", font_size),
            width=self.cell_width - 10,  # 設置文字換行寬度
            tags=merge_id
        )
        
        self.merged_cells[merge_id] = (rect_id, text_id)
        
    def display_single_timetable(self, result):
        """顯示單一課表"""
        self.clear_canvas()
        
        # 檢查每一天有沒有課程
        days = ['Time']
        if any(slot.get('monday') for slot in result):
            days.append('Monday')
        if any(slot.get('tuesday') for slot in result):
            days.append('Tuesday')
        if any(slot.get('wednesday') for slot in result):
            days.append('Wednesday')
        if any(slot.get('thursday') for slot in result):
            days.append('Thursday')
        if any(slot.get('friday') for slot in result):
            days.append('Friday')
            
        self.set_days(days)
        
        # 只保留有課程的時間槽
        times_with_courses = []
        for time_slot in result:
            if any(time_slot.get(day.lower(), '') for day in days[1:]):
                times_with_courses.append(time_slot.get('time', ''))
        
        # 去除重複並排序
        unique_times = sorted(set(times_with_courses), key=lambda x: self.time_to_minutes(x))
        self.draw_time_slots(unique_times)
        
        # 繪製課程
        for time_slot in result:
            if any(time_slot.get(day.lower(), '') for day in days[1:]):
                time = time_slot.get('time', '')
                row = unique_times.index(time)
                
                # 對每一天檢查是否有課
                for i, day in enumerate(days[1:], 1):
                    content = time_slot.get(day.lower(), '')
                    if content:
                        self.set_cell_content(row, i, content)
    
    def display_mix_timetable(self, result):
        """顯示混合課表（行事曆用）"""
        self.clear_canvas()
        
        # 檢查每一天有沒有課程
        days = ['Time']
        if any(slot.get('monday') for slot in result):
            days.append('Monday')
        if any(slot.get('tuesday') for slot in result):
            days.append('Tuesday')
        if any(slot.get('wednesday') for slot in result):
            days.append('Wednesday')
        if any(slot.get('thursday') for slot in result):
            days.append('Thursday')
        if any(slot.get('friday') for slot in result):
            days.append('Friday')
            
        self.set_days(days)
        
        # 只保留有課程的時間槽
        times_with_courses = []
        for time_slot in result:
            if any(time_slot.get(day.lower(), '') for day in days[1:]):
                times_with_courses.append(time_slot.get('time', ''))
        
        # 去除重複並排序
        unique_times = sorted(set(times_with_courses), key=lambda x: self.time_to_minutes(x))
        self.draw_time_slots(unique_times)
        
        # 為每一天找出連續的相同課程
        for day_index, day in enumerate(days[1:], 1):
            day_lower = day.lower()
            
            # 建立每個時間槽與課程的對應
            time_course_map = {}
            for time_slot in result:
                course = time_slot.get(day_lower, '')
                if course:
                    time = time_slot.get('time', '')
                    time_index = unique_times.index(time)
                    time_course_map[time_index] = course
            
            # 尋找連續的課程
            start_row = None
            current_course = None
            
            for i in range(len(unique_times)):
                if i in time_course_map:
                    course = time_course_map[i]
                    
                    if course == current_course:
                        # 課程相同，繼續累積
                        continue
                    else:
                        # 新課程，結束前一個課程的合併
                        if start_row is not None and i-1 > start_row:
                            # 合併前一個課程的儲存格
                            merged_content = f"{current_course}"
                            self.merge_cells(start_row, i-1, day_index, merged_content)
                        elif start_row is not None:
                            # 單一時間槽，無需合併
                            self.set_cell_content(start_row, day_index, 
                                                 f"{current_course}")
                        
                        # 開始新課程
                        start_row = i
                        current_course = course
                
                elif start_row is not None:
                    # 遇到空白課程，結束合併
                    if i-1 > start_row:
                        # 合併前一個課程的儲存格
                        merged_content = f"{current_course}"
                        self.merge_cells(start_row, i-1, day_index, merged_content)
                    else:
                        # 單一時間槽，無需合併
                        self.set_cell_content(start_row, day_index, 
                                             f"{current_course}")
                    
                    start_row = None
                    current_course = None
            
            # 處理最後一個課程
            if start_row is not None:
                end_row = len(unique_times) - 1
                if end_row > start_row:
                    # 合併最後的課程儲存格
                    merged_content = f"{current_course}"
                    self.merge_cells(start_row, end_row, day_index, merged_content)
                else:
                    # 單一時間槽，無需合併
                    self.set_cell_content(start_row, day_index, 
                                         f"{current_course}")
    
    def display_error(self, message):
        """顯示錯誤訊息"""
        self.clear_canvas()
        
        # 設置畫布大小
        self.canvas.config(scrollregion=(0, 0, self.width, self.height))
        
        # 繪製錯誤訊息
        self.canvas.create_text(
            self.width / 2, self.height / 2,
            text=message, font=("Iansui", 14, "bold"),
            fill="red"
        )
    
    @staticmethod
    def time_to_minutes(time_str):
        """將時間字符串轉換為分鐘數，用於排序"""
        if not time_str or '-' not in time_str:
            return 0
        start_time = time_str.split('-')[0].strip()
        if not start_time:
            return 0
        try:
            hours, minutes = map(int, start_time.split(':'))
            return hours * 60 + minutes
        except:
            return 0

# 主視窗設置
window = Tk()
window.title("NTUB Timetable ICS Generator by Nekolia") 
window.geometry('1000x700')

# 載入字型
font_name = "Iansui"
window.option_add("*Font", font_name)
window.tk.call("font", "create", font_name, "-family", font_name)

# 創建框架來容納控制項
control_frame = Frame(window)
control_frame.pack(fill='x', padx=20, pady=10)

# 學號輸入區 - 放在左側
id_frame = Frame(control_frame)
id_frame.pack(side='left', padx=10)

student_id_label = Label(id_frame, text="請輸入學號:", font=("Iansui", 12))
student_id_label.pack(side='left')
student_id_entry = Entry(id_frame, font=("Iansui", 12), width=12)
student_id_entry.pack(side='left', padx=5)

student_id_error_label=Label(id_frame, text="", font=("Iansui", 10), fg="red",state='disabled')
student_id_error_label.pack(side='left', padx=25)

# 驗證學號只能輸入數字
student_id_entry.config(
    validate="key",
    validatecommand=(window.register(lambda P: P.isdigit() or P == ""), "%P",),
)

# 課表類型選擇 - 放在中間
type_frame = Frame(control_frame)
type_frame.pack(side='left', padx=20)

class_type_label = Label(type_frame, text="課表類型:", font=("Iansui", 12))
class_type_label.pack(side='left')
class_type = StringVar(value="單一課表")  # 預設值

single_class_radio = Radiobutton(type_frame, text="課表", variable=class_type, value="單一課表", font=("Iansui", 12))
single_class_radio.pack(side='left', padx=5)

mix_class_radio = Radiobutton(type_frame, text="行事曆用課表", variable=class_type, value="混合課表", font=("Iansui", 12))
mix_class_radio.pack(side='left', padx=5)

# 產生課表按鈕 - 放在右側
button_frame = Frame(control_frame)
button_frame.pack(side='right', padx=10)

generate_button = Button(button_frame, text="產生課表", font=("Iansui", 12), bg="#F0C9E1", fg="black", padx=10)
generate_button.pack()

ics_button = Button(button_frame, text="匯出 ICS", font=("Iansui", 12), bg="#F0C9E1", fg="black", padx=10, state='disabled')
ics_button.pack()
ics_error_label = Label(button_frame, text="", font=("Iansui", 10), fg="red",state='disabled')
ics_error_label.pack()

# 創建課表畫布 - 指定適合的大小
timetable_canvas = TimetableCanvas(window, width=960, height=560)

student_id_check=""

# 產生課表函數
def generate_timetable():
    
    #取得學號
    student_id = student_id_entry.get()
    selected_type = class_type.get()

    #驗證學號
    global student_id_check
    student_id_check=student_id

    #清空錯誤訊息
    student_id_error_label.config(text='',state='disabled')
    ics_error_label.config(text='',state='disabled')

    try:
        if not student_id:
            error_type = '學號'
            raise Exception('請輸入學號')
        
        elif not student_id.isdigit():
            error_type='學號'
            raise Exception('不是你咋做到的')
            
        result = get_single_class_table(student_id)
        if result == '無此人':
            error_type='沒人'
            raise Exception('此學號不存在或沒選課')
            
        if result:
            if selected_type == '單一課表':
                timetable_canvas.display_single_timetable(result)
            else:  # 混合課表
                timetable_canvas.display_mix_timetable(result)
                ics_button.config(state='normal')

            
    except Exception as e:
        if error_type == '學號':
            student_id_error_label.config(text=str(e),state='normal')
            ics_button.config(state='disabled')

        else:
            timetable_canvas.display_error(f'錯誤: {str(e)}')
            ics_button.config(state='disabled')

def generate_ics():
    student_id = student_id_entry.get()

    ics_error_label.config(text='',state='disabled')
    
    global student_id_check
    

    try:
        if not student_id:
            raise Exception('偷刪學號是會被發現的喔')
        
        elif not student_id.isdigit():
            raise Exception('通報阿茲卡班，有魔法師逃出來了')
        
        elif student_id != student_id_check:
            raise Exception('你以為我不知道你換學號了嗎')

        result = get_mix_class_table(student_id)
        if result == '無此人':
            raise Exception('告訴下Nekolia你怎麼找到漏洞的')
        
        else:
            today = datetime.date.today()
            weekday = today.weekday()

            with open(f"ics_file/{student_id}_timetable.ics", "w+", encoding="utf-8") as f:
                f.write("BEGIN:VCALENDAR\n")
                f.write("VERSION:2.0\n")
                f.write("PRODID:-//NTUB Timetable Generator//EN\n")  # Updated PRODID
                f.write("CALSCALE:GREGORIAN\n")
                f.write("METHOD:PUBLISH\n")
                for i in range(0, len(result["class"])):
                    class_name = result["class"][i]
                    class_day = result["day"][i] - 1
                    class_place = result["place"][i]
                    class_start = result["start"][i]
                    class_end = result["end"][i]

                    go_to_class_date = today + datetime.timedelta(class_day - weekday + 7)

                    uid = f"{go_to_class_date.strftime('%Y%m%d')}T{class_start.replace(':','')}00Z-{class_name}@ntub.tw"  # UID generation
                    f.write("BEGIN:VEVENT\n")
                    f.write(f"SUMMARY:{class_name}\n")
                    f.write(f"DTSTART;TZID=Asia/Taipei:{go_to_class_date.strftime('%Y%m%d')}T{class_start.replace(':','')}00\n")
                    f.write(f"DTEND;TZID=Asia/Taipei:{go_to_class_date.strftime('%Y%m%d')}T{class_end.replace(':','')}00\n")
                    f.write(f"LOCATION:{class_place}\n")
                    f.write(f"UID:{uid}\n")  # Added UID
                    f.write(f"DTSTAMP:{today.strftime('%Y%m%d')}T000000Z\n")  # Added DTSTAMP
                    # Optional: Add description
                    # f.write(f"DESCRIPTION:{class_name} 課程\n")
                    f.write("END:VEVENT\n")

                f.write("END:VCALENDAR\n")
                    
                print(go_to_class_date)
                

    except Exception as e:
        ics_error_label.config(text=str(e),state='normal')


# 設定按鈕命令
generate_button.config(command=generate_timetable)
ics_button.config(command=generate_ics)
# 狀態欄
status_frame = Frame(window, height=20)
status_frame.pack(fill='x', side='bottom')
status_label = Label(status_frame, text="就緒", bd=1, relief=SUNKEN, anchor=W)
status_label.pack(fill='x')

window.mainloop()