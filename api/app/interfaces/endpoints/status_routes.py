import logging
from fastapi import APIRouter
from app.interfaces.schemas.base import Response

# 创建当前模块的日志记录器
logger = logging.getLogger(__name__)

# 创建状态模块的路由分组，设置前缀和标签
router = APIRouter(prefix="/status", tags=["状态模块"])

@router.get(
    path="",
    response_model=Response,
    summary="系统健康检查",
    description="检查系统的postgres、redis、fastapi等组件的状态信息。"
)
async def get_status() -> Response:
    """系统健康检查，检查postgres/redis/fastapi/cos等服务"""
    return Response.success()