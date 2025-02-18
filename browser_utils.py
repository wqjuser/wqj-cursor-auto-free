import logging
import os
import sys
import random
import platform
import json

from DrissionPage import ChromiumOptions, Chromium
from dotenv import load_dotenv

load_dotenv()


class BrowserManager:
    def __init__(self):
        self.browser = None

    def init_browser(self, user_agent=None, randomize_fingerprint=False):
        """初始化浏览器"""
        co = self._get_browser_options(user_agent, randomize_fingerprint)
        self.browser = Chromium(co)
        if randomize_fingerprint:
            self._inject_fingerprint_js(self.browser.latest_tab)
        return self.browser

    def _get_browser_options(self, user_agent=None, randomize_fingerprint=False):
        """获取浏览器配置"""
        co = ChromiumOptions()
        try:
            extension_path = self._get_extension_path()
            co.add_extension(extension_path)
        except FileNotFoundError as e:
            logging.warning(f"警告: {e}")

        co.set_pref("credentials_enable_service", False)
        co.set_argument("--hide-crash-restore-bubble")
        proxy = os.getenv("BROWSER_PROXY")
        if proxy:
            co.set_proxy(proxy)

        if randomize_fingerprint:
            self._randomize_fingerprint(co)

        co.auto_port()
        if user_agent:
            co.set_user_agent(user_agent)

        co.headless(
            os.getenv("BROWSER_HEADLESS", "True").lower() == "true"
        )  # 生产环境使用无头模式

        # Mac 系统特殊处理
        if sys.platform == "darwin":
            co.set_argument("--no-sandbox")
            co.set_argument("--disable-gpu")

        return co

    def _randomize_fingerprint(self, co):
        """随机化浏览器指纹"""
        # 随机化硬件并发数
        hardware_concurrency = random.randint(2, 16)
        co.set_pref("dom.maxHardwareConcurrency", hardware_concurrency)
        
        # 随机化设备内存
        memory = random.choice([2, 4, 8, 16, 32])
        co.set_pref("device.memory", memory)
        
        # 随机化语言
        languages = ['en-US', 'en-GB', 'zh-CN', 'zh-TW', 'ja-JP', 'ko-KR']
        co.set_argument(f"--lang={random.choice(languages)}")
        
        # 随机化时区
        timezones = ['Asia/Shanghai', 'America/New_York', 'Europe/London', 'Asia/Tokyo']
        co.set_argument(f"--timezone={random.choice(timezones)}")
        
        # 随机化屏幕分辨率
        resolutions = [
            (1920, 1080),
            (2560, 1440),
            (1366, 768),
            (1440, 900),
            (1680, 1050)
        ]
        width, height = random.choice(resolutions)
        co.set_argument(f"--window-size={width},{height}")
        
        logging.info("浏览器指纹已随机化")

    def _inject_fingerprint_js(self, tab):
        """注入修改浏览器指纹的 JavaScript 代码"""
        # 随机选择平台
        platforms = ['Win32', 'Linux x86_64', 'MacIntel']
        platform = random.choice(platforms)
        
        # 构建注入的 JavaScript 代码
        js_code = f"""
        // 修改平台信息
        Object.defineProperty(navigator, 'platform', {{
            get: function() {{ return '{platform}' }}
        }});
        
        // 修改硬件并发数
        Object.defineProperty(navigator, 'hardwareConcurrency', {{
            get: function() {{ return {random.randint(2, 16)} }}
        }});
        
        // 修改设备内存
        Object.defineProperty(navigator, 'deviceMemory', {{
            get: function() {{ return {random.choice([2, 4, 8, 16])} }}
        }});
        
        // 修改语言
        Object.defineProperty(navigator, 'language', {{
            get: function() {{ return '{random.choice(['en-US', 'en-GB', 'zh-CN', 'zh-TW', 'ja-JP', 'ko-KR'])}' }}
        }});
        
        // 修改 Canvas 指纹
        (function() {{
            const originalGetContext = HTMLCanvasElement.prototype.getContext;
            HTMLCanvasElement.prototype.getContext = function(type, ...args) {{
                const context = originalGetContext.apply(this, [type, ...args]);
                if (context && (type === '2d' || type === 'webgl' || type === 'webgl2')) {{
                    const noise = {random.uniform(0.1, 0.4)};  // 随机噪声值
                    
                    if (type === '2d') {{
                        const originalFillText = context.fillText;
                        context.fillText = function(...args) {{
                            context.save();
                            context.shadowBlur = noise;
                            context.shadowColor = 'rgba(0, 0, 0, 0.1)';
                            originalFillText.apply(this, args);
                            context.restore();
                        }};
                    }}
                    
                    if (type === 'webgl' || type === 'webgl2') {{
                        const originalGetParameter = context.getParameter;
                        context.getParameter = function(parameter) {{
                            const result = originalGetParameter.call(this, parameter);
                            
                            // 为某些参数添加随机噪声
                            if (parameter === this.ALIASED_LINE_WIDTH_RANGE ||
                                parameter === this.ALIASED_POINT_SIZE_RANGE) {{
                                return new Float32Array([
                                    result[0] * (1 + noise),
                                    result[1] * (1 + noise)
                                ]);
                            }}
                            
                            return result;
                        }};
                    }}
                }}
                return context;
            }};
        }})();
        
        // 修改音频指纹
        (function() {{
            const audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const originalCreateOscillator = audioContext.createOscillator;
            
            audioContext.createOscillator = function() {{
                const oscillator = originalCreateOscillator.call(this);
                const originalStart = oscillator.start;
                const noise = {random.uniform(0.1, 0.3)};  // 随机噪声值
                
                oscillator.start = function(when = 0) {{
                    const gainNode = audioContext.createGain();
                    gainNode.gain.value = 1 + noise;
                    oscillator.connect(gainNode);
                    gainNode.connect(audioContext.destination);
                    originalStart.call(this, when);
                }};
                
                return oscillator;
            }};
        }})();
        
        // 修改 WebRTC 指纹
        (function() {{
            const originalRTCPeerConnection = window.RTCPeerConnection;
            window.RTCPeerConnection = function(...args) {{
                const pc = new originalRTCPeerConnection(...args);
                const originalCreateOffer = pc.createOffer;
                
                pc.createOffer = function(...offerArgs) {{
                    const promise = originalCreateOffer.apply(this, offerArgs);
                    return promise.then(offer => {{
                        offer.sdp = offer.sdp.replace(/fingerprint:sha-256.*\\r\\n/g,
                            'fingerprint:sha-256 ' + Array.from(crypto.getRandomValues(new Uint8Array(32)))
                                .map(b => b.toString(16).padStart(2, '0')).join(':') + '\\r\\n');
                        return offer;
                    }});
                }};
                
                return pc;
            }};
        }})();
        """
        
        # 使用 DrissionPage 的 run_js 方法注入 JavaScript
        tab.run_js(js_code)

    def _get_extension_path(self):
        """获取插件路径"""
        root_dir = os.getcwd()
        extension_path = os.path.join(root_dir, "turnstilePatch")

        if hasattr(sys, "_MEIPASS"):
            extension_path = os.path.join(sys._MEIPASS, "turnstilePatch")

        if not os.path.exists(extension_path):
            raise FileNotFoundError(f"插件不存在: {extension_path}")

        return extension_path

    def quit(self):
        """关闭浏览器"""
        if self.browser:
            try:
                self.browser.quit()
            except:
                pass
