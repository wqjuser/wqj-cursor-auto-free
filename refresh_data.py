import json
import logging
import os
import random
import sys
import time
from datetime import datetime, timedelta, UTC
from typing import Optional, Dict, List
import urllib.parse
import requests

from browser_utils import BrowserManager
from config import Config
from cursor_auth_manager import CursorAuthManager
from get_email_code import EmailVerificationHandler

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


class EmailGenerator:
    def __init__(self):
        configInstance = Config()
        self.domain = configInstance.get_domain()

    @staticmethod
    def generate_password(length=12):
        """生成随机密码"""
        characters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*"
        return "".join(random.choices(characters, k=length))

    @staticmethod
    def generate_random_name(length=6):
        """生成随机用户名"""
        first_letter = random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        rest_letters = "".join(
            random.choices("abcdefghijklmnopqrstuvwxyz", k=length - 1)
        )
        return first_letter + rest_letters

    def generate_email(self, length=8):
        """生成随机邮箱地址"""
        random_str = "".join(random.choices("abcdefghijklmnopqrstuvwxyz", k=length))
        timestamp = str(int(time.time()))[-6:]  # 使用时间戳后6位
        return f"{random_str}{timestamp}@{self.domain}"

    def get_account_info(self):
        """获取完整的账号信息"""
        return {
            "email": self.generate_email(),
            "password": self.generate_password(),
            "first_name": self.generate_random_name(),
            "last_name": self.generate_random_name()
        }


def handle_turnstile(tab, max_retries: int = 2) -> bool:
    """处理 Turnstile 验证"""
    logging.info("正在检测 Turnstile 验证...")
    retry_count = 0

    while retry_count < max_retries:
        retry_count += 1
        logging.debug(f"第 {retry_count} 次尝试验证")

        try:
            # 定位验证框元素
            challenge_check = (
                tab.ele("@id=cf-turnstile", timeout=2)
                .child()
                .shadow_root.ele("tag:iframe")
                .ele("tag:body")
                .sr("tag:input")
            )

            if challenge_check:
                logging.info("检测到 Turnstile 验证框，开始处理...")
                time.sleep(random.uniform(1, 3))
                challenge_check.click()
                time.sleep(2)

            # 检查验证结果
            if tab.ele("Account Settings"):
                logging.info("验证成功 - 已进入账户设置页面")
                return True
            elif tab.ele("@data-index=0"):
                logging.info("验证成功 - 已到达验证码页面")
                return True
            elif tab.ele("@name=password"):
                logging.info("验证成功 - 已到达密码页面")
                return True

        except Exception as e:
            logging.debug(f"当前尝试未成功: {str(e)}")

        if retry_count < max_retries:
            time.sleep(random.uniform(1, 2))

    return False


def get_cursor_session_token(tab, max_attempts=3) -> Optional[tuple[str, str]]:
    """获取Cursor会话token"""
    logging.info("开始获取cookie")
    attempts = 0

    while attempts < max_attempts:
        try:
            cookies = tab.cookies()
            for cookie in cookies:
                if cookie.get("name") == "WorkosCursorSessionToken":
                    value = cookie["value"]
                    parts = value.split("%3A%3A")
                    if len(parts) >= 2:
                        return parts[0], parts[1]

            attempts += 1
            if attempts < max_attempts:
                logging.warning(f"第 {attempts} 次尝试未获取到CursorSessionToken，2秒后重试...")
                time.sleep(2)
            else:
                logging.error(f"已达到最大尝试次数({max_attempts})，获取CursorSessionToken失败")

        except Exception as e:
            logging.error(f"获取cookie失败: {str(e)}")
            attempts += 1
            if attempts < max_attempts:
                time.sleep(2)

    return None


