import requests
from typing import Optional, Dict, Any

class EmailHandler:
    DEFAULT_API_KEY = "mk_DON_yo3Be6Yz9gux5LQe3xp_MO-QpCtM"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        初始化 EmailHandler
        
        Args:
            api_key: API密钥，如果不传入则使用默认值
        """
        self.api_key = api_key or self.DEFAULT_API_KEY
        self.base_url = "https://mailnet.space/api"
        self.headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json"
        }
    
    def generate_email(self, email: str = None, name: str = None, expiry_time: int = 3600000, domain: str = "moemail.app") -> Dict[str, Any]:
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
