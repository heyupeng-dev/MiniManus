import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from app.application.errors.exceptions import AppException
from app.interfaces.schemas.base import Response

# 创建当前模块的日志记录器
logger = logging.getLogger(__name__)

def register_exception_handlers(app: FastAPI) -> None:
    """处理 MiniManus 项目中所有的异常并进行统一处理，涵盖自定义业务状态异常、HTTP 异常、通用异常"""

    # 注册 App 异常处理器：当项目里抛出 AppException 时，用下面这个函数处理
    @app.exception_handler(AppException)
    async def app_exception_handler(req: Request, e: AppException) -> JSONResponse:
        """处理 MiniManus 业务异常，将所有状态统一响应结构"""
        logger.error(f"AppException: {e.msg}")
        return JSONResponse(
            status_code=e.status_code,
            content=Response(
                code=e.status_code,
                msg=e.msg,
                data={}
            )
            # 将 content 转换成普通 Python 字典，方便 JSONResponse 输出成 JSON
            .model_dump(),
        )

    # 注册 HTTP 异常处理器：当项目里抛出 HTTPException 时，用下面这个函数处理
    @app.exception_handler(HTTPException)
    async def http_exception_handler(req: Request, e: HTTPException) -> JSONResponse:
        """处理 FastAPI 抛出的 HTTP 异常，将所有状态统一响应结构"""
        logger.error(f"HTTPException: {e.detail}")
        return JSONResponse(
            status_code=e.status_code,
            content=Response(
                code=e.status_code,
                msg=e.detail,
                data={}
            ).model_dump(),
        )

    # 注册兜底异常处理器：当项目里抛出的异常不是 AppException，也不是 HTTPException，就走这里
    @app.exception_handler(Exception)
    async def exception_handler(req: Request, e: Exception) -> JSONResponse:
        """处理 MiniManus 中抛出的未定义的任意一场，将状态码统一设置为 500"""
        logger.error(f"Exception: {str(e)}")
        return JSONResponse(
            status_code=500,
            content=Response(
                code=500,
                msg="服务器出现异常请稍后重试",
                data={},
            ).model_dump()
        )