def sign_in_account(tab, email: str, password: str) -> bool:
    """登录Cursor账号"""
    logging.info(f"=== 开始登录账号: {email} ===")
    login_url = "https://authenticator.cursor.sh"

    try:
        # 访问登录页面
        tab.get(login_url)

        # 输入邮箱
        if tab.ele("@name=email"):
            tab.ele("@name=email").input(email)
            time.sleep(random.uniform(1, 3))
            tab.ele("@type=submit").click()
            logging.info("邮箱已提交")

        # 处理turnstile验证
        if not handle_turnstile(tab):
            logging.error("第一次Turnstile验证失败")
            return False

        # 输入密码
        if tab.ele("@name=password"):
            tab.ele("@name=password").input(password)
            time.sleep(random.uniform(1, 2))
            tab.ele("@value=password").click()
            logging.info("密码已提交")

        # 再次处理turnstile验证
        if not handle_turnstile(tab):
            logging.error("第二次Turnstile验证失败")
            return False

        # 检查是否登录成功
        if tab.ele("Account Settings", timeout=10):
            logging.info("登录成功!")
            return True
        else:
            logging.error("登录失败")
            return False

    except Exception as e:
        logging.error(f"登录过程出错: {str(e)}")
        return False


def get_available_accounts() -> List[Dict]:
    """获取可用账号列表"""
    try:
        response = requests.get("https://accounts.zxai.fun/api/accounts/available")
        if response.status_code == 200:
            data = response.json()
            return data.get("accounts", [])
        else:
            logging.error(f"获取账号列表失败，状态码: {response.status_code}")
            return []
    except Exception as e:
        logging.error(f"获取账号列表时出错: {str(e)}")
        return []


def show_menu():
    """显示功能选择菜单"""
    print("\n=== Cursor 工具 ===")
    print("1. 刷新数据")
    print("2. 批量注册")
    print("3. 退出")

    while True:
        choice = input("\n请选择功能 (1-3): ").strip()
        if choice in ['1', '2', '3']:
            return int(choice)
        print("无效的选择，请重试")


def sign_up_account(tab, email: str, password: str, first_name: str, last_name: str,
                    email_handler: EmailVerificationHandler) -> bool | None:
    """注册Cursor账号"""
    logging.info(f"=== 开始注册账号: {email} ===")
    sign_up_url = "https://authenticator.cursor.sh/sign-up"

    try:
        # 访问注册页面
        tab.get(sign_up_url)

        # 输入个人信息
        if tab.ele("@name=first_name"):
            logging.info("正在填写个人信息...")
            tab.ele("@name=first_name").input(first_name)
            logging.info(f"已输入名字: {first_name}")
            time.sleep(random.uniform(1, 3))

            tab.ele("@name=last_name").input(last_name)
            logging.info(f"已输入姓氏: {last_name}")
            time.sleep(random.uniform(1, 3))

            tab.ele("@name=email").input(email)
            logging.info(f"已输入邮箱: {email}")
            time.sleep(random.uniform(1, 3))

            logging.info("提交个人信息...")
            tab.ele("@type=submit").click()

        # 处理turnstile验证
        if not handle_turnstile(tab):
            logging.error("第一次Turnstile验证失败")
            return False

        # 设置密码
        if tab.ele("@name=password"):
            logging.info("正在设置密码...")
            tab.ele("@name=password").input(password)
            time.sleep(random.uniform(1, 3))

            logging.info("提交密码...")
            tab.ele("@type=submit").click()
            logging.info("密码设置完成")

        # 再次处理turnstile验证
        if not handle_turnstile(tab):
            logging.error("第二次Turnstile验证失败")
            return False

        # 处理邮箱验证码
        while True:
            if tab.ele("Account Settings"):
                logging.info("注册成功 - 已进入账户设置页面")
                return True
            elif tab.ele("@data-index=0"):
                logging.info("正在获取邮箱验证码...")
                code = email_handler.get_verification_code()
                if not code:
                    logging.error("获取验证码失败")
                    return False

                logging.info(f"成功获取验证码: {code}")
                logging.info("正在输入验证码...")
                i = 0
                for digit in code:
                    tab.ele(f"@data-index={i}").input(digit)
                    time.sleep(random.uniform(0.1, 0.3))
                    i += 1
                logging.info("验证码输入完成")

                # 处理可能的turnstile验证
                if not handle_turnstile(tab):
                    logging.error("验证码提交后的Turnstile验证失败")
                    return False

                # 等待处理结果
                time.sleep(3)
                continue

            time.sleep(1)

    except Exception as e:
        logging.error(f"注册过程出错: {str(e)}")
        return False


