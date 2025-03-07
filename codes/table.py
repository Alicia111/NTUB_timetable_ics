import requests
from bs4 import BeautifulSoup
import concurrent.futures
from typing import List, Dict, Tuple, Optional
import threading
from api import ClassTableURL
# 設定課表查詢API的URL
CLASS_TABLE_URL = ClassTableURL  
CLASS_MAP_KEY = ["name", "teacher", "room"]

def get_personal_class_table(student_id: str, today: int) -> Optional[BeautifulSoup]:
    """發送請求獲取課表並返回BeautifulSoup物件"""
    client = requests.Session()
    data = {"StdNo": student_id, "today": str(today)}
    
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Requested-With": "com.hanglong.NTUBStdApp"
    }
    
    try:
        response = client.post(CLASS_TABLE_URL, data=data, headers=headers)
        response.raise_for_status()  # 當HTTP請求發生錯誤時拋出異常
        
        # 解析HTML回應
        doc = BeautifulSoup(response.text, 'html.parser')
        return doc
    except requests.exceptions.RequestException as e:
        raise e

def personal_class_table_by_day(doc: BeautifulSoup) -> List[Optional[Dict[str, str]]]:
    """從HTML文件中提取特定日期的課程信息"""
    class_table_of_day = []
    
    # 尋找所有class為Stdtd001的td元素
    for td in doc.select("td.Stdtd001"):
        # 獲取第一個a標籤的文本(課程名稱)
        name_tag = td.select_one("a")
        name = name_tag.text.strip() if name_tag else ""
        
        if name == "":
            class_table_of_day.append(None)
            continue
        
        # 獲取HTML內容並按<br/>標籤分割
        html_content = str(td)
        class_info = html_content.split("<br/>")
        class_info[0] = name
        
        class_dict = {}
        for i in range(min(3, len(class_info))):
            class_dict[CLASS_MAP_KEY[i]] = class_info[i]
        
        # 修復多教師時教室顯示異常的問題
        if "room" in class_dict and class_dict["room"] and "<" in class_dict["room"]:
            class_dict["room"] = class_dict["room"].split("<")[0]
        
        class_table_of_day.append(class_dict)
    
    return class_table_of_day

def personal_class_table_time(doc: BeautifulSoup) -> List[Dict[str, str]]:
    """從課表中提取時間信息"""
    time_list = []
    
    # 尋找所有class為Stdth003的th元素
    for th in doc.select("th.Stdth003"):
        html_content = str(th)
        time_info = html_content.split("<br/>")
        
        # 確保time_info至少有3個元素
        while len(time_info) < 3:
            time_info.append("")
        
        time_list.append({
            "class_no": time_info[0],
            "start_at": time_info[1],
            "end_at": time_info[2]
        })
    
    return time_list

def personal_class_table(student_id: str) -> Tuple[List[List[Optional[Dict[str, str]]]], List[Dict[str, str]], List[Exception]]:
    """獲取學生一週七天的完整課表"""
    class_table = [[] for _ in range(7)]
    class_time = []
    error_list = []
    
    # 用於線程安全操作共享資源的鎖
    lock = threading.Lock()
    
    def fetch_day(today: int):
        try:
            doc = get_personal_class_table(student_id, today)
            day_classes = personal_class_table_by_day(doc)
            
            with lock:
                class_table[today-1] = day_classes
                
                # 只從第一天提取時間信息
                if today == 1:
                    nonlocal class_time
                    class_time = personal_class_table_time(doc)
        
        except Exception as e:
            with lock:
                error_list.append(e)
    
    # 使用ThreadPoolExecutor進行併發處理
    with concurrent.futures.ThreadPoolExecutor(max_workers=7) as executor:
        # 提交所有7天的任務
        futures = [executor.submit(fetch_day, day) for day in range(1, 8)]
        
        # 等待所有任務完成
        concurrent.futures.wait(futures)
    
    return class_table, class_time, error_list

# 使用示例


def get_single_class_table(student_id):
    class_table, class_time, errors = personal_class_table(student_id)
