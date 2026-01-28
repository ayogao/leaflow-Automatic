#!/usr/bin/env python3
"""
Leaflow 自动签到脚本 - 极简可用版
变量名：LEAFLOW_ACCOUNTS
变量值：邮箱1:密码1,邮箱2:密码2
"""

import os
import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

class LeaflowAutoCheckin:
    def __init__(self, email, password):
        self.email = email
        self.password = password
        self.driver = None
        self._init_driver()
    
    def _init_driver(self):
        """初始化浏览器驱动"""
        options = Options()
        
        # GitHub Actions环境
        if os.getenv('GITHUB_ACTIONS'):
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--window-size=1920,1080')
        
        # 通用设置
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        self.driver = webdriver.Chrome(options=options)
        self.driver.implicitly_wait(10)
    
    def login(self):
        """登录"""
        logger.info(f"登录账号: {self.email}")
        
        try:
            # 访问登录页
            self.driver.get("https://leaflow.net/login")
            time.sleep(3)
            
            # 输入邮箱
            email_input = self.driver.find_element(By.XPATH, "//input[@type='email' or @type='text']")
            email_input.send_keys(self.email)
            time.sleep(1)
            
            # 输入密码
            password_input = self.driver.find_element(By.XPATH, "//input[@type='password']")
            password_input.send_keys(self.password)
            time.sleep(1)
            
            # 点击登录
            login_btn = self.driver.find_element(By.XPATH, "//button[contains(text(), '登录') or @type='submit']")
            login_btn.click()
            time.sleep(5)
            
            # 检查是否登录成功
            if "dashboard" in self.driver.current_url or "login" not in self.driver.current_url:
                logger.info("登录成功")
                return True
            else:
                logger.error("登录失败")
                return False
                
        except Exception as e:
            logger.error(f"登录出错: {e}")
            return False
    
    def checkin(self):
        """签到"""
        logger.info("开始签到")
        
        try:
            # 方法1: 直接访问签到页
            try:
                self.driver.get("https://checkin.leaflow.net")
                time.sleep(5)
            except:
                # 方法2: 从仪表板跳转
                self.driver.get("https://leaflow.net/dashboard")
                time.sleep(3)
                self.driver.get("https://checkin.leaflow.net")
                time.sleep(5)
            
            # 等待页面加载
            time.sleep(3)
            
            # 查找签到按钮
            checkin_buttons = [
                "//button[contains(text(), '立即签到')]",
                "//button[contains(text(), '签到')]",
                "//button[@class='checkin-btn']",
                "button.checkin-btn"
            ]
            
            for btn_xpath in checkin_buttons:
                try:
                    if "checkin-btn" in btn_xpath and not btn_xpath.startswith("//"):
                        # CSS选择器
                        btn = self.driver.find_element(By.CSS_SELECTOR, btn_xpath)
                    else:
                        # XPath选择器
                        btn = self.driver.find_element(By.XPATH, btn_xpath)
                    
                    if btn.is_displayed():
                        btn_text = btn.text
                        
                        if "已签到" in btn_text:
                            logger.info("今日已签到")
                            return "今日已签到"
                        
                        btn.click()
                        logger.info("点击签到按钮")
                        time.sleep(3)
                        
                        # 获取签到结果
                        return self._get_result()
                        
                except Exception as e:
                    continue
            
            logger.error("未找到签到按钮")
            return "签到失败：未找到按钮"
            
        except Exception as e:
            logger.error(f"签到出错: {e}")
            return f"签到失败：{str(e)}"
    
    def _get_result(self):
        """获取签到结果"""
        try:
            # 等待结果出现
            time.sleep(2)
            
            # 查找成功提示
            success_elements = [
                "//*[contains(text(), '成功')]",
                "//*[contains(text(), '获得')]",
                "//*[contains(text(), '恭喜')]",
                ".success-message",
                ".alert-success"
            ]
            
            for element in success_elements:
                try:
                    if element.startswith("//"):
                        elem = self.driver.find_element(By.XPATH, element)
                    else:
                        elem = self.driver.find_element(By.CSS_SELECTOR, element)
                    
                    if elem.is_displayed():
                        text = elem.text[:50]  # 截取前50个字符
                        return f"签到成功：{text}"
                except:
                    continue
            
            # 检查页面是否有成功关键词
            page_text = self.driver.page_source
            if "成功" in page_text or "获得" in page_text or "谢谢" in page_text:
                return "签到成功"
            
            return "签到完成（结果未知）"
            
        except Exception as e:
            return f"签到完成：{str(e)}