def switch_proxy() -> bool:
    """切换代理
    Returns:
        bool: 是否成功切换到新代理
    """
    try:
        # 获取代理列表
        response = requests.get("http://127.0.0.1:9097/proxies/OKZTWO")
        if response.status_code == 200:
            proxy_data = response.json()
            all_proxies = proxy_data.get('all', [])

            # 筛选出以"专线"和"Lv"开头的代理
            valid_proxies = [
                proxy for proxy in all_proxies
                if proxy.startswith(('专线', 'Lv'))
            ]

            if valid_proxies:
                # 随机选择代理并检查存活状态，直到找到可用的代理
                random.shuffle(valid_proxies)  # 随机打乱代理列表

                for selected_proxy in valid_proxies:
                    # URL编码代理名称
                    encoded_proxy = urllib.parse.quote(selected_proxy)

                    # 检查代理存活状态
                    check_response = requests.get(f"http://127.0.0.1:9097/proxies/{encoded_proxy}")
                    if check_response.status_code == 200:
                        proxy_info = check_response.json()
                        is_alive = proxy_info.get('alive')

                        if is_alive:  # 如果代理存活
                            logging.info(f"找到可用代理: {selected_proxy}")

                            # 切换到选中的代理
                            proxy_payload = {"name": selected_proxy}
                            put_response = requests.put(
                                "http://127.0.0.1:9097/proxies/OKZTWO",
                                json=proxy_payload
                            )

                            if put_response.status_code == 204:
                                logging.info(f"成功切换到代理: {selected_proxy}")
                                # 等待1秒
                                time.sleep(1)

                                # 获取当前IP
                                try:
                                    ip_response = requests.get("http://ip-api.com/json")
                                    if ip_response.status_code == 200:
                                        ip_info = ip_response.json()
                                        current_ip = ip_info.get('query', 'unknown')
                                        logging.info(f"当前IP地址: {current_ip}")
                                except Exception as e:
                                    logging.error(f"获取IP地址失败: {str(e)}")
                                return True
                            else:
                                logging.error("切换代理失败")
                        else:
                            logging.warning(f"代理 {selected_proxy} 未存活 (alive: {is_alive})，尝试下一个")
                    else:
                        logging.error(f"检查代理 {selected_proxy} 状态失败")

                logging.error("未找到可用的存活代理")
                return False
            else:
                logging.error("未找到符合条件的代理")
                return False
        else:
            logging.error("获取代理列表失败")
            return False
    except Exception as e:
        logging.error(f"代理切换过程出错: {str(e)}")
        return False


def get_user_agent():
    """获取user_agent"""
    try:
        # 使用JavaScript获取user agent
        browser_manager = BrowserManager()
        browser = browser_manager.init_browser()
        user_agent = browser.latest_tab.run_js("return navigator.userAgent")
        browser_manager.quit()
        return user_agent
    except Exception as e:
        logging.error(f"获取user agent失败: {str(e)}")
        return None

