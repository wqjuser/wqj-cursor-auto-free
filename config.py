import os
import random
import sys

from dotenv import load_dotenv

from logger import logging


class Config:
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        # 如果已经初始化过，直接返回
        if self._initialized:
            return

        self._initialized = True
        
        self.version = "0.3.9.1"

        # 获取应用程序的根目录路径
        if getattr(sys, "frozen", False):
            # 如果是打包后的可执行文件
            application_path = os.path.dirname(sys.executable)
        else:
            # 如果是开发环境
            application_path = os.path.dirname(os.path.abspath(__file__))

        # 指定 .env 文件的路径
        dotenv_path = os.path.join(application_path, ".env")
        self._domains = [
            "wqj666.ggff.net",
            "wqjsonder.ggff.net",
            "wqjnb.ggff.net",
            ]
        # 设置默认值
        self.imap = False
        self.temp_mail = "sonder"  # 默认设置为 sonder
        self.domain = random.choice(self._domains)
        # 不设置默认API URL，必须从环境变量中读取

        # 检查是否支持颜色输出
        def supports_color():
            if os.name == 'nt':
                try:
                    import ctypes
                    kernel32 = ctypes.windll.kernel32
                    handle = kernel32.GetStdHandle(-11)
                    mode = ctypes.c_ulong()
                    if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                        return False
                    mode.value |= 0x0004
                    if not kernel32.SetConsoleMode(handle, mode):
                        return False
                    return True
                except:
                    return False
            return True

        # 根据是否支持颜色选择输出格式
        if supports_color():
            yellow = "\033[33m"
            reset = "\033[0m"
        else:
            yellow = ""
            reset = ""

        # 如果.env文件存在，则读取配置
        if os.path.exists(dotenv_path):
            # 加载 .env 文件，设置 override=False 防止创建新文件
            load_dotenv(dotenv_path, override=False)

            env_domain = os.getenv("DOMAIN")
            if env_domain and self.check_is_valid(env_domain):
                try:
                    # 尝试解析环境变量中的域名数组
                    domains = eval(env_domain)
                    if isinstance(domains, list) and len(domains) > 0:
                        self.domain = random.choice(domains).strip()
                    else:
                        self.domain = env_domain.strip()
                except:
                    # 如果解析失败，使用原始字符串
                    self.domain = env_domain.strip()
            
            env_temp_mail = os.getenv("TEMP_MAIL", "").strip()

            # 只有当环境变量中存在 TEMP_MAIL 时才覆盖默认值
            if env_temp_mail:
                self.temp_mail = env_temp_mail.split("@")[0]

            # 如果临时邮箱为null则加载IMAP
            if self.temp_mail == "null":
                self.imap = True
                self.imap_server = os.getenv("IMAP_SERVER", "").strip()
                self.imap_port = os.getenv("IMAP_PORT", "").strip()
                self.imap_user = os.getenv("IMAP_USER", "").strip()
                self.imap_pass = os.getenv("IMAP_PASS", "").strip()
                self.imap_dir = os.getenv("IMAP_DIR", "inbox").strip()

            # 读取API相关URL
            self.api_base_url = os.getenv("API_BASE_URL")
            self.api_accounts_url = os.getenv("API_ACCOUNTS_URL")
            self.api_available_accounts_url = os.getenv("API_AVAILABLE_ACCOUNTS_URL")
            self.api_mark_used_url_prefix = os.getenv("API_MARK_USED_URL_PREFIX")
        else:
            self.print_config()

        self.check_config()

    def get_temp_mail(self):

        return self.temp_mail
    
    def get_version(self):
        return self.version

    def get_imap(self):
        if not self.imap:
            return False
        return {
            "imap_server": self.imap_server,
            "imap_port": self.imap_port,
            "imap_user": self.imap_user,
            "imap_pass": self.imap_pass,
            "imap_dir": self.imap_dir,
        }

    def get_domain(self):
        """返回域名
        如果存在环境变量配置的域名，则从配置的域名数组中随机返回一个
        否则随机返回一个默认域名
        """
        env_domain = os.getenv("DOMAIN")
        if env_domain and self.check_is_valid(env_domain):
            try:
                # 尝试解析环境变量中的域名数组
                domains = eval(env_domain)
                if isinstance(domains, list) and len(domains) > 0:
                    return random.choice(domains).strip()
            except:
                # 如果解析失败，返回原始字符串
                return env_domain.strip()
        return random.choice(self._domains)

    def get_api_base_url(self):
        """获取API基础URL"""
        if not self.api_base_url:
            logging.warning("API_BASE_URL未配置，API相关功能将不可用")
            return None
        return self.api_base_url

    def get_api_accounts_url(self):
        """获取账号API URL"""
        if not self.api_accounts_url:
            logging.warning("API_ACCOUNTS_URL未配置，账号API相关功能将不可用")
            return None
        return self.api_accounts_url

    def get_api_available_accounts_url(self):
        """获取可用账号API URL"""
        if not self.api_available_accounts_url:
            logging.warning("API_AVAILABLE_ACCOUNTS_URL未配置，获取可用账号功能将不可用")
            return None
        return self.api_available_accounts_url

    def get_api_mark_used_url(self, email):
        """获取标记账号已使用的API URL"""
        if not self.api_mark_used_url_prefix:
            logging.warning("API_MARK_USED_URL_PREFIX未配置，标记账号已使用功能将不可用")
            return None
        return f"{self.api_mark_used_url_prefix}/{email}/mark-used"

    def check_config(self):
        """检查配置项是否有效

        检查规则：
        1. 如果使用 tempmail.plus，需要配置 TEMP_MAIL 和 DOMAIN
        2. 如果使用 IMAP，需要配置 IMAP_SERVER、IMAP_PORT、IMAP_USER、IMAP_PASS
        3. IMAP_DIR 是可选的
        4. DOMAIN 可以是单个域名或域名数组
        5. API相关URL为可选配置
        
        Returns:
            bool: 配置是否有效
        """
        try:
            # 检查域名配置
            env_domain = os.getenv("DOMAIN")
            if env_domain:
                try:
                    domains = eval(env_domain)
                    if isinstance(domains, list):
                        if not domains:
                            logging.error("域名数组不能为空，请在 .env 文件中正确设置 DOMAIN")
                            return False
                        for domain in domains:
                            if not self.check_is_valid(domain):
                                logging.error(f"域名数组中存在无效域名: {domain}")
                                return False
                    elif not self.check_is_valid(env_domain):
                        logging.error("域名配置无效，请在 .env 文件中正确设置 DOMAIN")
                        return False
                except:
                    if not self.check_is_valid(env_domain):
                        logging.error("域名配置无效，请在 .env 文件中正确设置 DOMAIN")
                        return False
            elif not self.check_is_valid(self.domain):
                logging.error("域名未配置，请在 .env 文件中设置 DOMAIN")
                return False

            # 检查邮箱配置
            if self.temp_mail != "null":
                # tempmail.plus 模式
                if not self.check_is_valid(self.temp_mail):
                    logging.error("临时邮箱未配置，请在 .env 文件中设置 TEMP_MAIL")
                    return False
            else:
                # IMAP 模式
                imap_configs = {
                    "imap_server": "IMAP服务器",
                    "imap_port": "IMAP端口",
                    "imap_user": "IMAP用户名",
                    "imap_pass": "IMAP密码",
                }

                for key, name in imap_configs.items():
                    value = getattr(self, key)
                    if value == "null" or not self.check_is_valid(value):
                        logging.error(f"{name}未配置，请在 .env 文件中设置 {key.upper()}")
                        return False

                # IMAP_DIR 是可选的，如果设置了就检查其有效性
                if self.imap_dir != "null" and not self.check_is_valid(self.imap_dir):
                    logging.error("IMAP收件箱目录配置无效，请在 .env 文件中正确设置 IMAP_DIR")
                    return False
            
            # 检查邮箱API配置 - 这些是可选的
            if os.getenv("EMAIL_BASE_URL") and not self.check_is_valid(os.getenv("EMAIL_BASE_URL")):
                logging.warning("EMAIL_BASE_URL未配置或无效")
            if os.getenv("EMAIL_API_KEY") and not self.check_is_valid(os.getenv("EMAIL_API_KEY")):
                logging.warning("EMAIL_API_KEY未配置或无效")
            # 检查API相关配置 - 这些是可选的
            if os.getenv("API_BASE_URL") and not self.check_is_valid(os.getenv("API_BASE_URL")):
                logging.warning("API_BASE_URL配置无效")
            if os.getenv("API_ACCOUNTS_URL") and not self.check_is_valid(os.getenv("API_ACCOUNTS_URL")):
                logging.warning("API_ACCOUNTS_URL配置无效")
            if os.getenv("API_AVAILABLE_ACCOUNTS_URL") and not self.check_is_valid(os.getenv("API_AVAILABLE_ACCOUNTS_URL")):
                logging.warning("API_AVAILABLE_ACCOUNTS_URL配置无效")
            if os.getenv("API_MARK_USED_URL_PREFIX") and not self.check_is_valid(os.getenv("API_MARK_USED_URL_PREFIX")):
                logging.warning("API_MARK_USED_URL_PREFIX配置无效")

            return True
        except Exception as e:
            logging.error(f"配置检查出错: {str(e)}")
            return False

    def check_is_valid(self, value):
        """检查配置项是否有效

        Args:
            value: 配置项的值

        Returns:
            bool: 配置项是否有效
        """
        return isinstance(value, str) and len(str(value).strip()) > 0

    def print_config(self):
        # 检查是否支持颜色输出
        def supports_color():
            if os.name == 'nt':
                try:
                    import ctypes
                    kernel32 = ctypes.windll.kernel32
                    handle = kernel32.GetStdHandle(-11)
                    mode = ctypes.c_ulong()
                    if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                        return False
                    mode.value |= 0x0004
                    if not kernel32.SetConsoleMode(handle, mode):
                        return False
                    return True
                except:
                    return False
            return True

        # 根据是否支持颜色选择输出格式
        if supports_color():
            yellow = "\033[33m"
            reset = "\033[0m"
        else:
            yellow = ""
            reset = ""

# 使用示例
if __name__ == "__main__":
    try:
        config = Config()
        print("环境变量加载成功！")
        # config.print_config()
    except ValueError as e:
        print(f"错误: {e}")
