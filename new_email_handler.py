import os
import re
import time
from typing import Optional, Dict, Any

import requests
from dotenv import load_dotenv


class EmailHandler:
    # 加载 .env 文件
    load_dotenv()

    # 从环境变量获取配置，如果不存在则使用默认值
    DEFAULT_API_KEY = os.getenv("EMAIL_API_KEY", "mk_DON_yo3Be6Yz9gux5LQe3xp_MO-QpCtM")

    # 处理 base_url，确保正确拼接 /api
    _base_url = os.getenv("EMAIL_BASE_URL", "https://mailnet.space").rstrip('/')
    DEFAULT_BASE_URL = _base_url if _base_url.endswith('/api') else f"{_base_url}/api"

    def __init__(self, api_key: Optional[str] = None):
        """
        初始化 EmailHandler
        
        Args:
            api_key: API密钥，如果不传入则使用默认值
        """
        self.api_key = api_key or self.DEFAULT_API_KEY
        self.base_url = self.DEFAULT_BASE_URL
        self.headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json"
        }

    def generate_email(self, email: Optional[str] = None, name: Optional[str] = None, expiry_time: int = 3600000,
                       domain: str = "moemail.app") -> Dict[str, Any]:
        """
        生成临时邮箱
        
        Args:
            email: 完整的邮箱地址（例如：test@moemail.app），如果提供则会自动拆分name和domain
            name: 邮箱名称（如果提供email则此参数无效）
            expiry_time: 邮箱有效期（毫秒），默认1小时
            domain: 邮箱域名（如果提供email则此参数无效）
            
        Returns:
            包含邮箱信息的字典
        """
        if email:
            try:
                name, domain = email.split("@")
            except ValueError:
                raise ValueError("邮箱格式不正确，应为：username@domain.com")

        if not name:
            raise ValueError("必须提供 email 或 name 参数")

        url = f"{self.base_url}/emails/generate"
        data = {
            "name": name,
            "expiryTime": expiry_time,
            "domain": domain
        }
        response = requests.post(url, headers=self.headers, json=data)
        return response.json()

    def get_email_list(self, cursor: Optional[str] = None) -> Dict[str, Any]:
        """
        获取邮箱列表
        
        Args:
            cursor: 分页游标
            
        Returns:
            包含邮箱列表的字典
        """
        url = f"{self.base_url}/emails"
        if cursor:
            url += f"?cursor={cursor}"
        response = requests.get(url, headers=self.headers)
        return response.json()

    def get_message_list(self, email_id: str, cursor: Optional[str] = None) -> Dict[str, Any]:
        """
        获取指定邮箱的邮件列表
        
        Args:
            email_id: 邮箱ID
            cursor: 分页游标
            
        Returns:
            包含邮件列表的字典
        """
        url = f"{self.base_url}/emails/{email_id}"
        if cursor:
            url += f"?cursor={cursor}"
        response = requests.get(url, headers=self.headers)
        return response.json()

    def get_message_detail(self, email_id: str, message_id: str) -> Dict[str, Any]:
        """
        获取单封邮件的详细信息
        
        Args:
            email_id: 邮箱ID
            message_id: 邮件ID
            
        Returns:
            包含邮件详细信息的字典
        """
        url = f"{self.base_url}/emails/{email_id}/{message_id}"
        response = requests.get(url, headers=self.headers)
        return response.json()

    def delete_message(self, email_id: str, message_id: str) -> Dict[str, Any]:
        """
        删除指定的单封邮件
        
        Args:
            email_id: 邮箱ID
            message_id: 邮件ID
            
        Returns:
            删除操作的响应结果
        """
        url = f"{self.base_url}/emails/{email_id}/{message_id}"
        response = requests.delete(url, headers=self.headers)
        return response.json()

    def delete_email(self, email_id: str) -> Dict[str, Any]:
        """
        删除指定的邮箱
        
        Args:
            email_id: 要删除的邮箱ID
            
        Returns:
            删除操作的响应结果
        """
        url = f"{self.base_url}/emails/{email_id}"
        response = requests.delete(url, headers=self.headers)
        return response.json()

    def wait_for_verification_code(self, email_id: str, max_attempts: int = 20, interval: int = 3) -> str:
        """
        轮询等待邮件并获取验证码
        
        Args:
            email_id: 邮箱ID
            max_attempts: 最大尝试次数，默认20次
            interval: 每次尝试的间隔时间（秒），默认3秒
            
        Returns:
            提取到的验证码，如果未找到则返回空字符串
        """
        for attempt in range(max_attempts):

            # 获取邮件列表
            message_list = self.get_message_list(email_id)

            # 检查是否有邮件
            if message_list.get('messages') and len(message_list['messages']) > 0:
                # 获取第一封邮件的ID
                message_id = message_list['messages'][0]['id']
                # 尝试提取验证码
                verification_code = self.extract_verification_code(email_id, message_id)
                if verification_code:
                    return verification_code

            # 如果还没到最后一次尝试，等待一段时间后继续
            if attempt < max_attempts - 1:
                time.sleep(interval)

        return ""

    def extract_verification_code(self, email_id: str, message_id: str) -> str:
        """
        获取邮件详情并提取其中的验证码，如果成功获取验证码则删除该邮件和邮箱
        
        Args:
            email_id: 邮箱ID
            message_id: 邮件ID
            
        Returns:
            提取到的6位验证码，如果未找到则返回空字符串
        """
        # 获取邮件详情
        message_detail = self.get_message_detail(email_id, message_id)

        # 获取邮件内容
        if 'message' in message_detail and 'content' in message_detail['message']:
            content = message_detail['message']['content']
            # 使用正则表达式匹配6位数字
            match = re.search(r'\b\d{6}\b', content)
            if match:
                verification_code = match.group(0)
                # 删除邮箱
                self.delete_email(email_id)
                return verification_code

        return ""


# 使用示例
if __name__ == "__main__":
    handler = EmailHandler()  # 不传入 API key，使用默认值

    # 方式1：传入完整邮箱
    new_email1 = handler.generate_email(email="test@moemail.app")
    print("方式1 - 新邮箱信息:", new_email1)

    # 方式2：分别传入用户名和域名
    new_email2 = handler.generate_email(name="test2", domain="moemail.app")
    print("方式2 - 新邮箱信息:", new_email2)

    # 获取邮箱列表
    email_list = handler.get_email_list()
    print("邮箱列表:", email_list)