def batch_register(num_accounts):
    """批量注册账号
    Args:
        num_accounts: 要注册的账号数量
    """
    # 获取邮箱PIN码
    pin = input("\n请输入邮箱 PIN 码: ").strip()
    logging.info("PIN 码已输入")
    logging.info("正在初始化邮箱验证模块...")
    # 初始化邮箱验证处理器
    email_handler = EmailVerificationHandler(pin=pin)

    successful_accounts = []
    failed_attempts = 0

    for i in range(num_accounts):
        # 切换代理
        if not switch_proxy():
            logging.error("代理切换失败，跳过当前账号注册")
            failed_attempts += 1
            continue

        # 开始注册流程
        logging.info(f"\n=== 开始注册第 {i + 1}/{num_accounts} 个账号 ===")
        browser_manager = None
        try:
            # 初始化浏览器
            logging.info("正在初始化浏览器...")
            # 获取user_agent
            user_agent = get_user_agent()
            if not user_agent:
                logging.error("获取user agent失败，使用默认值")
                user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            # 剔除user_agent中的"HeadlessChrome"
            user_agent = user_agent.replace("HeadlessChrome", "Chrome")
            browser_manager = BrowserManager()
            browser = browser_manager.init_browser(user_agent=user_agent)
            # 获取并打印浏览器的user-agent
            user_agent = browser.latest_tab.run_js("return navigator.userAgent")
            tab = browser.latest_tab
            tab.run_js("try { turnstile.reset() } catch(e) { }")
            # 生成账号信息
            email_generator = EmailGenerator()
            account_info = email_generator.get_account_info()
            email = account_info["email"]
            password = account_info["password"]
            first_name = account_info["first_name"]
            last_name = account_info["last_name"]

            # 注册账号
            if sign_up_account(tab, email, password, first_name, last_name, email_handler):
                # 获取会话令牌
                tokens = get_cursor_session_token(tab)
                if tokens:
                    user_id, refresh_token = tokens
                    access_token = refresh_token
                    successful_accounts.append({
                        'email': email,
                        'password': password,
                        'user_id': user_id,
                        'refresh_token': refresh_token,
                        'access_token': access_token
                    })
                    logging.info(f"第 {i + 1} 个账号注册成功")
                    # 调用接口保存账号
                    try:
                        credits = 150  # 默认额度
                        save_result = save_account_to_api(email, password, credits, user_id, refresh_token,
                                                          access_token)
                        if save_result:
                            logging.info("账号已成功保存到数据库")
                        else:
                            logging.warning("账号保存到数据库失败")
                    except Exception as e:
                        logging.error(f"保存账号过程出错: {str(e)}")
                else:
                    failed_attempts += 1
                    logging.error(f"第 {i + 1} 个账号获取令牌失败")
            else:
                failed_attempts += 1
                logging.error(f"第 {i + 1} 个账号注册失败")
        except Exception as e:
            failed_attempts += 1
            logging.error(f"第 {i + 1} 个账号注册时发生错误: {str(e)}")
        finally:
            if browser_manager:
                browser_manager.quit()

        if i < num_accounts - 1:  # 如果不是最后一个账号，则添加延迟
            delay_seconds = random.uniform(10, 20)
            logging.info(f"为避免频繁注册，将等待 {delay_seconds:.1f} 秒后继续下一个注册...")
            time.sleep(delay_seconds)

    # 打印注册结果摘要
    logging.info("\n=== 批量注册完成 ===")
    logging.info(f"成功注册账号数: {len(successful_accounts)}")
    logging.info(f"失败注册数: {failed_attempts}")

    # 保存账号信息到文件
    if successful_accounts:
        filename = f"cursor_accounts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("=== Cursor 账号信息 ===\n\n")
                for acc in successful_accounts:
                    f.write(f"邮箱: {acc['email']}\n")
                    f.write(f"密码: {acc['password']}\n")
                    f.write(f"用户ID: {acc['user_id']}\n")
                    f.write(f"刷新令牌: {acc['refresh_token']}\n")
                    f.write(f"访问令牌: {acc['access_token']}\n")
                    f.write("-" * 30 + "\n")
            logging.info(f"账号信息已保存到文件: {filename}")
        except Exception as e:
            logging.error(f"保存账号信息到文件时出错: {str(e)}")


