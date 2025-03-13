import json
import logging
import os
import sqlite3
import sys
import subprocess
import tempfile
import traceback


class CursorAuthManager:
    """Cursor认证信息管理器"""

    def __init__(self):
        # 判断操作系统
        if sys.platform == "win32":  # Windows
            appdata = os.getenv("APPDATA")
            if appdata is None:
                raise EnvironmentError("APPDATA 环境变量未设置")
            self.db_path = os.path.join(
                appdata, "Cursor", "User", "globalStorage", "state.vscdb"
            )
        elif sys.platform == "darwin":  # macOS
            self.db_path = os.path.abspath(os.path.expanduser(
                "~/Library/Application Support/Cursor/User/globalStorage/state.vscdb"
            ))
        elif sys.platform == "linux":  # Linux 和其他类Unix系统
            self.db_path = os.path.abspath(os.path.expanduser(
                "~/.config/Cursor/User/globalStorage/state.vscdb"
            ))
        else:
            raise NotImplementedError(f"不支持的操作系统: {sys.platform}")

    def update_auth(self, email=None, access_token=None, refresh_token=None, user_id=None, only_refresh=False):
        """
        更新Cursor的认证信息
        :param email: 新的邮箱地址
        :param access_token: 新的访问令牌
        :param refresh_token: 新的刷新令牌
        :param user_id: 新的用户ID
        :param only_refresh: bool 是否仅更新
        :return: bool 是否成功更新
        """
        updates = []
        if not only_refresh:
            # 登录状态
            updates.append(("cursorAuth/cachedSignUpType", "Auth_0"))

        if email is not None:
            updates.append(("cursorAuth/cachedEmail", email))
        if access_token is not None:
            updates.append(("cursorAuth/accessToken", access_token))
        if refresh_token is not None:
            updates.append(("cursorAuth/refreshToken", refresh_token))

        if not updates:
            logging.info("没有提供任何要更新的值")
            return False

        # 处理 account.json 文件
        account_path = os.path.join(os.path.dirname(self.db_path), "account.json")
        account_data = {"email": email, "user_id": user_id, "token": refresh_token or access_token}
        
        # 检查是否在macOS上运行
        is_macos = sys.platform == "darwin"
        
        try:
            # 如果是macOS系统，执行特殊处理
            if is_macos:
                logging.info("在macOS上更新account.json文件")
                return self._update_account_json_macos(account_path, account_data)
            else:
                # 非macOS系统，使用普通方式处理
                return self._update_account_json_normal(account_path, account_data)
                
        except Exception as e:
            logging.error(f"处理account.json文件失败: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
            return False
        
    def _update_account_json_normal(self, account_path, account_data):
        """普通方式更新account.json文件"""
        try:
            # 如果文件已存在，先读取现有内容
            if os.path.exists(account_path):
                try:
                    with open(account_path, 'r', encoding='utf-8') as f:
                        existing_data = json.loads(f.read())
                        # 合并新旧数据
                        for key, value in account_data.items():
                            if value is not None:
                                existing_data[key] = value
                        account_data = existing_data
                except json.JSONDecodeError:
                    logging.warning(f"account.json文件内容无效，将重新创建")
                except Exception as e:
                    logging.warning(f"读取account.json失败: {str(e)}，将重新创建")

            # 写入或更新文件
            with open(account_path, 'w', encoding='utf-8') as f:
                json.dump(account_data, f, indent=2)
            logging.info(f"成功更新account.json文件")
            
            # 更新数据库
            return self._update_database(account_data)
        except Exception as e:
            logging.error(f"更新account.json文件失败: {str(e)}")
            return False
    
    def _update_account_json_macos(self, account_path, account_data):
        """在macOS上使用管理员权限更新account.json文件"""
        import subprocess
        import tempfile
        
        try:
            # 创建临时文件
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
                temp_path = temp_file.name
                # 写入数据到临时文件
                json.dump(account_data, temp_file, indent=2)
            
            logging.info(f"已创建临时文件: {temp_path}")
            
            # 确保目标目录存在
            account_dir = os.path.dirname(account_path)
            if not os.path.exists(account_dir):
                logging.info(f"创建目录: {account_dir}")
                mkdir_cmd = ['osascript', '-e', 
                           f'do shell script "mkdir -p \\"{account_dir}\\"" with administrator privileges']
                result = subprocess.run(mkdir_cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    logging.error(f"创建目录失败: {result.stderr}")
                    return False
            
            # 使用管理员权限复制临时文件到目标位置
            cmd = ['osascript', '-e', 
                  f'do shell script "cp \\"{temp_path}\\" \\"{account_path}\\"" with administrator privileges']
            
            logging.info(f"正在复制文件到: {account_path}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                logging.error(f"复制文件失败: {result.stderr}")
                return False
            
            # 设置文件权限
            chmod_cmd = ['osascript', '-e', 
                        f'do shell script "chmod 666 \\"{account_path}\\"" with administrator privileges']
            
            chmod_result = subprocess.run(chmod_cmd, capture_output=True, text=True)
            if chmod_result.returncode != 0:
                logging.warning(f"设置文件权限失败: {chmod_result.stderr}")
            
            # 清理临时文件
            try:
                os.unlink(temp_path)
            except:
                pass
            
            logging.info("成功在macOS上更新account.json文件")
            
            # 更新数据库
            return self._update_database(account_data)
            
        except Exception as e:
            logging.error(f"在macOS上更新account.json文件失败: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
            return False
    
    def _update_database(self, account_data):
        """更新Cursor数据库"""
        updates = []
        
        # 根据account_data构建需要更新的键值对
        if 'email' in account_data and account_data['email']:
            updates.append(("cursorAuth/cachedEmail", account_data['email']))
        if 'token' in account_data and account_data['token']:
            updates.append(("cursorAuth/refreshToken", account_data['token']))
            updates.append(("cursorAuth/accessToken", account_data['token']))
        
        if not updates:
            logging.info("没有需要更新到数据库的值")
            return True
            
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            for key, value in updates:
                # 检查键是否存在
                check_query = "SELECT COUNT(*) FROM itemTable WHERE key = ?"
                cursor.execute(check_query, (key,))
                if cursor.fetchone()[0] == 0:
                    insert_query = "INSERT INTO itemTable (key, value) VALUES (?, ?)"
                    cursor.execute(insert_query, (key, value))
                else:
                    update_query = "UPDATE itemTable SET value = ? WHERE key = ?"
                    cursor.execute(update_query, (value, key))

                if cursor.rowcount > 0:
                    logging.info(f"成功更新数据库项 {key.split('/')[-1]}")
                else:
                    logging.info(f"数据库项 {key.split('/')[-1]} 未找到或值未变化")

            conn.commit()
            return True

        except sqlite3.Error as e:
            logging.error(f"数据库错误: {str(e)}")
            return False
        except Exception as e:
            logging.error(f"更新数据库时发生错误: {str(e)}")
            return False
        finally:
            if conn:
                conn.close()
