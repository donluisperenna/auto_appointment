import tkinter as tk
from tkinter import messagebox
import tkinter.scrolledtext as scrolledtext
import json
import os
import sys
import auto_appointment
import threading
from tkinter import ttk  
import re              
from datetime import date, timedelta, datetime
try:
    import holidays
    # 載入台灣國定假日支援
    tw_holidays = holidays.Taiwan()
except ImportError:
    tw_holidays = None

CONFIG_FILE = 'config.json'

# 預設設定檔（當 config.json 不存在時使用）
DEFAULT_CONFIG = {
    "target_dept": "家庭醫學部",
    "target_doctors": ["123", "321"],
    "target_date": "9/29",
    "my_id": "A135724680",
    "my_year": "69",
    "my_month": "1",
    "my_day": "15",
    "target_time": "",
    "automatic_confirm": "False",
    "discord_webhook_url": ""
}

# 攔截 print() 輸出的自定義類別
class PrintLogger:
    def __init__(self, text_widget):
        self.text_widget = text_widget

    def write(self, text):
        # 將文字插入到文字框的最後面
        self.text_widget.insert(tk.END, text)
        # 自動捲動到最底端
        self.text_widget.see(tk.END)

    def flush(self):
        pass

class AppGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("自動掛號設定系統")
        self.root.geometry("1100x1000")
        
        # ===== 定義全域色彩與字體 =====
        self.bg_color = "#F0F2F5"        # 視窗背景色 (淺灰)
        self.text_color = "#333333"      # 文字顏色 (深灰)
        self.btn_bg = "#2563EB"          # 按鈕背景色 (現代藍)
        self.btn_fg = "#FFFFFF"          # 按鈕文字色 (白)
        self.log_bg = "#FFFFFF"          # Log區背景色
        self.log_fg = "#000000"          # Log區文字色
        
        self.font_title = ("微軟正黑體", 18, "bold")
        self.font_main = ("微軟正黑體", 18)
        self.font_log = ("微軟正黑體", 18) # 適合顯示程式碼或Log的等寬字體

        style = ttk.Style()
        style.theme_use('clam')  # 'clam' 主題最容易自訂顏色與扁平化

        # 1. Combobox 輸入框本體配色
        style.configure("TCombobox",
                        font=self.font_main,
                        padding=6,                    # 增加上下內邊距，看起來更大方
                        background="#FFFFFF",         # 右側箭頭按鈕背景色 (白色)
                        fieldbackground="#FFFFFF",    # 輸入框本體背景 (純白)
                        foreground=self.text_color,   # 文字深灰
                        arrowcolor="#4B5563",         # 下拉箭頭顏色 (深灰)
                        bordercolor="#D1D5DB",        # 邊框顏色 (細緻淺灰)
                        lightcolor="#D1D5DB",
                        darkcolor="#D1D5DB")

        # 2. 狀態變化 (滑鼠懸停/點擊時的邊框色彩變化)
        style.map("TCombobox",
                  fieldbackground=[('readonly', '#FFFFFF')],
                  selectbackground=[('readonly', '#FFFFFF')], # 避免點選文字時出現藍底反白
                  selectforeground=[('readonly', self.text_color)],
                  bordercolor=[('focus', '#2563EB'), ('hover', '#9CA3AF')]) # 聚焦時變藍色邊框

        # 3. 彈出的下拉清單 (Popdown Listbox) 美化
        self.root.option_add('*TCombobox*Listbox.font', self.font_main)
        self.root.option_add('*TCombobox*Listbox.background', '#FFFFFF')         # 清單背景白底
        self.root.option_add('*TCombobox*Listbox.foreground', self.text_color)    # 清單文字深灰
        self.root.option_add('*TCombobox*Listbox.selectBackground', '#E0E7FF')   # 選中項目高亮背景 (高質感淡藍)
        self.root.option_add('*TCombobox*Listbox.selectForeground', '#1E40AF')   # 選中項目高亮文字 (深藍)
        self.root.option_add('*TCombobox*Listbox.relief', 'flat')
        self.root.option_add('*TCombobox*Listbox.borderWidth', '1')

        self.root.configure(bg=self.bg_color)
        
        self.config_data = self.load_config()
        self.entries = {}
        
        self.create_widgets()
        
        sys.stdout = PrintLogger(self.log_area, self)
        sys.stderr = PrintLogger(self.log_area, self)

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                messagebox.showerror("錯誤", f"讀取設定檔失敗: {e}")
        return DEFAULT_CONFIG

    def save_config(self):
        # 將介面上的資料更新回字典
        for key, entry in self.entries.items():
            if key == "target_doctors":
                # 將逗號分隔的字串轉回 List，並去除空白
                doctors_str = entry.get()
                self.config_data[key] = [d.strip() for d in doctors_str.split(',') if d.strip()]
            elif key == "automatic_confirm":
                # 將 Checkbox 的布林值轉為字串 "True" 或 "False"
                self.config_data[key] = str(self.auto_confirm_var.get())
            else:
                self.config_data[key] = entry.get()

        # 寫入 JSON
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config_data, f, ensure_ascii=False, indent=4)
            return True
        except Exception as e:
            messagebox.showerror("錯誤", f"儲存設定檔失敗: {e}")
            return False
    def create_widgets(self):
        form_frame = tk.Frame(self.root, bg=self.bg_color)
        form_frame.pack(pady=15, padx=30) # 置中排版

        tk.Label(form_frame, text="掛號參數設定", font=self.font_title, bg=self.bg_color, \
                 fg="#1F2937").grid(row=0, column=0, columnspan=2, pady=(0, 20))
        departments = [
            "內科系-內科部", "復健部", "老年醫學部", "腫瘤醫學部", "家庭醫學部", 
            "精神部", "神經部", "環境暨職業醫學部", "基因醫學部", "外科系-外科部", 
            "口腔醫學部", "骨科部", "皮膚部", "婦產部", "泌尿部", "眼科部", 
            "麻醉部", "耳鼻喉部", "其他科系-血友病中心", "影像醫學部", 
            "形體美容中心", "營養室", "乳房醫學中心", "核子醫學部", 
            "臨床心理中心", "傷口造護小組", "顱顏醫療暨形態科學發展中心"
        ]

        row = 1
        # --- 1. 科別下拉選單 ---
        tk.Label(form_frame, text="目標科別", font=self.font_main, bg=self.bg_color, fg=self.text_color).grid(row=row, column=0, sticky='e', padx=10, pady=3)
        self.dept_cb = ttk.Combobox(form_frame, values=departments, font=self.font_main, width=33, state="readonly")
        current_dept = self.config_data.get("target_dept", "家庭醫學部")
        self.dept_cb.set(current_dept if current_dept in departments else departments[4])
        self.dept_cb.grid(row=row, column=1, columnspan=2, pady=3, sticky='w')
        self.entries["target_dept"] = self.dept_cb
        row += 1

        # --- 2. 目標醫師 (一般輸入框) ---
        tk.Label(form_frame, text="目標醫師 (逗號分隔)", font=self.font_main, bg=self.bg_color, fg=self.text_color).grid(row=row, column=0, sticky='e', padx=10, pady=3)
        doc_entry = tk.Entry(form_frame, font=self.font_main, width=35, relief="solid", bd=1)
        doc_entry.insert(0, ", ".join(self.config_data.get("target_doctors", [])))
        doc_entry.grid(row=row, column=1, columnspan=2, pady=3, sticky='w')
        self.entries["target_doctors"] = doc_entry
        row += 1

        # --- 3. 目標日期 (月/日 下拉選單組合，免安裝第三方套件) ---
        tk.Label(form_frame, text="門診日期", font=self.font_main, bg=self.bg_color, fg=self.text_color).grid(row=row, column=0, sticky='e', padx=10, pady=3)
        date_frame = tk.Frame(form_frame, bg=self.bg_color)
        date_frame.grid(row=row, column=1, columnspan=2, sticky='w', pady=3)

        curr_date = self.config_data.get("target_date", "9/29").split('/')
        curr_m = curr_date[0] if len(curr_date) == 2 else "9"
        curr_d = curr_date[1] if len(curr_date) == 2 else "29"

        self.target_month_cb = ttk.Combobox(date_frame, values=[str(i) for i in range(1, 13)], width=6, font=self.font_main, state="readonly")
        self.target_month_cb.set(curr_m)
        self.target_month_cb.pack(side=tk.LEFT)
        tk.Label(date_frame, text="月", font=self.font_main, bg=self.bg_color).pack(side=tk.LEFT, padx=(2, 8))

        self.target_day_cb = ttk.Combobox(date_frame, values=[str(i) for i in range(1, 32)], width=6, font=self.font_main, state="readonly")
        self.target_day_cb.set(curr_d)
        self.target_day_cb.pack(side=tk.LEFT)
        tk.Label(date_frame, text="日", font=self.font_main, bg=self.bg_color).pack(side=tk.LEFT, padx=(2, 0))
        row += 1

        # --- 4. 目標時間 ---
        # --- 4. 目標時間 (立即模式 Checkbox + 時/分/秒選單 + 兩大快捷鍵) ---
        tk.Label(form_frame, text="搶號時間", font=self.font_main, bg=self.bg_color, fg=self.text_color).grid(row=row, column=0, sticky='e', padx=10, pady=3)
        time_frame = tk.Frame(form_frame, bg=self.bg_color)
        time_frame.grid(row=row, column=1, columnspan=2, sticky='w', pady=3)

        # 解析原本 config 的時間設定
        raw_time = self.config_data.get("target_time", "").strip()
        is_immediate_mode = (raw_time == "")

        curr_time = raw_time.split(':') if raw_time else ["00", "00", "00"]
        def_h = curr_time[0] if len(curr_time) == 3 else "00"
        def_m = curr_time[1] if len(curr_time) == 3 else "00"
        def_s = curr_time[2] if len(curr_time) == 3 else "00"

        # 下拉選單元件
        self.hour_cb = ttk.Combobox(time_frame, values=[f"{i:02d}" for i in range(24)], width=4, font=self.font_main, state="readonly")
        self.hour_cb.set(def_h)
        self.hour_cb.pack(side=tk.LEFT)
        self.colon1_lbl = tk.Label(time_frame, text=":", font=self.font_main, bg=self.bg_color)
        self.colon1_lbl.pack(side=tk.LEFT, padx=1)

        self.min_cb = ttk.Combobox(time_frame, values=[f"{i:02d}" for i in range(60)], width=4, font=self.font_main, state="readonly")
        self.min_cb.set(def_m)
        self.min_cb.pack(side=tk.LEFT)
        self.colon2_lbl = tk.Label(time_frame, text=":", font=self.font_main, bg=self.bg_color)
        self.colon2_lbl.pack(side=tk.LEFT, padx=1)

        self.sec_cb = ttk.Combobox(time_frame, values=[f"{i:02d}" for i in range(60)], width=4, font=self.font_main, state="readonly")
        self.sec_cb.set(def_s)
        self.sec_cb.pack(side=tk.LEFT)

        # 快捷鍵 1：搶兩週後 00:00:00
        def set_midnight():
            self.immediate_var.set(False)
            self.toggle_time_mode()
            self.hour_cb.set("00")
            self.min_cb.set("00")
            self.sec_cb.set("00")
            
            # 自動連動掛號日期至兩週後 (第 14 天)
            target_d = date.today() + timedelta(days=14)
            self.target_month_cb.set(str(target_d.month))
            self.target_day_cb.set(str(target_d.day))

        # 快捷鍵 2：搶隔天 (時間設為 18:00:00，門診日期自動跳到明天)
        def set_evening():
            self.immediate_var.set(False)
            self.toggle_time_mode()
            self.hour_cb.set("18")
            self.min_cb.set("00")
            self.sec_cb.set("00")
            
            # 自動連動掛號日期至隔天
            target_d = date.today() + timedelta(days=1)
            self.target_month_cb.set(str(target_d.month))
            self.target_day_cb.set(str(target_d.day))

        self.btn_midnight = tk.Button(time_frame, text="兩週後 (00:00)", font=("微軟正黑體", 9), command=set_midnight, relief="groove")
        self.btn_midnight.pack(side=tk.LEFT, padx=(6, 2))

        self.btn_evening = tk.Button(time_frame, text="搶隔天 (18:00)", font=("微軟正黑體", 9), command=set_evening, relief="groove")
        self.btn_evening.pack(side=tk.LEFT, padx=(2, 6))

        # 立即執行 Checkbox (勾選則代表 target_time 為空字串，進入常駐監聽)
        self.immediate_var = tk.BooleanVar(value=is_immediate_mode)
        self.chk_immediate = tk.Checkbutton(time_frame, text="立即搶號", variable=self.immediate_var, 
                                            font=self.font_main, bg=self.bg_color, fg=self.text_color, 
                                            activebackground=self.bg_color, selectcolor=self.bg_color,
                                            command=self.toggle_time_mode)
        self.chk_immediate.pack(side=tk.LEFT, padx=4)

        # 初始根據 config 設定反灰狀態
        self.toggle_time_mode()

        self.entries["target_time"] = None
        row += 1

        # --- 5. 身分證字號 (密碼遮罩 + 顯示切換按鈕) ---
        tk.Label(form_frame, text="身分證字號", font=self.font_main, bg=self.bg_color, fg=self.text_color).grid(row=row, column=0, sticky='e', padx=10, pady=3)
        self.id_entry = tk.Entry(form_frame, font=self.font_main, width=28, relief="solid", bd=1, show="*")
        self.id_entry.insert(0, self.config_data.get("my_id", ""))
        self.id_entry.grid(row=row, column=1, pady=3, sticky='w')
        self.entries["my_id"] = self.id_entry

        self.show_id = False
        self.toggle_btn = tk.Button(form_frame, text="顯示", font=("微軟正黑體", 9), command=self.toggle_id_visibility, relief="groove")
        self.toggle_btn.grid(row=row, column=2, padx=5, sticky='w')
        row += 1

        # --- 6. 出生年月日 ---
        for key, text in [("my_year", "出生年 (民國)"), ("my_month", "出生月"), ("my_day", "出生日")]:
            tk.Label(form_frame, text=text, font=self.font_main, bg=self.bg_color, fg=self.text_color).grid(row=row, column=0, sticky='e', padx=10, pady=3)
            e = tk.Entry(form_frame, font=self.font_main, width=35, relief="solid", bd=1)
            e.insert(0, self.config_data.get(key, ""))
            e.grid(row=row, column=1, columnspan=2, pady=3, sticky='w')
            self.entries[key] = e
            row += 1

        # --- 7. Discord Webhook ---
        tk.Label(form_frame, text="Discord Webhook", font=self.font_main, bg=self.bg_color, fg=self.text_color).grid(row=row, column=0, sticky='e', padx=10, pady=3)
        webhook_entry = tk.Entry(form_frame, font=self.font_main, width=35, relief="solid", bd=1)
        webhook_entry.insert(0, self.config_data.get("discord_webhook_url", ""))
        webhook_entry.grid(row=row, column=1, columnspan=2, pady=3, sticky='w')
        self.entries["discord_webhook_url"] = webhook_entry
        row += 1

        # Checkbox 設定
        self.auto_confirm_var = tk.BooleanVar(value=self.config_data.get("automatic_confirm") == "True")
        chk = tk.Checkbutton(form_frame, text="自動確認送出", variable=self.auto_confirm_var, 
                             font=self.font_main, bg=self.bg_color, fg=self.text_color, 
                             activebackground=self.bg_color, selectcolor=self.bg_color)
        chk.grid(row=row, column=1, sticky='w', pady=5)
        self.entries["automatic_confirm"] = None
        row += 1

        # 按鈕設計：扁平化、顏色亮眼、加上 cursor="hand2" 讓滑鼠移過去變成手指
        self.run_btn = tk.Button(form_frame, text="儲存並執行", command=self.run_program, 
                                 bg=self.btn_bg, fg=self.btn_fg, font=("微軟正黑體", 14, "bold"), 
                                 relief="flat", cursor="hand2")
        # 使用 ipadx 和 ipady 來增加按鈕內部的留白(變大)
        self.run_btn.grid(row=row, column=0, columnspan=2, pady=25, ipadx=40, ipady=5)
        row += 1
        
        log_frame = tk.Frame(self.root, bg=self.bg_color)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=40, pady=(0, 40))

        tk.Label(log_frame, text="執行紀錄", font=("微軟正黑體", 14, "bold"), bg=self.bg_color, fg=self.text_color).pack(anchor='w', pady=(0, 5))
        
        # 4. ScrolledText 也設定 fill=tk.BOTH, expand=True，它就會跟著視窗變寬變高
        self.log_area = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=18,
                                                  font=self.font_log, bg=self.log_bg, fg=self.log_fg, 
                                                  relief="flat", padx=15, pady=15)
        self.log_area.pack(fill=tk.BOTH, expand=True)

        # 確認送出按鈕 (初始為停用狀態)
        self.confirm_btn = tk.Button(
            form_frame, 
            text="確認送出掛號 (Enter)", 
            command=self.trigger_confirm, 
            bg="#10B981", fg="#FFFFFF", 
            font=("微軟正黑體", 14, "bold"), 
            relief="flat", cursor="hand2", 
            state=tk.DISABLED
        )
        self.confirm_btn.grid(row=row, column=0, columnspan=2, pady=(0, 20), ipadx=30, ipady=5)
        row += 1

        # 綁定整重視窗的 Enter 鍵
        self.root.bind("<Return>", lambda event: self.trigger_confirm())

    def toggle_id_visibility(self):
        """切換身分證字號明文與星號遮罩"""
        if self.show_id:
            self.id_entry.config(show="*")
            self.toggle_btn.config(text="顯示")
            self.show_id = False
        else:
            self.id_entry.config(show="")
            self.toggle_btn.config(text="隱藏")
            self.show_id = True
    def toggle_time_mode(self):
        """根據是否勾選『立即執行』動態切換時間下拉選單的啟用/停用狀態"""
        if self.immediate_var.get():
            # 取得目前的時、分、秒並自動填入選單
            now = datetime.now()
            self.hour_cb.set(f"{now.hour:02d}")
            self.min_cb.set(f"{now.minute:02d}")
            self.sec_cb.set(f"{now.second:02d}")

            # 填完後反灰停用
            self.hour_cb.config(state="disabled")
            self.min_cb.config(state="disabled")
            self.sec_cb.config(state="disabled")
        else:
            self.hour_cb.config(state="readonly")
            self.min_cb.config(state="readonly")
            self.sec_cb.config(state="readonly")
    def validate_inputs(self):
        """即時格式防呆驗證"""
        # 1. 驗證身分證格式 (1碼大寫英文字母 + 9碼數字)
        my_id = self.entries["my_id"].get().strip().upper()
        if not re.match(r"^[A-Z][1289]\d{8}$", my_id):
            messagebox.showwarning("格式錯誤", "身分證字號格式不正確！\n應為 1 碼英文大寫搭配 9 碼數字。")
            return False
        # 2. 驗證是否有填寫醫生代號
        doctors_str = self.entries["target_doctors"].get().strip()
        if not doctors_str:
            messagebox.showwarning("欄位遺漏", "請至少輸入一位目標醫師姓名！")
            return False

        doctor_list = [d.strip() for d in doctors_str.split(',') if d.strip()]
        if not doctor_list:
            messagebox.showwarning("欄位遺漏", "請輸入有效的目標醫師姓名！")
            return False

        chinese_name_pattern = r"^[\u4e00-\u9fa5]{2,}$"
        for doc in doctor_list:
            if not re.match(chinese_name_pattern, doc):
                messagebox.showwarning(
                    "格式錯誤", 
                    f"醫師姓名「{doc}」格式不正確！\n必須全為中文字，且長度至少 2 個字以上。"
                )
                return False

        # 3. 驗證出生年月日是否皆為純數字
        year_str = self.entries["my_year"].get().strip()
        month_str = self.entries["my_month"].get().strip()
        day_str = self.entries["my_day"].get().strip()

        if not (year_str.isdigit() and month_str.isdigit() and day_str.isdigit()):
            messagebox.showwarning("格式錯誤", "出生年、月、日皆必須填寫純數字！")
            return False

        input_year = int(year_str)
        month = int(month_str)
        day = int(day_str)
        
        # 4. 驗證掛號目標日期 (檢查合法性，並限制僅能掛號今天起兩週內的門診)
        today = date.today()
        target_m = int(self.target_month_cb.get())
        target_d = int(self.target_day_cb.get())

        # 優先以今年計算
        target_year = today.year
        try:
            target_date = date(target_year, target_m, target_d)
        except ValueError:
            messagebox.showwarning("掛號日期不合法", f"所選的掛號日期不存在：{target_m} 月 {target_d} 日！")
            return False

        # 跨年處理：如果目標日期小於今天超過半年，合理推斷是要掛明年的門診
        if target_date < today and (today - target_date).days > 180:
            try:
                target_date = date(target_year + 1, target_m, target_d)
            except ValueError:
                messagebox.showwarning("掛號日期不合法", f"明年的掛號日期不存在：{target_m} 月 {target_d} 日！")
                return False

        # 計算日期差距
        days_diff = (target_date - today).days

        if days_diff < 0:
            messagebox.showwarning("日期錯誤", f"掛號日期 ({target_m}/{target_d}) 已經過去，無法預約！")
            return False
        elif days_diff > 14:
            max_date = today + timedelta(days=14)
            messagebox.showwarning(
                "超出預約範圍", 
                f"臺大醫院僅開放兩週內的門診預約！\n"
                f"目前僅開放至：{max_date.strftime('%Y/%m/%d')}\n"
                f"您選擇的日期差距為 {days_diff} 天。"
            )
            return False
        # weekday(): 0=週一, 1=週二, ..., 4=週五, 5=週六, 6=週日
        weekday_map = {5: "星期六", 6: "星期日"}
        if target_date.weekday() in weekday_map:
            messagebox.showwarning(
                "非門診日", 
                f"您所選的日期 ({target_date.strftime('%Y/%m/%d')}) 是 {weekday_map[target_date.weekday()]}，門診休診無看診！"
            )
            return False

        # --- 新增：檢查是否為國定假日 ---
        is_holiday = False
        holiday_name = ""
        if tw_holidays is not None:
            # 優先使用 holidays 套件精準判斷台灣假日
            if target_date in tw_holidays:
                is_holiday = True
                holiday_name = tw_holidays.get(target_date)
        else:
            # 若無安裝 holidays 套件，使用常規固定國定假日作為備案
            fixed_holidays = {
                (1, 1): "元旦",
                (2, 28): "和平紀念日",
                (4, 4): "兒童節",
                (4, 5): "清明節",
                (5, 1): "勞動節",
                (10, 10): "國慶日"
            }
            md = (target_date.month, target_date.day)
            if md in fixed_holidays:
                is_holiday = True
                holiday_name = fixed_holidays[md]

        if is_holiday:
            holiday_info = f" ({holiday_name})" if holiday_name else ""
            messagebox.showwarning(
                "非門診日", 
                f"您所選的日期 ({target_date.strftime('%Y/%m/%d')}) 為國定假日{holiday_info}，門診休診！"
            )
            return False
        # 驗證出生年月日
        if 1 <= input_year <= 150:
            ad_year = input_year + 1911  # 民國轉西元
            year_display = f"民國 {input_year} 年 (西元 {ad_year} 年)"
        elif 1900 <= input_year <= 2100:
            ad_year = input_year         # 直接為西元年
            year_display = f"西元 {input_year} 年"
        else:
            messagebox.showwarning("年份不合理", "請填寫合理的年份！\n民國年請填 1~150，西元年請填 1900 以上。")
            return False

        # 驗證真實日曆有效性 (包含大小月、閏年 2/29 檢查)
        try:
            birth_date = date(ad_year, month, day)
        except ValueError:
            messagebox.showwarning(
                "日期不合法", 
                f"您輸入的出生日期不存在！\n{year_display} 沒有 {month} 月 {day} 日。"
            )
            return False

        # 出生日期不能在今天之後
        if birth_date > date.today():
            messagebox.showwarning("日期不合理", "出生日期不能大於今天！")
            return False

        return True

    def save_config(self):
        # 儲存前先進行格式檢查，沒過就中斷
        if not self.validate_inputs():
            return False

        # 更新普通輸入框
        for key, entry in self.entries.items():
            if entry is None:
                continue
            if key == "target_doctors":
                self.config_data[key] = [d.strip() for d in entry.get().split(',') if d.strip()]
            elif key == "my_id":
                self.config_data[key] = entry.get().strip().upper()  # 自動轉大寫
            else:
                self.config_data[key] = entry.get().strip()

        # 組裝日期字串 (MM/DD)
        self.config_data["target_date"] = f"{self.target_month_cb.get()}/{self.target_day_cb.get()}"
        # 組裝時間字串 (hh:mm:ss)
        # 判斷是否為「立即執行」模式
        if self.immediate_var.get():
            self.config_data["target_time"] = ""
        else:
            self.config_data["target_time"] = f"{self.hour_cb.get()}:{self.min_cb.get()}:{self.sec_cb.get()}"
        self.config_data["automatic_confirm"] = str(self.auto_confirm_var.get())

        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config_data, f, ensure_ascii=False, indent=4)
            return True
        except Exception as e:
            messagebox.showerror("錯誤", f"儲存設定檔失敗: {e}")
            return False
    def run_program(self):
        # 當使用者按下「儲存並執行」時
        if self.save_config():
            self.run_btn.config(state=tk.DISABLED, bg="#9CA3AF")
            self.log_area.delete('1.0', tk.END)
            print("設定已儲存！開始連線至掛號系統...\n" + "="*40)
            
            thread = threading.Thread(target=self.execute_booking)
            thread.daemon = True 
            thread.start()
    def execute_booking(self):
        try:
            # 呼叫你原本的程式碼
            auto_appointment.auto_snipe_appointment()
            print("\n" + "="*50 + "\n[系統訊息] 任務執行完畢！")
        except Exception as e:
            print(f"\n[系統錯誤] {e}")
            self.root.after(0, lambda: messagebox.showerror("錯誤", f"掛號失敗: {e}"))
        finally:
            # 程式跑完後，將按鈕恢復正常狀態 (安全地更新 GUI)
            self.root.after(0, lambda: self.run_btn.config(state=tk.NORMAL, bg=self.btn_bg))
            self.root.after(0, lambda: self.confirm_btn.config(state=tk.DISABLED, bg="#9CA3AF"))
    def trigger_confirm(self):
        """點擊確認按鈕或在 GUI 視窗按下 Enter 時觸發"""
        if self.confirm_btn['state'] == tk.NORMAL:
            self.confirm_btn.config(state=tk.DISABLED, bg="#9CA3AF")
            auto_appointment.confirm_event.set()
class PrintLogger:
    def __init__(self, text_widget, app=None):
        self.text_widget = text_widget
        self.app = app

    def write(self, text):
        self.text_widget.insert(tk.END, text)
        self.text_widget.see(tk.END)
        
        # 當爬蟲提示等待確認時，透過主線程啟用 GUI 確認按鈕
        if "【GUI 等待確認】" in text and self.app:
            self.app.root.after(0, lambda: self.app.confirm_btn.config(state=tk.NORMAL, bg="#10B981"))

    def flush(self):
        pass
if __name__ == "__main__":
    root = tk.Tk()
    app = AppGUI(root)
    root.mainloop()