def save_account_to_api(email, password, credits=150, user_id=None, refresh_token=None, access_token=None):
    """保存账号信息到API
    Args:
        email: 邮箱账号
        password: 密码
        credits: 额度，默认150
        user_id: 用户ID
        refresh_token: 刷新令牌
        access_token: 访问令牌
    Returns:
        bool: 是否保存成功
    """
    api_url = "https://accounts.zxai.fun/api/accounts"
    payload = {
        "accounts": [
            {
                "email": email,
                "password": password,
                "credits": credits,
                "user_id": user_id,
                "refresh_token": refresh_token,
                "access_token": access_token
            }
        ]
    }

    try:
        response = requests.post(api_url, json=payload)
        if response.status_code == 200:
            return True
        else:
            logging.error(f"保存账号信息失败，状态码: {response.status_code}")
            return False
    except Exception as e:
        logging.error(f"调用保存账号接口出错: {str(e)}")
        return False


def update_cursor_auth(email=None, access_token=None, refresh_token=None, user_id=None, only_refresh=True):
    """
    更新Cursor的认证信息的便捷函数
    """
    auth_manager = CursorAuthManager()
    return auth_manager.update_auth(email, access_token, refresh_token, user_id, only_refresh=only_refresh)


def change_account_info(email: str) -> bool:
    """标记账号为已使用状态
    Args:
        email: 要标记的账号邮箱
    Returns:
        bool: 是否标记成功
    """
    logging.info(f"正在标记账号 {email} 为已使用状态...")
    api_url = f"https://accounts.zxai.fun/api/accounts/{email}/mark-used"

    try:
        response = requests.put(api_url)
        if response.status_code == 200:
            logging.info(f"账号 {email} 已成功标记为已使用")
            return True
        else:
            logging.error(f"标记账号失败，状态码: {response.status_code}")
            return False
    except Exception as e:
        logging.error(f"标记账号时出错: {str(e)}")
        return False


