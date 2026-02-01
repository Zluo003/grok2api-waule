"""视频超分管理器 - 用于将普通视频升级为HD视频"""

import asyncio
import orjson
from typing import Dict, Any, Optional
from curl_cffi.requests import AsyncSession

from app.services.grok.statsig import get_dynamic_headers
from app.core.exception import GrokApiException
from app.core.config import setting
from app.core.logger import logger

# 常量
ENDPOINT = "https://grok.com/rest/media/video/upscale"
TIMEOUT = 30
BROWSER = "chrome133a"

class VideoUpscaleManager:
    """视频超分管理器"""

    @staticmethod
    async def upscale(video_id: str, auth_token: str) -> Optional[Dict[str, Any]]:
        """执行视频超分
        
        Args:
            video_id: 视频ID (UUID格式)
            auth_token: 认证令牌 (sso-rw)
            
        Returns:
            包含 hdMediaUrl 的结果字典
        """
        if not video_id:
            raise GrokApiException("视频ID缺失", "INVALID_PARAMS")
        if not auth_token:
            raise GrokApiException("认证令牌缺失", "NO_AUTH_TOKEN")

        try:
            # 构建请求
            data = {"videoId": video_id}
            
            cf = setting.grok_config.get("cf_clearance", "")
            headers = {
                **get_dynamic_headers("/rest/media/video/upscale"),
                "Cookie": f"{auth_token};{cf}" if cf else auth_token,
                "Content-Type": "application/json",
                "Origin": "https://grok.com",
                "Referer": f"https://grok.com/imagine/post/{video_id}"
            }
            
            # 使用代理池逻辑
            from app.core.proxy_pool import proxy_pool
            max_retries = 3
            
            for retry in range(max_retries + 1):
                proxy = await setting.get_proxy_async("service")
                if retry > 0 and proxy_pool._enabled:
                    proxy = await proxy_pool.force_refresh()
                
                proxies = {"http": proxy, "https": proxy} if proxy else None

                async with AsyncSession() as session:
                    response = await session.post(
                        ENDPOINT,
                        headers=headers,
                        json=data,
                        impersonate=BROWSER,
                        timeout=TIMEOUT,
                        proxies=proxies
                    )

                    if response.status_code == 200:
                        result = response.json()
                        logger.info(f"[VideoUpscale] 成功: {video_id}")
                        return result
                    
                    if response.status_code == 403 and proxy_pool._enabled and retry < max_retries:
                        logger.warning(f"[VideoUpscale] 遇到403，重试 {retry + 1}/{max_retries}")
                        await asyncio.sleep(0.5)
                        continue
                    
                    # 错误处理
                    try:
                        error = response.json()
                        msg = f"状态码: {response.status_code}, 详情: {error}"
                    except:
                        msg = f"状态码: {response.status_code}, 详情: {response.text[:200]}"
                    
                    logger.error(f"[VideoUpscale] 失败: {msg}")
                    raise GrokApiException(f"超分失败: {msg}", "UPSCALE_ERROR")

        except GrokApiException:
            raise
        except Exception as e:
            logger.error(f"[VideoUpscale] 异常: {e}")
            raise GrokApiException(f"超分异常: {e}", "UPSCALE_ERROR") from e
