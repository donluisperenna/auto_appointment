import requests
import ntplib
import sys
import os
import json
import subprocess
import time
from time import ctime
from datetime import datetime, timedelta
from playwright._impl._driver import compute_driver_executable, get_driver_env
custom_browser_dir = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'ms-playwright')
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = custom_browser_dir
from playwright.sync_api import sync_playwright
import ddddocr
def get_config_path():
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, 'config.json')

def setup_playwright():
    print("正在檢查瀏覽器核心 (首次執行約需 1~2 分鐘下載，後續將秒開)...")
    try:
        from playwright._impl._driver import compute_driver_executable, get_driver_env
        driver_executable, driver_cli = compute_driver_executable()
        env = get_driver_env()
        env["PLAYWRIGHT_BROWSERS_PATH"] = custom_browser_dir
        subprocess.run(
            [driver_executable, driver_cli, "install", "chromium"],
            env=env,
            check=True,
            capture_output=True 
        )
    except Exception as e:
        print(f"⚠️ 瀏覽器下載程序異常，若後續正常彈出視窗則可忽略。錯誤細節: {e}")
def send_discord_notify(webhook_url, message):
    """發送 Discord Webhook 通知"""
    if not webhook_url:
        return  # 若沒有設定網址則直接跳過
        
    payload = {"content": message}
    try:
        # timeout 設短一點，避免發送通知卡住主程式
        requests.post(webhook_url, json=payload, timeout=5)
        print("🔔 已成功發送 Discord 通知！")
    except Exception as e:
        print(f"⚠️ Discord 通知發送失敗: {e}")
def get_ntp_offset():
    """與國家時間伺服器同步，取得本機與標準時間的秒數誤差"""
    # 台灣的國家時間與頻率標準實驗室 NTP 伺服器
    ntp_servers = ['time.stdtime.gov.tw', 'clock.stdtime.gov.tw', 'tw.pool.ntp.org']
    
    print("🔄正在與國家時間伺服器進行同步...")
    client = ntplib.NTPClient()
    
    for server in ntp_servers:
        try:
            # timeout 設為 2 秒，避免卡住
            response = client.request(server, version=3, timeout=2)
            offset = response.offset
            print(f"✅ 時間同步成功！({server})")
            print(f"   本機時間與標準時間誤差: {offset:.4f} 秒")
            return offset
        except Exception as e:
            print(f"⚠️ {server} 同步失敗 ({e})，嘗試下一個伺服器...")
            
    print("❌ 所有 NTP 伺服器同步失敗，將使用本機時間。")
    return 0.0
def wait_until_target(target_time_str):
    """具備 NTP 補償的精準倒數計時器"""
    # 1. 取得時間誤差
    time_offset = get_ntp_offset()
    
    # 2. 計算出「真正的現在時間」
    real_now = datetime.now() + timedelta(seconds=time_offset)
    
    try:
        target_time = datetime.strptime(target_time_str, "%H:%M:%S").replace(
            year=real_now.year, month=real_now.month, day=real_now.day
        )
    except ValueError:
        print("❌ 時間格式錯誤！請使用 HH:MM:SS 格式（如 18:00:00）")
        exit()

    if target_time < real_now:
        print("⏳ 提醒：輸入的時間今日已過，將設定為【明天】的此時刻啟動。")
        target_time += timedelta(days=1)

    print(f"⏳ 系統將在標準時間 {target_time.strftime('%Y-%m-%d %H:%M:%S')} 準時開搶...")
    
    while True:
        # 在迴圈內持續補償誤差
        real_now = datetime.now() + timedelta(seconds=time_offset)
        diff = (target_time - real_now).total_seconds()
        
        if diff <= 0.02:
            print(f"\n🚀 時間到！開始執行搶號 ({real_now.strftime('%H:%M:%S.%f')[:-3]})")
            break
        elif diff > 2:
            time.sleep(1)
            if diff < 60 and int(diff) % 10 == 0:
                print(f"倒數 {int(diff)} 秒...")
            elif diff>=60 and int(diff)//60//60 >= 1 and int(diff) % 60 == 0:
                print(f"倒數 {int(diff)//60//60}時{int(diff)//60%60}分...")
            elif diff>=60 and int(diff)//60//60 == 0 and int(diff) % 60 == 0:
                print(f"倒數 {int(diff)//60%60}分...")
        else:
            # 進入最後 2 秒，完全不使用 sleep，讓 CPU 全速輪詢 (Busy Wait)
            # 配合 NTP 誤差補償，精準度可達到幾毫秒之內
            pass

def intercept_route(route):
    resource_type = route.request.resource_type
    url = route.request.url
    
    if resource_type in ["stylesheet", "font", "media"]:
        route.abort()
    elif resource_type == "image":
        if "ValidNumerImage" in url:
            route.continue_()
        else:
            route.abort()
    else:
        route.continue_()

