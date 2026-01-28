#!/usr/bin/env python3
"""
Leaflow 多账号自动签到脚本 - 完整可运行版
功能：
1. 多账号登录和签到
2. 超时和页面加载失败重试
3. 获取余额
4. Telegram 通知
"""

import os
import time
import logging
import re
import random
from datetime import datetime
from typing import Optional, Tuple, List, Dict
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, WebDriverException

# -------------------- 日志配置 --------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# -------------------- 常量配置 --------------------
BASE_URL = "https://leaflow.net"
CHECKIN_URLS = [
    "https://checkin.leaflow.net",
    "https://leaflow.net/checkin",
    "https://app.leaflow.net/checkin",
    f"{BASE_URL}/daily-checkin",
    f"{BASE_URL}/checkin/daily"
]
DASHBOARD_URL = f"{BASE_URL}/dashboard"
LOGIN_URL = f"{BASE_URL}/login"

# -------------------- Chrome 驱动管理 --------------------
class DriverManager:
    """Chrome驱动管理器"""
    @staticmethod
    def create_driver(headless: bool = False) -> webdriver.Chrome:
        chrome_options = Options()
        # Headless模式
        if headless or os.getenv('GITHUB_ACTIONS'):
            chrome_options.add_argument('--headless=new')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')

        # 反检测
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        # 性能优化 - 不加载图片
        prefs = {'profile.default_content_setting_values': {'images': 2}}
        chrome_options.add_experimental_option('prefs', prefs)

        try:
            driver = webdriver.Chrome(options=chrome_options)
        except Exception as e:
            logger.error(f"创建驱动失败: {e}")
            raise

        driver.set_page_load_timeout(90)
        driver.set_script_timeout(45)
        driver.implicitly_wait(10)

        # 隐藏自动化特征
        try:
            driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': '''
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                    window.chrome = {runtime:{}};
                '''
            })
        except:
            pass

        return driver

# -------------------- 页面加载辅助 --------------------
class PageLoadHelper:
    """页面加载辅助工具"""
    @staticmethod
    def wait_for_page_loaded(driver: webdriver.Chrome, timeout: int = 90) -> bool:
        try:
            WebDriverWait(driver, timeout).until(
                lambda d: d.execute_script('return document.readyState') == 'complete'
            )
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(2)
            return True
        except TimeoutException:
            logger.warning("页面加载超时")
            return False
        except:
            return False

    @staticmethod
    def retry_page_load(driver: webdriver.Chrome, url: str, max_retries: int = 3) -> bool:
        for retry in range(max_retries):
            try:
                driver.execute_script(f"window.location.href = '{url}';")
                if PageLoadHelper.wait_for_page_loaded(driver, 60):
                    return True
                time.sleep(random.uniform(3, 8))
            except:
                time.sleep(5)
        return False

# -------------------- Leaflow自动签到 --------------------
class LeaflowAutoCheckin:
    """单账号签到"""
    def __init__(self, email: str, password: str):
        self.email = email
        self.password = password
        self.driver: Optional[webdriver.Chrome] = None
        self.is_headless = bool(os.getenv('GITHUB_ACTIONS'))
        self.max_retries = 3

    def __enter__(self):
        self.driver = DriverManager.create_driver(self.is_headless)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.driver:
            self.driver.quit()
            self.driver = None

    # -------------------- 登录 --------------------
    def login(self) -> bool:
        logger.info(f"开始登录账号: {self.email[:3]}***")
        for retry in range(self.max_retries):
            try:
                self.driver.get(LOGIN_URL)
                PageLoadHelper.wait_for_page_loaded(self.driver, 60)

                # 输入邮箱和密码
                email_input = self._find_input(["input[type='email']", "input[name='email']"])
                password_input = self._find_input(["input[type='password']", "input[name='password']"])
                login_button = self._find_clickable(["button[type='submit']", "//button[contains(text(),'登录')]"])

                if not (email_input and password_input and login_button):
                    logger.warning("未找到登录表单元素")
                    continue

                email_input.clear()
                email_input.send_keys(self.email)
                password_input.clear()
                password_input.send_keys(self.password)
                self._safe_click_element(login_button)
                time.sleep(5)

                if self._verify_login_success():
                    return True
            except Exception as e:
                logger.error(f"登录错误: {e}")
                time.sleep(random.uniform(5, 10))
        return False

    def _find_input(self, selectors: List[str]):
        for sel in selectors:
            try:
                if sel.startswith("//"):
                    element = self.driver.find_element(By.XPATH, sel)
                else:
                    element = self.driver.find_element(By.CSS_SELECTOR, sel)
                if element.is_displayed():
                    return element
            except:
                continue
        return None

    def _find_clickable(self, selectors: List[str]):
        for sel in selectors:
            try:
                if sel.startswith("//"):
                    element = WebDriverWait(self.driver, 8).until(
                        EC.element_to_be_clickable((By.XPATH, sel))
                    )
                else:
                    element = WebDriverWait(self.driver, 8).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, sel))
                    )
                if element.is_displayed() and element.is_enabled():
                    return element
            except:
                continue
        return None

    def _safe_click_element(self, element):
        try:
            self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
            self.driver.execute_script("arguments[0].click();", element)
            time.sleep(1)
            return True
        except:
            try:
                element.click()
                time.sleep(1)
                return True
            except:
                return False

    def _verify_login_success(self, timeout: int = 20):
        start_time = time.time()
        while time.time() - start_time < timeout:
            url = self.driver.current_url.lower()
            if "login" not in url:
                return True
            time.sleep(2)
        return False

    # -------------------- 签到 --------------------
    def checkin(self) -> Tuple[bool, str]:
        logger.info("开始签到流程")
        for retry in range(self.max_retries):
            if self.navigate_to_checkin_page():
                if self._check_already_checked_in():
                    return True, "今日已签到"
                if self._perform_checkin_operation():
                    return True, self._get_checkin_result()
            time.sleep(random.uniform(5, 10))
        return False, "签到失败"

    def navigate_to_checkin_page(self) -> bool:
        try:
            self.driver.get(DASHBOARD_URL)
            PageLoadHelper.wait_for_page_loaded(self.driver, 30)
            for link in ["//a[contains(@href,'checkin')]", "//button[contains(text(),'签到')]"]:
                elements = self.driver.find_elements(By.XPATH, link)
                for el in elements:
                    if el.is_displayed():
                        self._safe_click_element(el)
                        time.sleep(5)
                        if "checkin" in self.driver.current_url:
                            return True
        except:
            pass
        # 尝试直接访问签到URL
        return PageLoadHelper.retry_page_load(self.driver, CHECKIN_URLS[0])

    def _check_already_checked_in(self):
        try:
            for sel in ["//button[contains(text(),'已签到')]", ".checked-in", "button[disabled]"]:
                elements = self.driver.find_elements(By.XPATH if sel.startswith("//") else By.CSS_SELECTOR, sel)
                for e in elements:
                    if e.is_displayed():
                        return True
        except:
            pass
        return False

    def _perform_checkin_operation(self):
        try:
            for sel in ["//button[contains(text(),'立即签到')]", ".checkin-btn"]:
                element = self._find_clickable([sel])
                if element:
                    return self._safe_click_element(element)
        except:
            pass
        return False

    def _get_checkin_result(self):
        try:
            body = self.driver.find_element(By.TAG_NAME, "body").text
            for line in body.splitlines():
                if "成功" in line or "领取" in line:
                    return line.strip()
        except:
            pass
        return "签到完成"

    # -------------------- 获取余额 --------------------
    def get_balance(self) -> str:
        try:
            self.driver.get(DASHBOARD_URL)
            PageLoadHelper.wait_for_page_loaded(self.driver, 30)
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            matches = re.findall(r'[¥￥](\d+\.?\d*)', body_text)
            if matches:
                return f"{max(float(m) for m in matches)}元"
        except:
            pass
        return "未知"

    # -------------------- 运行单账号 --------------------
    def run(self) -> Tuple[bool, str, str]:
        with self:
            if not self.login():
                return False, "登录失败", "未知"
            success, result = self.checkin()
            balance = self.get_balance() if success else "未知"
            return success, result, balance

# -------------------- 多账号管理 --------------------
class MultiAccountManager:
    def __init__(self):
        self.telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
        self.accounts = self.load_accounts()

    def load_accounts(self) -> List[Dict[str, str]]:
        accounts = []
        accounts_str = os.getenv('LEAFLOW_ACCOUNTS', '').strip()
        if accounts_str:
            for i, pair in enumerate(accounts_str.split(','), 1):
                if ':' in pair:
                    email, password = pair.split(':', 1)
                    accounts.append({'email': email.strip(), 'password': password.strip(), 'index': i})
        else:
            email = os.getenv('LEAFLOW_EMAIL', '').strip()
            password = os.getenv('LEAFLOW_PASSWORD', '').strip()
            if email and password:
                accounts.append({'email': email, 'password': password, 'index': 1})
        if not accounts:
            raise ValueError("未找到有效账号配置")
        logger.info(f"共加载 {len(accounts)} 个账号")
        return accounts

    def send_notification(self, results: List[Tuple[str, bool, str, str]]):
        if not self.telegram_bot_token or not self.telegram_chat_id:
            return
        try:
            message = "🎁 <b>Leaflow自动签到通知</b>\n"
            message += f"📅 执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            message += "="*30 + "\n"
            for email, success, result, balance in results:
                masked = email[:3] + "***" + email[email.find("@"):]
                status = "✅" if success else "❌"
                message += f"<b>{masked}</b>\n{status} {result}\n💰 余额: {balance}\n\n"
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
            requests.post(url, json={"chat_id": self.telegram_chat_id, "text": message, "parse_mode": "HTML"}, timeout=15)
        except Exception as e:
            logger.error(f"Telegram通知发送失败: {e}")

    def run_all(self) -> Tuple[bool, List[Tuple[str, bool, str, str]]]:
        results = []
        all_success = True
        for account in self.accounts:
            email = account['email']
            password = account['password']
            try:
                checker = LeaflowAutoCheckin(email, password)
                success, result, balance = checker.run()
                results.append((email, success, result, balance))
                if not success:
                    all_success = False
            except Exception as e:
                logger.error(f"{email}处理异常: {e}")
                results.append((email, False, f"异常: {e}", "未知"))
                all_success = False
        self.send_notification(results)
        return all_success, results

# -------------------- 主程序入口 --------------------
if __name__ == "__main__":
    manager = MultiAccountManager()
    success, all_results = manager.run_all()

    logger.info("========== 所有账号处理完成 ==========")
    for email, success, result, balance in all_results:
        status = "成功" if success else "失败"
        logger.info(f"{email}: {status}, {result}, 余额: {balance}")