# Check if all elements in class_table are None
    if all(all(x is None for x in day) for day in class_table):
        #print("無此人")
        return "無此人"

    if errors:
        return []

    # Create a list to store formatted time slots
    result = []

    # Initialize time slots with empty data
    for i in range(len(class_time)):
        time_slot = {
            'time': f"{class_time[i]['start_at']} - {class_time[i]['end_at'][:-5]}"
        }
        result.append(time_slot)

    # Fill in class information for each day
    for day_index, day_classes in enumerate(class_table[:5]):  # Only process Monday to Friday
        day_map = {
            0: 'monday',
            1: 'tuesday',
            2: 'wednesday',
            3: 'thursday',
            4: 'friday',
            5: 'saturday',
            6: 'sunday'
        }

        # Check if there are any classes on this day
        has_classes = any(class_info is not None for class_info in day_classes)

        if has_classes:
            for i, class_info in enumerate(day_classes):
                if class_info:
                    class_str = f"{class_info['name']} - {class_info['teacher']} ({class_info['room']})"
                    result[i][day_map[day_index]] = class_str
 
    #print(result)
    return result
def get_mix_class_table(student_id) :   
    

    result={"class":[],"place":[],"day":[],"start":[],"end":[]}
    
    class_table, class_time, errors = personal_class_table(student_id)

    if all(all(x is None for x in day) for day in class_table):
        #print("無此人")
        return "無此人"

    if errors:
        #print(f"發生 {len(errors)} 個錯誤:")
        for e in errors:
            print(f"- {e}")

    else:
        print("\n課表:")
        for day_index, day_classes in enumerate(class_table):
            # Check if there are any classes on this day
            has_classes = any(class_info is not None for class_info in day_classes)

            if has_classes:
                
                #print(f"\n【星期{day_index + 1}】")
                
                # 用於存儲合併後的課程
                merged_classes = {}

                # 遍歷當天所有課程
                for i, class_info in enumerate(day_classes):
                    if class_info:
                        class_key = f"{class_info['name']}_{class_info['teacher']}_{class_info['room']}"
                        # 如果課程已存在，添加新的時間段
                        if class_key in merged_classes:
                            merged_classes[class_key]['periods'].append({
                                'period': i + 1,
                                'start': class_time[i]['start_at'],
                                'end': class_time[i]['end_at'][:-5]
                            })
                        else:
                            # 如果是新課程，創建新條目
                            merged_classes[class_key] = {
                                'name': class_info['name'],
                                'teacher': class_info['teacher'],
                                'room': class_info['room'],
                                'periods': [{
                                    'period': i + 1,
                                    'start': class_time[i]['start_at'],
                                    'end': class_time[i]['end_at'][:-5]
                                }]
                            }

                # 顯示合併後的課程
                for class_info in merged_classes.values():

                    periods = [p['period'] for p in class_info['periods']]
                    if len(periods) > 1:
                        period_str = f"第{periods[0]}~{periods[-1]}節:"
                    else:
                        period_str = f"第{periods[0]}節:"

                    #print(f"{period_str} {class_info['name']} - {class_info['teacher']} ({class_info['room']}) / ({class_info['periods'][0]['start']} - {class_info['periods'][-1]['end']})")
                    
                    result["class"].append(class_info['name'])
                    result["place"].append(class_info['room'])
                    result["day"].append(day_index+1)
                    result["start"].append(class_info['periods'][0]['start'])
                    result["end"].append(class_info['periods'][-1]['end'])
            
        return result

                    # periods = class_info['periods']
                    # period_str = f"第{periods[0]['period']}"
                    # if len(periods) > 1:
                    #     print(f"第{i+1}節: {class_info['name']} - {class_info['teacher']} ({class_info['room']}) / ({class_time[i]['start_at']} - {class_time[i]['end_at'][:-5]})")






if __name__ == "__main__":
    student_id = input("請輸入學號: ")
    #get_single_class_table(student_id)
    print(get_mix_class_table(student_id))