def auto_snipe_appointment():
    setup_playwright()
    ocr = ddddocr.DdddOcr(show_ad=False)
    config_file = get_config_path()
    
    if not os.path.exists(config_file):
        print(f"❌ 找不到設定檔：{config_file}")
        input("請按 Enter 鍵結束...")
        return

    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)

    target_dept = config.get("target_dept", "").strip()
    
    # 讀取醫生候補名單陣列，若只有單一醫師也能相容
    target_doctors = config.get("target_doctors", [])
    if not target_doctors and config.get("target_doctor"):
        target_doctors = [config.get("target_doctor").strip()]
    discord_webhook_url = config.get("discord_webhook_url", "").strip()
    target_date = config.get("target_date", "").strip()
    # 讀取撿漏模式的刷新間隔 
    snipe_interval = config.get("snipe_interval", 60)

    if not target_dept or not target_doctors:
        print("❌ 設定檔中「科別」或「醫師姓名陣列(target_doctors)」未填寫，程式結束。")
        return

    my_id = config.get("my_id", "").strip()
    my_year = config.get("my_year", "").strip()
    my_month = config.get("my_month", "").strip()
    my_day = config.get("my_day", "").strip()
    target_time_input = config.get("target_time", "").strip()
    automatic_confirm = config.get("automatic_confirm", "").strip()
    
    print(f"✅ 設定讀取成功：將預約 {target_dept}，候補醫師順序：{target_doctors}")
    print(f"✅ 撿漏刷新間隔設定為：{snipe_interval} 秒")
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
        page.route("**/*", intercept_route)
        print(f"正在前往台大醫院總覽頁面，尋找【{target_dept}】...")
        
        try:
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
            print(f"❌ 找不到您輸入的科別【{target_dept}】，請檢查名稱是否正確。")
            browser.close()
            return
            
        target_dept_url = f"https://reg.ntuh.gov.tw{dept_href}" if dept_href.startswith("/") else dept_href
        print(f"✅ 成功找到科別網址：{target_dept_url}")
        print("正在預先載入該科別排班頁面，準備暖機...")
        
        try:
            page.goto(target_dept_url, timeout=60000, wait_until="domcontentloaded")
        except:
            pass
            
        if target_date:
            print(f"正在檢查 {target_date} 是否有 {target_doctors} 醫師的門診...")
            check_js = """
            (params) => {
                let { target_date, target_doctors } = params;
                let buttons = document.querySelectorAll('button.doctor-tag');
                for (let btn of buttons) {
                    let nameDiv = btn.querySelector('.doc-name');
                    let nameText = nameDiv ? nameDiv.innerText : '';
                    let isTarget = target_doctors.some(doc => nameText.includes(doc));
                    if (!isTarget) continue;
                    
                    // 根據網頁結構，往上尋找該醫師隸屬的日期標題 (sm-table-header)
                    let rowElem = btn.closest('.row');
                    let prevElem = rowElem ? rowElem.previousElementSibling : null;
                    while (prevElem && !prevElem.classList.contains('sm-table-header')) {
                        prevElem = prevElem.previousElementSibling;
                    }
                    
                    if (prevElem && prevElem.innerText.includes(target_date)) {
                        return true; // 找到了，該日期確實有該醫師的診
                    }
                }
                return false; // 找不到
            }
            """
            has_clinic = page.evaluate(check_js, {"target_date": target_date, "target_doctors": target_doctors})
            if not has_clinic:
                print(f"❌ 錯誤：在網頁上找不到【{target_date}】包含【{target_doctors}】的門診，請確認日期格式或班表是否正確！")
                browser.close()
                return
            print(f"✅ 檢查通過：{target_date} 有目標醫師的門診，準備進入搶號狀態！")
        if target_time_input:
            wait_until_target(target_time_input)
        attempt_count = 1
        found_url = None
        
        while True:
            print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] 執行第 {attempt_count} 次掃描...")
            
            try:
                if attempt_count == 1 and target_time_input:
                    page.reload(timeout=15000, wait_until="domcontentloaded")
                page.wait_for_selector(".doctor-tag", timeout=10000)
            except Exception as e:
                print(f"⚠️ 伺服器塞車，立即重試... ({e})")
                page.reload(timeout=15000, wait_until="domcontentloaded")
                attempt_count += 1
                continue
            
            js_code = """
            (params) => {
                let { target_doctors, target_date } = params;
                let buttons = document.querySelectorAll('button.doctor-tag');
                
                for (let target_doctor of target_doctors) {
                    for (let btn of buttons) {
                        let text = btn.innerText;
                        let nameDiv = btn.querySelector('.doc-name');
                        let nameText = nameDiv ? nameDiv.innerText : '';
                        
                        // 1. 確認醫師名稱
                        if (!nameText.includes(target_doctor)) continue;
                        
                        // 2. [新增] 確認日期是否符合
                        if (target_date) {
                            let rowElem = btn.closest('.row');
                            let prevElem = rowElem ? rowElem.previousElementSibling : null;
                            while (prevElem && !prevElem.classList.contains('sm-table-header')) {
                                prevElem = prevElem.previousElementSibling;
                            }
                            // 如果沒找到日期標題，或是標題不包含指定日期，就跳過這個按鈕
                            if (!prevElem || !prevElem.innerText.includes(target_date)) {
                                continue;
                            }
                        }
                        
                        // 3. 過濾無法掛號狀態
                        if (text.includes('不續掛') || text.includes('停診')) continue;
                        if (text.includes('額滿') || text.includes('僅存本院初診')) continue;
                        
                        // 4. 解析網址並立刻回傳
                        let onclickAttr = btn.getAttribute('onclick');
                        if (onclickAttr) {
                            let match = onclickAttr.match(/window\\.location\\.href\\s*=\\s*'([^']+)'/);
                            if (match && match[1]) {
                                return {
                                    href: match[1],
                                    doctor: target_doctor
                                };
                            }
                        }
                    }
                }
                return null;
            }
            """
            
            # [修改] 將參數打包成字典傳給 JavaScript
            result = page.evaluate(js_code, {"target_doctors": target_doctors, "target_date": target_date})
            
            if result:
                found_url = f"https://reg.ntuh.gov.tw/WebReg/WebReg/{result['href']}"
                matched_doctor = result['doctor'] # [新增] 紀錄實際掛到的醫師名字，方便後續通知使用
                print(f"\n🎉 恭喜！找到【{matched_doctor}】醫師的名額，極速跳轉中...")
                break
            else:
                print(f"❌ 所有候補醫師皆無名額，{snipe_interval} 秒後重新整理 (撿漏模式)...\n")
                # 【修改點】：使用設定檔中的秒數進行等待，避免請求過快被封鎖
                time.sleep(snipe_interval) 
                attempt_count += 1
                try:
                    page.reload(timeout=15000, wait_until="domcontentloaded")
                except:
                    pass

        print("\a\a\a")
        
        try:
            page.route("**/*", intercept_route)
            page.goto(found_url, wait_until='commit')
            
            try:
                max_retry = 2
                retry_count = 0
                while retry_count < max_retry:
                    retry_count += 1
                    page.wait_for_selector('#option-1', timeout=5000)
                    
                    js_fill_code = f"""
                        let option1 = document.getElementById('option-1');
                        if (option1) {{
                            option1.checked = true;
                            option1.dispatchEvent(new Event('change', {{ bubbles: true }}));
                            if (typeof changeInputType === 'function') {{
                                changeInputType('personID');
                            }}
                        }}
                        function fastFill(id, value) {{
                            let el = document.getElementById(id);
                            if (el) {{
                                el.value = value;
                                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                            }}
                        }}
                        fastFill('txtInputID', '{my_id}'); 
                        fastFill('year', '{my_year}');               
                        fastFill('month', '{my_month}');               
                        fastFill('day', '{my_day}');                
                    """
                    page.evaluate(js_fill_code)
                    
                    captcha_img_locator = page.locator('img[src^="ValidNumerImage"]')
                    captcha_img_locator.wait_for(state='visible')
                    
                    image_bytes = captcha_img_locator.screenshot()
                    captcha_text = ocr.classification(image_bytes)
                    print(f"第 {retry_count} 次嘗試 - ddddocr 辨識出: {captcha_text}")
                    
                    page.locator('#validText').fill(captcha_text)
                    
                    if automatic_confirm == 'True':
                        page.locator('#patientIdentityConfirm').click()
                        print("自動確認掛號，掛號完成！")
                    else:
                        print("\n按下 Enter 鍵來確認掛號")
                        input("\n✅ 【資料填妥後，請直接在按下 Enter 鍵】，程式將瞬間為您送出表單...")
                        page.locator('#patientIdentityConfirm').click()
                        
                    if page.locator('img[src^="ValidNumerImage"]').is_visible():
                        print("❌ 驗證碼錯誤或資料有誤，跳回原畫面，立刻重新嘗試...\n")
                        continue  
                    else:
                        print("✅ 驗證碼正確，成功進入下一頁！")
                        success_msg = f"🎉 **掛號成功通知** 🎉\n您已成功預約 **{target_dept}** 的 **{matched_doctor}** 醫師！\n請盡快登入醫院系統確認詳細診號與時間。"
                        send_discord_notify(discord_webhook_url, success_msg)
                        break  
                
                page.wait_for_timeout(50000) 
            except Exception as e:
                print(f"發生錯誤: {e}")
        except Exception as e:
            print(f"跳轉失敗，請手動點擊連結: {found_url}")
            input("\n按下 Enter 鍵結束程式...")
            
        browser.close()

if __name__ == "__main__":
    auto_snipe_appointment()