import re
import os
import json
import subprocess
import time
from datetime import datetime, timedelta
from playwright._impl._driver import compute_driver_executable, get_driver_env
custom_browser_dir = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'ms-playwright')
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = custom_browser_dir
from playwright.sync_api import sync_playwright
import ddddocr
from PIL import Image
def setup_playwright():
    """使用內建驅動程式自動下載 Chromium，並存放在固定路徑"""
    print("正在檢查瀏覽器核心 (首次執行約需 1~2 分鐘下載，後續將秒開)...")
    try:
        from playwright._impl._driver import compute_driver_executable, get_driver_env
        driver_executable, driver_cli = compute_driver_executable()
        
        # 取得 Playwright 的預設環境變數，並確保包含我們自訂的路徑
        env = get_driver_env()
        env["PLAYWRIGHT_BROWSERS_PATH"] = custom_browser_dir
        
        # 隱藏終端機輸出，強制靜默下載，避免與 CMD 畫面衝突
        subprocess.run(
            [driver_executable, driver_cli, "install", "chromium"],
            env=env,
            check=True,
            capture_output=True 
        )
    except Exception as e:
        print(f"⚠️ 瀏覽器下載程序異常，若後續正常彈出視窗則可忽略。錯誤細節: {e}")

def wait_until_target(target_time_str):
    """精準倒數計時器"""
    now = datetime.now()
    try:
        # 將輸入的時間字串轉換為今天的日期+目標時間
        target_time = datetime.strptime(target_time_str, "%H:%M:%S").replace(
            year=now.year, month=now.month, day=now.day
        )
    except ValueError:
        print("❌ 時間格式錯誤！請重新執行並使用 HH:MM:SS 格式（如 18:00:00）")
        exit()

    # 如果輸入的時間已經過了，自動設定為明天的這個時間
    if target_time < now:
        print("⏳ 提醒：輸入的時間今日已過，將設定為【明天】的此時刻啟動。")
        target_time += timedelta(days=1)

    print(f"⏳ 系統將在 {target_time.strftime('%Y-%m-%d %H:%M:%S')} 準時開搶...")
    
    while True:
        now = datetime.now()
        diff = (target_time - now).total_seconds()
        
        if diff <= 0:
            print(f"\n🚀 時間到！開始執行搶號 ({now.strftime('%H:%M:%S.%f')[:-3]})")
            break
        elif diff > 2:
            # 距離大於 2 秒時，每秒檢查一次，不佔用 CPU 資源
            time.sleep(1)
            # 每 10 秒印出一次進度，讓你知道程式還活著
            if int(diff) % 10 == 0:
                print(f"倒數 {int(diff)} 秒...")
        else:
            # [關鍵] 距離小於 2 秒時，進入「忙碌等待 (Busy Wait)」
            # 不使用 sleep，讓 CPU 全速輪詢，達到毫秒級的觸發精準度
            pass
def intercept_route(route):
    # 攔截圖片(但放行驗證碼)、CSS、字體等不需要的資源
    resource_type = route.request.resource_type
    url = route.request.url
    
    if resource_type in ["stylesheet", "font", "media"]:
        route.abort()
    elif resource_type == "image":
        # 注意：千萬不能擋掉驗證碼圖片！
        if "ValidNumerImage" in url:
            route.continue_()
        else:
            route.abort()
    else:
        route.continue_()
