#!/usr/bin/env python3
"""
Leaflow 多账号自动签到脚本 - 完整优化版
变量名：LEAFLOW_ACCOUNTS
变量值：邮箱1:密码1,邮箱2:密码2,邮箱3:密码3
"""

import os
import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
import requests
from datetime import datetime
import re

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LeaflowAutoCheckin:
    def __init__(self, email, password):
        self.email = email
        self.password = password
        self.telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID', '')

        if not self.email or not self.password:
            raise ValueError("邮箱和密码不能为空")

        self.driver = None
        self.setup_driver()

    def setup_driver(self):
        """设置Chrome驱动选项"""
        chrome_options = Options()
        # GitHub Actions环境配置
        if os.getenv('GITHUB_ACTIONS'):
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
        # 通用配置
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        self.driver.set_page_load_timeout(120)  # 避免超时

    def close_popup(self):
        """关闭初始弹窗"""
        try:
            logger.info("尝试关闭初始弹窗...")
            time.sleep(2)
            try:
                actions = ActionChains(self.driver)
                actions.move_by_offset(10, 10).click().perform()
                logger.info("已成功关闭弹窗")
                return True
            except:
                return False
        except Exception as e:
            logger.warning(f"关闭弹窗时出错: {e}")
            return False

    def wait_for_element_clickable(self, by, value, timeout=10):
        return WebDriverWait(self.driver, timeout).until(
            EC.element_to_be_clickable((by, value))
        )

    def login(self):
        """执行登录流程"""
        logger.info(f"开始登录流程")
        self.driver.get("https://leaflow.net/login")
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        self.close_popup()

        # 输入邮箱
        email_selectors = [
            "input[type='text']",
            "input[type='email']",
            "input[placeholder*='邮箱']",
            "input[placeholder*='邮件']",
            "input[placeholder*='email']",
            "input[name='email']",
            "input[name='username']"
        ]
        email_input = None
        for selector in email_selectors:
            try:
                email_input = self.wait_for_element_clickable(By.CSS_SELECTOR, selector, 5)
                break
            except:
                continue
        if not email_input:
            raise Exception("找不到邮箱输入框")
        email_input.clear()
        email_input.send_keys(self.email)
        logger.info("邮箱输入完成")

        # 输入密码
        password_input = self.wait_for_element_clickable(By.CSS_SELECTOR, "input[type='password']", 10)
        password_input.clear()
        password_input.send_keys(self.password)
        logger.info("密码输入完成")

        # 点击登录
        login_btn_selectors = [
            "//button[contains(text(), '登录')]",
            "//button[contains(text(), 'Login')]",
            "//button[@type='submit']",
            "//input[@type='submit']",
            "button[type='submit']"
        ]
        login_btn = None
        for selector in login_btn_selectors:
            try:
                if selector.startswith("//"):
                    login_btn = self.wait_for_element_clickable(By.XPATH, selector, 5)
                else:
                    login_btn = self.wait_for_element_clickable(By.CSS_SELECTOR, selector, 5)
                break
            except:
                continue
        if not login_btn:
            raise Exception("找不到登录按钮")
        login_btn.click()
        logger.info("已点击登录按钮")

        # 等待登录完成
        WebDriverWait(self.driver, 20).until(
            lambda d: "dashboard" in d.current_url or "workspaces" in d.current_url or "login" not in d.current_url
        )
        logger.info(f"登录成功，当前URL: {self.driver.current_url}")
        return True

    def get_balance(self):
        """获取当前账号的总余额"""
        try:
            self.driver.get("https://leaflow.net/dashboard")
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            balance_selectors = [
                "//*[contains(text(), '¥') or contains(text(), '￥') or contains(text(), '元')]",
                "//*[contains(@class, 'balance')]",
                "//*[contains(@class, 'money')]",
                "//*[contains(@class, 'amount')]",
                "//button[contains(@class, 'dollar')]",
                "//span[contains(@class, 'font-medium')]"
            ]
            for selector in balance_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    for element in elements:
                        text = element.text.strip()
                        if any(char.isdigit() for char in text) and ('¥' in text or '￥' in text or '元' in text):
                            numbers = re.findall(r'\d+\.?\d*', text)
                            if numbers:
                                balance = numbers[0]
                                logger.info(f"找到余额: {balance}元")
                                return f"{balance}元"
                except:
                    continue
            logger.warning("未找到余额信息")
            return "未知"
        except Exception as e:
            logger.warning(f"获取余额时出错: {e}")
            return "未知"

    # ================= 优化签到相关方法 =================
    def wait_for_checkin_page_loaded(self, timeout=60):
        """等待签到页面完全加载"""
        checkin_indicators = [
            "button.checkin-btn",
            "//button[contains(text(), '立即签到')]",
            "//button[contains(text(), '已签到')]",
            "//*[contains(text(), '每日签到')]",
            "//*[contains(text(), '签到')]"
        ]
        for indicator in checkin_indicators:
            try:
                if indicator.startswith("//"):
                    elem = WebDriverWait(self.driver, timeout).until(
                        EC.presence_of_element_located((By.XPATH, indicator))
                    )
                else:
                    elem = WebDriverWait(self.driver, timeout).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, indicator))
                    )
                if elem.is_displayed():
                    logger.info(f"签到页面元素已加载: {indicator}")
                    return True
            except:
                continue
        logger.warning("签到页面加载失败，未找到签到相关元素")
        return False

    def find_and_click_checkin_button(self):
        """查找并点击签到按钮"""
        logger.info("查找签到按钮...")
        checkin_selectors = [
            "button.checkin-btn",
            "//button[contains(text(), '立即签到')]",
            "//button[contains(@class, 'checkin')]",
            "button[type='submit']",
            "button[name='checkin']"
        ]
        for selector in checkin_selectors:
            try:
                if selector.startswith("//"):
                    checkin_btn = WebDriverWait(self.driver, 15).until(
                        EC.presence_of_element_located((By.XPATH, selector))
                    )
                else:
                    checkin_btn = WebDriverWait(self.driver, 15).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                if checkin_btn.is_displayed():
                    btn_text = checkin_btn.text.strip()
                    if "已签到" in btn_text:
                        logger.info("今日已签到过，无需再次签到")
                        return "already_checked_in"
                    if checkin_btn.is_enabled():
                        logger.info("找到并点击立即签到按钮")
                        checkin_btn.click()
                        return True
                    else:
                        logger.info("签到按钮不可用，可能已签到")
                        return "already_checked_in"
            except Exception as e:
                logger.debug(f"选择器未找到按钮: {e}")
                continue
        logger.error("找不到签到按钮")
        return False

    def checkin(self):
        """执行签到流程"""
        logger.info("跳转到签到页面...")
        try:
            self.driver.get("https://leaflow.net/dashboard")
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            logger.info("仪表板页面加载完成")

            self.driver.get("https://checkin.leaflow.net")
            self.driver.set_page_load_timeout(120)

            if not self.wait_for_checkin_page_loaded(timeout=60):
                raise Exception("签到页面加载失败，未找到签到相关元素")

            checkin_result = self.find_and_click_checkin_button()
            if checkin_result == "already_checked_in":
                return "今日已签到"
            elif checkin_result is True:
                logger.info("已点击立即签到按钮")
                WebDriverWait(self.driver, 10).until(
                    lambda d: "已签到" in d.page_source or "成功" in d.page_source or "签到完成" in d.page_source
                )
                result_message = self.get_checkin_result()
                return result_message
            else:
                raise Exception("找不到立即签到按钮或按钮不可点击")
        except Exception as e:
            raise Exception(f"签到流程出错: {e}")

    def get_checkin_result(self):
        """获取签到结果消息"""
        try:
            time.sleep(2)
            success_selectors = [
                ".alert-success",
                ".success",
                ".message",
                "[class*='success']",
                "[class*='message']",
                ".modal-content",
                ".ant-message",
                ".el-message",
                ".toast",
                ".notification"
            ]
            for selector in success_selectors:
                try:
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if element.is_displayed() and element.text.strip():
                        return element.text.strip()
                except:
                    continue
            page_text = self.driver.find_element(By.TAG_NAME, "body").text
            keywords = ["成功", "签到", "获得", "恭喜", "谢谢", "感谢", "完成", "已签到", "连续签到"]
            for line in page_text.split("\n"):
                if any(k in line for k in keywords) and len(line.strip()) < 100:
                    return line.strip()
            return "签到完成，但未找到具体结果消息"
        except Exception as e:
            return f"获取签到结果时出错: {str(e)}"

    def run(self):
        """单个账号执行流程"""
        try:
            logger.info(f"开始处理账号: {self.email}")
            if self.login():
                result = self.checkin()
                balance = self.get_balance()
                logger.info(f"签到结果: {result}, 余额: {balance}")
                return True, result, balance
            else:
                raise Exception("登录失败")
        except Exception as e:
            error_msg = f"自动签到失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, "未知"
        finally:
            if self.driver:
                self.driver.quit()


