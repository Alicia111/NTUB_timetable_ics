from tkinter import *
from tkinter import ttk
from table import get_single_class_table, get_mix_class_table



window = Tk()
window.title("NTUB Timetable ICS")
window.geometry('1200x800')


# 載入 TTF 字型檔案
font_path = 'font/Iansui-Regular'  # 替換為實際路徑
font_name = "Iansui"  # 您可以為字型命名


# 註冊字型
window.option_add("*Font", font_name)
window.tk.call("font", "create", font_name, "-family", font_name)


student_id_label = Label(window, text="請輸入學號:", font=("Iansui", 12))
student_id_label.pack()
student_id_entry = Entry(window, font=("Iansui", 12))
student_id_entry.pack(pady=10)



student_id_entry.config(
    validate="key",
    validatecommand=(window.register(lambda P: P.isdigit() or P == ""), "%P",),
)





class_type_label = Label(window, text="請選擇課表類型:", font=("Iansui", 12))
class_type_label.pack(pady=10)
class_type = StringVar(value="單一課表")  # 預設值

single_class_radio = Radiobutton(window, text="課表", variable=class_type, value="單一課表", font=("Iansui", 12))
single_class_radio.pack()

mix_class_radio = Radiobutton(window, text="行事曆用課表", variable=class_type, value="混合課表", font=("Iansui", 12))
mix_class_radio.pack()

tree_frame = Frame(window)
tree_frame.pack(pady=20, fill='both', expand=True)

style = ttk.Style(tree_frame)

tree = ttk.Treeview(tree_frame)
tree.column('#0', width=0, stretch=NO)
scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
scrollbar.pack(side='right', fill='y')
tree.configure(yscrollcommand=scrollbar.set)
tree.pack(fill='both', expand=True)

def wrap_text(text, width=15):
    if not text:
        return ''
    words = text.split()
    lines = []
    current_line = []
    current_length = 0

    for word in words:
        if current_length + len(word) + 1 <= width:
            current_line.append(word)
            current_length += len(word) + 1
        else:
            lines.append(' '.join(current_line))
            current_line = [word]
            current_length = len(word)

    if current_line:
        lines.append(' '.join(current_line))

    return '\n'.join(lines)

def time_to_minutes(time_str):
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

def adjust_row_heights():
    max_height = 20
    for item in tree.get_children():
        values = tree.item(item)['values']
        max_lines = 1
        for value in values:
            if value:
                lines = str(value).count('\n') + 1
                max_lines = max(max_lines, lines)
        row_height = max_lines * 20
        max_height = max(max_height, row_height)
    style.configure('Treeview', rowheight=max_height)

def generate_timetable():
    student_id = student_id_entry.get()

    
    selected_type = class_type.get()

    for item in tree.get_children():
        tree.delete(item)

    try:
        if not student_id:
            raise Exception('請輸入學號')
        
        elif not student_id.isdigit():
            raise Exception('學號必須是數字')
        


        result = get_single_class_table(student_id)
        if result=='無此人':
            raise Exception ('此學號不存在或沒選課')
            
        
        if result:
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
            tree['columns'] = tuple(days)
            for col in tree['columns']:
                tree.column(col, anchor=CENTER, width=120)
                tree.heading(col, text=col, anchor=CENTER)

            sorted_slots = sorted(result, key=lambda x: time_to_minutes(x.get('time', '')))
            if selected_type == '單一課表':

                for time_slot in sorted_slots:
                    if any(time_slot.get(day.lower(), '') for day in days[1:]):
                        values = [wrap_text(time_slot.get('time', ''))]
                        for day in days[1:]:
                            values.append(wrap_text(time_slot.get(day.lower(), '')))
                        tree.insert('', 'end', values=tuple(values))

            elif selected_type == '混合課表':
                merged_slots = {}
                for time_slot in sorted_slots:
                    key = tuple(time_slot.get(day.lower(), '') for day in days[1:])
                    if key in merged_slots:
                        merged_slots[key]['time'] += f"\n{time_slot.get('time', '')}"
                    else:
                        merged_slots[key] = time_slot.copy()

                for key, merged_slot in merged_slots.items():
                    if any(key):
                        values = [wrap_text(merged_slot.get('time', ''))]
                        for value in key:
                            values.append(wrap_text(value))
                        tree.insert('', 'end', values=tuple(values))
            adjust_row_heights()
        else:
            tree['columns'] = ('Message',)
            tree.column('Message', anchor=CENTER, width=600)
            tree.heading('Message', text='Message', anchor=CENTER)
            tree.insert('', 'end', values=('無課表資料',))



    except Exception as e:
        tree['columns'] = ('Error',)
        tree.column('Error', anchor=CENTER, width=600)
        tree.heading('Error', text='Error', anchor=CENTER)
        tree.insert('', 'end', values=(f'錯誤: {str(e)}',))



    



generate_button = Button(window, text="產生課表", command=generate_timetable, font=("Iansui", 12))
generate_button.pack(pady=20)

window.mainloop()