def replace_account():
    """替换账号功能"""
    # 根据操作系统确定account.json的路径
    if sys.platform == "win32":  # Windows
        appdata = os.getenv("APPDATA")
        if appdata is None:
            logging.error("APPDATA 环境变量未设置")
            return False
        account_path = os.path.join(appdata, "Cursor", "User", "globalStorage", "account.json")
    elif sys.platform == "darwin":  # macOS
        account_path = os.path.abspath(os.path.expanduser(
            "~/Library/Application Support/Cursor/User/globalStorage/account.json"
        ))
    elif sys.platform == "linux":  # Linux
        account_path = os.path.abspath(os.path.expanduser(
            "~/.config/Cursor/User/globalStorage/account.json"
        ))
    else:
        logging.error(f"不支持的操作系统: {sys.platform}")
        return False
    if os.path.exists(account_path):
        try:
            with open(account_path, 'r', encoding='utf-8') as f:
                account_data = json.loads(f.read())
                current_user_id = account_data.get('user_id')

                if current_user_id:
                    # 检查使用情况
                    logging.info("开始检查账号使用情况...")
                    try:
                        cookies = {
                            'WorkosCursorSessionToken': f"{current_user_id}%3A%3A{account_data['token']}"
                        }
                        response = requests.get(
                            f"https://www.cursor.com/api/usage",
                            params={"user": current_user_id},
                            cookies=cookies
                        )
                        if response.status_code == 200:
                            usage_data = response.json()
                            # 将字符串解析为datetime并添加UTC时区
                            start_of_month = datetime.strptime(usage_data['startOfMonth'],
                                                               "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)
                            expiry_date = start_of_month + timedelta(days=14)
                            current_time = datetime.now(UTC)

                            logging.info(f"账号开始时间: {start_of_month}")
                            logging.info(f"账号过期时间: {expiry_date}")
                            logging.info(f"当前时间: {current_time}")

                            if expiry_date > current_time:
                                logging.info("账号在有效期内")
                                gpt4_usage = usage_data.get('gpt-4', {}).get('numRequests', 0)
                                logging.info(f"高级对话 已使用次数: {gpt4_usage}")

                                if gpt4_usage < 50:
                                    logging.info("当前账号仍然可用，无需替换")
                                    return True
                                else:
                                    logging.info("高级对话 使用次数已达到或超过限制，需要替换账号")
                            else:
                                logging.info("账号已过期，需要替换")
                        else:
                            logging.error(f"API请求失败，状态码: {response.status_code}")
                            if response.status_code == 401:
                                logging.error("认证失败，token可能已过期，需要替换账号")
                    except Exception as e:
                        logging.error(f"检查使用情况时出错: {str(e)}")
                else:
                    logging.info("account.json 中没有 user_id 信息")
        except Exception as e:
            logging.error(f"读取account.json文件时出错: {str(e)}")

    logging.info("开始执行账号替换流程...")
    # 获取可用账号
    accounts = get_available_accounts()
    if len(accounts) == 0:
        logging.error("没有可用的账号")
        return False

    logging.info(f"获取到 {len(accounts)} 个可用账号")
    # 随机选择一个
    account = random.choice(accounts)
    logging.info(f"随机选择一个账号: {account['email']}")

    # 更新认证信息
    logging.info("更新认证信息...")
    is_updated = update_cursor_auth(
        email=account["email"],
        access_token=account["access_token"],
        refresh_token=account["refresh_token"],
        user_id=account["user_id"],
        only_refresh = True
    )

    if is_updated:
        # 标记账号为已使用
        if change_account_info(account["email"]):
            logging.info("账号替换完成")
            logging.info(
                f"脚本为免费提供，请勿用于商业用途。也请通过付费渠道获得本脚本的用户及时退款，以免造成不必要的损失。")
            return True
        else:
            logging.error("标记账号已使用状态失败")
            logging.info(
                f"脚本为免费提供，请勿用于商业用途。也请通过付费渠道获得本脚本的用户及时退款，以免造成不必要的损失。")
            return False

    else:
        logging.error("更新认证信息失败")
        logging.info(f"脚本为免费提供，请勿用于商业用途。也请通过付费渠道获得本脚本的用户及时退款，以免造成不必要的损失。")
        return False


def refresh_data():
    """刷新数据功能"""
    # 获取可用账号
    accounts = get_available_accounts()
    if not accounts:
        logging.error("没有可用的账号")
        return

    logging.info(f"获取到 {len(accounts)} 个可用账号")

    # 初始化浏览器
    browser_manager = BrowserManager()
    browser = browser_manager.init_browser()

    try:
        # 为每个账号创建新的上下文
        for account in accounts:
            tab = browser.latest_tab

            email = account["email"]
            password = account["password"]

            # 登录账号
            if sign_in_account(tab, email, password):
                # 获取会话令牌
                tokens = get_cursor_session_token(tab)
                if tokens:
                    user_id, refresh_token = tokens
                    logging.info(f"账号 {email} 登录成功，获取到令牌")
                    logging.info(f"获取到的user_id: \n{user_id}")
                    logging.info(f"获取到的refresh_token: \n{refresh_token}")
                else:
                    logging.error(f"账号 {email} 获取令牌失败")

            # 添加随机延迟，避免频繁请求
            time.sleep(random.uniform(5, 10))

    except Exception as e:
        logging.error(f"程序执行出错: {str(e)}")
    finally:
        browser_manager.quit()


def main():
    while True:
        choice = show_menu()

        if choice == 1:
            refresh_data()
        elif choice == 2:
            while True:
                try:
                    num = input("\n请输入要注册的账号数量: ").strip()
                    num = int(num)
                    if num > 0:
                        break
                    print("请输入大于0的数字")
                except ValueError:
                    print("请输入有效的数字")
            batch_register(num)
        elif choice == 3:
            print("程序退出")
            sys.exit(0)

        input("\n按回车键继续...")


if __name__ == "__main__":
    main()