def auto_snipe_appointment():
    setup_playwright()
    ocr = ddddocr.DdddOcr(show_ad=False)
    config_file = 'config.json'
    
    # 檢查設定檔是否存在
    if not os.path.exists(config_file):
        print(f"❌ 找不到 {config_file} 檔案，請先建立該檔案。")
        return

    # 讀取 JSON 設定檔 (加入 encoding="utf-8" 避免中文亂碼)
    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)

    # 取得設定值，並使用 .get() 避免欄位遺失導致程式崩潰
    target_dept = config.get("target_dept", "").strip()
    target_doctor = config.get("target_doctor", "").strip()

    if not target_dept or not target_doctor:
        print("❌ 設定檔中「科別」或「醫師姓名」未填寫，程式結束。")
        return

    my_id = config.get("my_id", "").strip()
    my_year = config.get("my_year", "").strip()
    my_month = config.get("my_month", "").strip()
    my_day = config.get("my_day", "").strip()
    target_time_input = config.get("target_time", "").strip()
    automatic_confirm = config.get("automatic_confirm", "").strip()
    
    print(f"✅ 設定讀取成功：將預約 {target_dept} {target_doctor} 醫師")
    url = "https://reg.ntuh.gov.tw/WebReg/WebReg/RegShowBlock?vHospCode=T0"

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=[
                "--disable-animations",
                "--disable-smooth-scrolling",
                "--disable-blink-features=AutomationControlled",
            ]
        )
        page = browser.new_page()
        
        # [加速技巧 2] 更激進的資源阻擋 (連媒體檔一起擋)
        page.route("**/*", intercept_route)
        print(f"正在前往台大醫院總覽頁面，尋找【{target_dept}】...")
        
        try:
            # 步驟 A：先到總覽頁面找出該科別的網址
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_selector(".dep-name-border", timeout=15000)
        except Exception as e:
            print(f"❌ 載入總覽頁面失敗: {e}")
            browser.close()
            return
        find_dept_js = """
        (targetDept) => {
            let deptDivs = document.querySelectorAll('.dep-name-border');
            for (let div of deptDivs) {
                if (div.innerText.trim().includes(targetDept)) {
                    let aTag = div.closest('a');
                    if (aTag) {
                        return aTag.getAttribute('href');
                    }
                }
            }
            return null;
        }
        """
        
        dept_href = page.evaluate(find_dept_js, target_dept)
        
        if not dept_href:
            print(f"❌ 找不到您輸入的科別【{target_dept}】，請檢查名稱是否正確（例如是否包含『部』字）。")
            browser.close()
            return
        target_dept_url = f"https://reg.ntuh.gov.tw{dept_href}" if dept_href.startswith("/") else dept_href
        print(f"✅ 成功找到科別網址：{target_dept_url}")
        
        # 步驟 B：跳轉到該科別的排班頁面進行暖機
        print("正在預先載入該科別排班頁面，準備暖機...")
        try:
            page.goto(target_dept_url, timeout=60000, wait_until="domcontentloaded")
        except:
            pass
            
        if target_time_input:
            wait_until_target(target_time_input)
        
        attempt_count = 1
        found_url = None
        
        # 開搶核心迴圈
        while True:
            print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] 執行第 {attempt_count} 次掃描...")
            
            try:
                if attempt_count == 1 and target_time_input:
                    page.reload(timeout=15000, wait_until="domcontentloaded")
                
                # 等待目標出現 (這是必須的，確保 DOM 載入)
                page.wait_for_selector(".doctor-tag", timeout=10000)
            except Exception as e:
                print(f"⚠️ 伺服器塞車，立即重試... ({e})")
                page.reload(timeout=15000, wait_until="domcontentloaded")
                attempt_count += 1
                continue
            
            # ==========================================
            # [加速技巧 3] 將 Python 迴圈改為 JavaScript 內部執行
            # 這能消除 Python 與 Browser 之間幾十次的 WebSocket 傳輸延遲，瞬間完成判斷
            # ==========================================
            js_code = """
            (target_doctor) => {
                let buttons = document.querySelectorAll('button.doctor-tag');
                for (let btn of buttons) {
                    let text = btn.innerText;
                    
                    // 1. 確認醫師名稱
                    let nameDiv = btn.querySelector('.doc-name');
                    let nameText = nameDiv ? nameDiv.innerText : '';
                    if (!nameText.includes(target_doctor)) continue;
                    
                    // 2. 過濾無法掛號狀態
                    if (text.includes('不續掛') || text.includes('停診')) continue;
                    if (text.includes('額滿') || text.includes('僅存本院初診')) continue;
                    
                    // 3. 解析 onclick 網址
                    let onclickAttr = btn.getAttribute('onclick');
                    if (onclickAttr) {
                        let match = onclickAttr.match(/window\\.location\\.href\\s*=\\s*'([^']+)'/);
                        if (match && match[1]) {
                            return match[1]; // 直接回傳相對路徑
                        }
                    }
                }
                return null; // 沒找到回傳 null
            }
            """
            
            # 呼叫 evaluate，將 JavaScript 丟進瀏覽器執行，毫秒級返回結果
            href_result = page.evaluate(js_code, target_doctor)
            
            if href_result:
                found_url = f"https://reg.ntuh.gov.tw/WebReg/WebReg/{href_result}"
                break
            else:
                print(f"❌ 尚未釋出名額，2 秒後重新整理...\n")
                time.sleep(2) 
                attempt_count += 1
                try:
                    page.reload(timeout=15000, wait_until="domcontentloaded")
                except:
                    pass

        # ================= 成功抓到名額後的極速跳轉 =================
        print("\a\a\a")
        print(f"\n🎉 恭喜！找到名額，極速跳轉中...")
        # 解除攔截器
        #page.unroute("**/*", route_interceptor)
        try:
            page.route("**/*", intercept_route)
            page.goto(found_url, wait_until='commit')
            #input("\n👉 已進入掛號頁面！請盡快在瀏覽器上完成掛號。\n完成後，請在此終端機按下 Enter 鍵結束程式並關閉瀏覽器...")
            try:
                # 2. 等待「證件號碼」輸入框載入完成
                # --- 實務重要提醒 ---
                # 台大醫院掛號通常會有「圖形驗證碼」需要輸入。
                # 程式自動填寫完上述資料後，可以讓程式暫停，讓你手動輸入驗證碼並點擊送出。
                # 可以使用 page.pause() 開啟 Playwright 偵錯工具，或是用 wait_for_timeout 爭取手動時間。
                # 等待 30 秒，讓你有時間手動輸入驗證碼並看結果
                 # 定位驗證碼圖片 
                max_retry = 2
                retry_count = 0
                while retry_count < max_retry:
                    retry_count += 1
                    # ⚠️ 重要提醒：如果網頁跳回原頁面會「清空」你的身分證或生日等欄位，
                    # 請務必把「填寫基本資料 (身分證、生日)」的程式碼也搬進這個迴圈裡執行！
                    # 例如：
                    # page.locator('#my_id_input').fill(my_id)
                    page.wait_for_selector('#option-1', timeout=5000)
                    # (選擇性) 確保「身分證字號」的單選按鈕有被選取
                    '''page.locator('#option-1').check()
                    # 3. 輸入證件號碼 (對應 id="txtInputID")
                    # 替換成你的身分證字號
                    page.locator('#txtInputID').fill('A123456789') 
                    # 4. 輸入出生日期 (對應 id="year", "month", "day")
                    # 替換成你的出生年月日 (例如民國 69 年 1 月 15 日)
                    page.locator('#year').fill('69')
                    page.locator('#month').fill('1')
                    page.locator('#day').fill('15')'''
                    # 極速寫法 (打包成 JS 一次讓瀏覽器瞬間執行)
                    js_fill_code = f"""
                        // 處理單選按鈕
                        let option1 = document.getElementById('option-1');
                        if (option1) {{
                            option1.checked = true;
                            option1.dispatchEvent(new Event('change', {{ bubbles: true }}));
                            
                            if (typeof changeInputType === 'function') {{
                                changeInputType('personID');
                            }}
                        }}
    
                        // 定義極速填表函數
                        function fastFill(id, value) {{
                            let el = document.getElementById(id);
                            if (el) {{
                                el.value = value;
                                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                            }}
                        }}
                        
                        // 動態帶入使用者輸入的變數
                        fastFill('txtInputID', '{my_id}'); 
                        fastFill('year', '{my_year}');               
                        fastFill('month', '{my_month}');               
                        fastFill('day', '{my_day}');                
                    """
                    # 執行注入
                    page.evaluate(js_fill_code)
                    # 1. 定位驗證碼與辨識
                    captcha_img_locator = page.locator('img[src^="ValidNumerImage"]')
                    captcha_img_locator.wait_for(state='visible')
                    
                    image_bytes = captcha_img_locator.screenshot()
                    captcha_text = ocr.classification(image_bytes)
                    print(f"第 {retry_count} 次嘗試 - ddddocr 辨識出: {captcha_text}")
                    
                    page.locator('#validText').fill(captcha_text)
                    # 2. 點擊確定送出並等待網頁反應
                    if automatic_confirm == 'True':
                        page.locator('#patientIdentityConfirm').click()
                        print("自動確認掛號，掛號完成！")
                    else:
                        print("\n按下 Enter 鍵來確認掛號")
                        input("\n✅ 【資料填妥後，請直接在此終端機按下 Enter 鍵】，程式將瞬間為您送出表單...")
                        page.locator('#patientIdentityConfirm').click()
                    # 3. 驗證是否成功進入下一頁
                    # 檢查網頁上是否還能看到驗證碼圖片。如果還在，代表失敗了被退回原網頁
                    if page.locator('img[src^="ValidNumerImage"]').is_visible():
                        print("❌ 驗證碼錯誤或資料有誤，跳回原畫面，立刻重新嘗試...\n")
                        continue  # 回到 while 迴圈開頭，重新辨識
                    else:
                        print("✅ 驗證碼正確，成功進入下一頁！")
                        break  # 離開迴圈，繼續執行後續搶號邏輯
                # 5. 點選「確定送出」
                # 這裡依然假設按鈕文字包含"確定送出"，
                # 如果你有送出按鈕的 HTML，也可以改成用 id 定位 (例如 page.locator('#btnSubmit').click())
                
                page.wait_for_timeout(50000) 
            except Exception as e:
                print(f"發生錯誤: {e}")
        except Exception as e:
            print(f"跳轉失敗，請手動點擊連結: {found_url}")
            input("\n按下 Enter 鍵結束程式...")
            
        browser.close()

if __name__ == "__main__":
    auto_snipe_appointment()