class MultiAccountManager:
    """多账号管理器"""
    def __init__(self):
        self.telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
        self.accounts = self.load_accounts()

    def load_accounts(self):
        """从环境变量加载账号"""
        accounts = []
        accounts_str = os.getenv('LEAFLOW_ACCOUNTS', '').strip()
        if accounts_str:
            for pair in accounts_str.split(','):
                if ':' in pair:
                    email, password = pair.split(':', 1)
                    accounts.append({'email': email.strip(), 'password': password.strip()})
            if accounts:
                logger.info(f"加载 {len(accounts)} 个账号")
                return accounts
        # 单账号
        single_email = os.getenv('LEAFLOW_EMAIL', '').strip()
        single_password = os.getenv('LEAFLOW_PASSWORD', '').strip()
        if single_email and single_password:
            accounts.append({'email': single_email, 'password': single_password})
            logger.info("加载单个账号")
            return accounts
        raise ValueError("未找到有效的账号配置")

    def send_notification(self, results):
        """发送Telegram通知"""
        if not self.telegram_bot_token or not self.telegram_chat_id:
            logger.info("Telegram配置未设置，跳过通知")
            return
        try:
            success_count = sum(1 for _, success, _, _ in results if success)
            total_count = len(results)
            current_date = datetime.now().strftime("%Y/%m/%d")
            message = f"🎁 Leaflow自动签到通知\n📊 成功: {success_count}/{total_count}\n📅 签到时间：{current_date}\n\n"
            for email, success, result, balance in results:
                masked_email = email[:3] + "***" + email[email.find("@"):]
                status = "✅" if success else "❌"
                message += f"账号：{masked_email}\n{status}  {result}\n💰  当前总余额：{balance}\n\n" if success else f"账号：{masked_email}\n{status}  {result}\n\n"
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
            requests.post(url, data={"chat_id": self.telegram_chat_id, "text": message, "parse_mode": "HTML"}, timeout=10)
            logger.info("Telegram汇总通知发送成功")
        except Exception as e:
            logger.error(f"发送Telegram通知失败: {e}")

    def run_all(self):
        """运行所有账号签到"""
        results = []
        for i, account in enumerate(self.accounts, 1):
            try:
                auto_checkin = LeaflowAutoCheckin(account['email'], account['password'])
                success, result, balance = auto_checkin.run()
                results.append((account['email'], success, result, balance))
                if i < len(self.accounts):
                    time.sleep(5)
            except Exception as e:
                results.append((account['email'], False, f"处理账号异常: {str(e)}", "未知"))
        self.send_notification(results)
        return all(success for _, success, _, _ in results), results


def main():
    try:
        manager = MultiAccountManager()
        overall_success, detailed_results = manager.run_all()
        if overall_success:
            logger.info("✅ 所有账号签到成功")
        else:
            success_count = sum(1 for _, success, _, _ in detailed_results if success)
            logger.warning(f"⚠️ 部分账号签到失败: {success_count}/{len(detailed_results)} 成功")
        exit(0)
    except Exception as e:
        logger.error(f"❌ 脚本执行出错: {e}")
        exit(1)


if __name__ == "__main__":
    main()
