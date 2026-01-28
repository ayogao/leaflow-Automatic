class LeaflowAutoCheckin:
    """GitHub Actions 专用稳定版"""

    def __init__(self, email, password):
        self.email = email
        self.password = password
        self.driver = None
        self.setup_driver()

    def setup_driver(self):
        chrome_options = Options()
        if os.getenv("GITHUB_ACTIONS"):
            chrome_options.add_argument("--headless=new")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)

        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    def wait_page_ready(self, timeout=15):
        """等待页面完全加载"""
        try:
            WebDriverWait(self.driver, timeout).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            return True
        except:
            return False

    def close_popup(self):
        try:
            # 尝试点击页面空白处关闭弹窗
            ActionChains(self.driver).move_by_offset(10, 10).click().perform()
            time.sleep(1)
        except:
            pass

    def login(self):
        self.driver.get("https://leaflow.net/login")
        if not self.wait_page_ready():
            logger.warning("页面加载超时")
        time.sleep(2)
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
            email_input = WebDriverWait(self.driver, 5, 0.5).until(
                lambda d: d.find_element(By.CSS_SELECTOR, sel)
            )
            if email_input:
                break
        if not email_input:
            raise Exception(f"找不到邮箱输入框, URL={self.driver.current_url}")
        email_input.clear()
        email_input.send_keys(self.email)

        # 密码输入
        password_input = WebDriverWait(self.driver, 5, 0.5).until(
            lambda d: d.find_element(By.CSS_SELECTOR, "input[type='password']")
        )
        password_input.clear()
        password_input.send_keys(self.password)

        # 登录按钮
        login_btn_selectors = ["button[type='submit']", "//button[contains(text(),'登录')]"]
        login_btn = None
        for sel in login_btn_selectors:
            try:
                if sel.startswith("//"):
                    login_btn = WebDriverWait(self.driver, 5, 0.5).until(
                        lambda d: d.find_element(By.XPATH, sel)
                    )
                else:
                    login_btn = WebDriverWait(self.driver, 5, 0.5).until(
                        lambda d: d.find_element(By.CSS_SELECTOR, sel)
                    )
                if login_btn:
                    break
            except:
                continue
        if not login_btn:
            raise Exception("找不到登录按钮")
        login_btn.click()

        WebDriverWait(self.driver, 15, 0.5).until(
            lambda d: "dashboard" in d.current_url or "login" not in d.current_url
        )
        logger.info(f"{self.email} 登录成功, URL={self.driver.current_url}")

    def checkin(self):
        self.driver.get("https://checkin.leaflow.net")
        for attempt in range(3):
            time.sleep(5)
            self.wait_page_ready()
            checkin_btn_selectors = ["button.checkin-btn", "//button[contains(text(),'立即签到')]"]
            for sel in checkin_btn_selectors:
                try:
                    if sel.startswith("//"):
                        btn = self.driver.find_element(By.XPATH, sel)
                    else:
                        btn = self.driver.find_element(By.CSS_SELECTOR, sel)
                    if btn.is_displayed():
                        if "已签到" in btn.text:
                            return "今日已签到"
                        btn.click()
                        time.sleep(2)
                        return "签到完成"
                except:
                    continue
            logger.warning(f"第{attempt+1}次尝试未找到签到按钮, 重试...")
        raise Exception("签到页面加载失败，找不到签到按钮")

    def get_balance(self):
        self.driver.get("https://leaflow.net/dashboard")
        self.wait_page_ready()
        body = self.driver.find_element(By.TAG_NAME, "body").text
        m = re.search(r"¥?\d+\.?\d*", body)
        return m.group(0) if m else "未知"

    def run(self):
        try:
            self.login()
            result = self.checkin()
            balance = self.get_balance()
            logger.info(f"{self.email} 签到结果: {result}, 余额: {balance}")
            return True, result, balance
        except Exception as e:
            logger.error(f"{self.email} 自动签到失败: {e}")
            return False, str(e), "未知"
        finally:
            if self.driver:
                self.driver.quit()
