"""视频服务API - 提供视频处理相关功能"""

from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import Optional

from app.services.grok.upscale import VideoUpscaleManager
from app.services.grok.token import token_manager
from app.services.grok.cache import video_cache_service
from app.core.exception import GrokApiException
from app.core.logger import logger

router = APIRouter()

class UpscaleRequest(BaseModel):
    video_id: str

@router.post("/upscale")
async def upscale_video(request: UpscaleRequest, authorization: Optional[str] = Header(None)):
    """视频超分接口"""
    # 简单的Token验证 (如果全局配置了API Key)
    # 这里我们复用 grok2api 的 token 管理器获取一个可用的 sso-rw
    
    try:
        # 获取一个轮询 Token
        token_info = token_manager.get_token("grok-imagine-0.9")
        if not token_info:
            raise HTTPException(status_code=503, detail="无可用 Token")
        
        sso_rw = token_info
        
        # 执行超分
        result = await VideoUpscaleManager.upscale(request.video_id, sso_rw)
        
        # 自动下载并缓存，以便通过代理访问
        hd_url = result.get("hdMediaUrl")
        if hd_url:
            path = hd_url.replace("https://assets.grok.com", "")
            logger.info(f"[VideoAPI] 正在缓存 HD 视频: {path}")
            await video_cache_service.download_video(path, sso_rw)
            
        return result
        
    except GrokApiException as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"[VideoAPI] 接口异常: {e}")
        raise HTTPException(status_code=500, detail="服务器内部错误")
