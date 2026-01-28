#!/usr/bin/env python3
"""
Leaflow 多账号自动签到脚本 - 基础稳定版
环境变量：
LEAFLOW_ACCOUNTS: 邮箱1:密码1,邮箱2:密码2
TELEGRAM_BOT_TOKEN: Telegram bot token
TELEGRAM_CHAT_ID: Telegram chat ID
LEAFLOW_WAIT_TIME: 账号间等待时间(秒)，默认5
"""

import os
import time
import logging
import re
from datetime import datetime
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains

# 日志配置
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

WAIT_TIME_BETWEEN_ACCOUNTS = int(os.getenv("LEAFLOW_WAIT_TIME", 5))

class LeaflowAutoCheckin:
    def __init__(self, email, password):
        self.email = email
        self.password = password
        self.driver = None
        self.setup_driver()

    def setup_driver(self):
        chrome_options = Options()
        if os.getenv('GITHUB_ACTIONS'):
            chrome_options.add_argument("--headless=new")
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    def close_popup(self):
        try:
            actions = ActionChains(self.driver)
            actions.move_by_offset(10, 10).click().perform()
        except:
            pass

    def wait_for_element(self, by, selector, timeout=10):
        try:
            return WebDriverWait(self.driver, timeout).until(EC.presence_of_element_located((by, selector)))
        except:
            return None

    def login(self):
        self.driver.get("https://leaflow.net/login")
        time.sleep(3)
        self.close_popup()

        # 邮箱输入框
        email_selectors = [
            "input[type='text']",
            "input[type='email']",
            "input[name='email']",
            "input[placeholder*='邮箱']",
            "input[placeholder*='email']"
        ]
        email_input = None
        for sel in email_selectors:
            email_input = self.wait_for_element(By.CSS_SELECTOR, sel, 5)
            if email_input:
                break
        if not email_input:
            raise Exception(f"找不到邮箱输入框, 当前URL: {self.driver.current_url}")
        email_input.clear()
        email_input.send_keys(self.email)

        # 密码输入框
        password_input = self.wait_for_element(By.CSS_SELECTOR, "input[type='password']", 10)
        if not password_input:
            raise Exception(f"找不到密码输入框, 当前URL: {self.driver.current_url}")
        password_input.clear()
        password_input.send_keys(self.password)

        # 登录按钮
        login_btn_selectors = ["button[type='submit']", "//button[contains(text(),'登录')]"]
        login_btn = None
        for sel in login_btn_selectors:
            try:
                if sel.startswith("//"):
                    login_btn = WebDriverWait(self.driver, 5).until(EC.element_to_be_clickable((By.XPATH, sel)))
                else:
                    login_btn = WebDriverWait(self.driver, 5).until(EC.element_to_be_clickable((By.CSS_SELECTOR, sel)))
                if login_btn:
                    break
            except:
                continue
        if not login_btn:
            raise Exception("找不到登录按钮")
        login_btn.click()

        # 等待跳转
        WebDriverWait(self.driver, 15).until(lambda d: "dashboard" in d.current_url or "login" not in d.current_url)
        logger.info(f"{self.email} 登录成功，当前URL: {self.driver.current_url}")

    def checkin(self):
        self.driver.get("https://checkin.leaflow.net")
        time.sleep(3)
        checkin_btn_selectors = [
            "button.checkin-btn",
            "//button[contains(text(),'立即签到')]"
        ]
        for sel in checkin_btn_selectors:
            try:
                if sel.startswith("//"):
                    btn = WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.XPATH, sel)))
                else:
                    btn = WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, sel)))
                if btn and btn.is_displayed():
                    if "已签到" in btn.text:
                        return "今日已签到"
                    btn.click()
                    time.sleep(2)
                    return "签到完成"
            except:
                continue
        return "未找到签到按钮"

    def get_balance(self):
        self.driver.get("https://leaflow.net/dashboard")
        time.sleep(2)
        body_text = self.driver.find_element(By.TAG_NAME, "body").text
        m = re.search(r"¥?\d+\.?\d*", body_text)
        return m.group(0) if m else "未知"

    def run(self):
        try:
            self.login()
            checkin_result = self.checkin()
            balance = self.get_balance()
            logger.info(f"{self.email} 签到结果: {checkin_result}, 余额: {balance}")
            return True, checkin_result, balance
        except Exception as e:
            logger.error(f"{self.email} 自动签到失败: {e}")
            return False, str(e), "未知"
        finally:
            if self.driver:
                self.driver.quit()

class MultiAccountManager:
    def __init__(self):
        self.accounts = self.load_accounts()
        self.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "")

    def load_accounts(self):
        accounts = []
        accounts_str = os.getenv("LEAFLOW_ACCOUNTS", "").strip()
        if accounts_str:
            for pair in accounts_str.split(","):
                if ":" in pair:
                    email, password = pair.split(":", 1)
                    accounts.append({"email": email.strip(), "password": password.strip()})
        if not accounts:
            raise ValueError("未找到有效账号配置")
        logger.info(f"加载 {len(accounts)} 个账号")
        return accounts

    def send_telegram(self, results):
        if not self.telegram_bot_token or not self.telegram_chat_id:
            return
        message = "Leaflow自动签到结果:\n\n"
        for email, success, result, balance in results:
            masked = email[:3]+"***"+email[email.find("@"):]
            status = "✅" if success else "❌"
            message += f"{masked} {status} {result}, 余额: {balance}\n"
        try:
            requests.post(
                f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage",
                data={"chat_id": self.telegram_chat_id, "text": message, "parse_mode":"HTML"},
                timeout=10
            )
        except Exception as e:
            logger.error(f"发送Telegram失败: {e}")

    def run_all(self):
        results = []
        for i, acc in enumerate(self.accounts):
            checker = LeaflowAutoCheckin(acc['email'], acc['password'])
            success, result, balance = checker.run()
            results.append((acc['email'], success, result, balance))
            if i < len(self.accounts):
                logger.info(f"等待 {WAIT_TIME_BETWEEN_ACCOUNTS} 秒处理下一个账号...")
                time.sleep(WAIT_TIME_BETWEEN_ACCOUNTS)
        self.send_telegram(results)
        return results

def main():
    manager = MultiAccountManager()
    results = manager.run_all()
    success_count = sum(1 for _, s, _, _ in results if s)
    logger.info(f"{success_count}/{len(results)} 个账号签到成功")

if __name__ == "__main__":
    main()
