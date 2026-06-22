from fastapi import APIRouter
from app.interfaces.endpoints import status_routes, app_config_routes

def create_api_routes() -> APIRouter:
    """创建 API 路由，涵盖整个项目的所有路由管理"""
    # 创建 APIRouter 实例
    api_router = APIRouter()

    # 将各个模块添加到 api_router 中
    api_router.include_router(status_routes.router)
    api_router.include_router(app_config_routes.router)

    # 返回 APIRouter 实例
    return api_router

router = create_api_routes()