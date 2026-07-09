import asyncio
from typing import List

from app.domain.external.health_checker import HealthChecker
from app.domain.models.health_status import HealthStatus


class StatusService:
    """应用层状态服务，负责编排所有基础设施健康检查器并聚合结果"""

    def __init__(self, checkers: List[HealthChecker]) -> None:
        """构造函数，传递所有健康检查器完成服务初始化"""
        self._checkers = checkers

    async def check_all(self) -> List[HealthStatus]:
        """调用所有检查器发起检查并返回对应的健康状态"""
        # 并发执行多个异步检查任务
        results = await asyncio.gather(
            # 调用每个检查器的 check 方法
            *(checker.check() for checker in self._checkers),
            # 某个检查失败时返回异常而不是中断
            return_exceptions=True,
        )

        # 处理可能发生的异常
        processed_results = []
        # 逐个处理检查结果
        for res in results:
            # 判断结果是不是异常
            if isinstance(res, Exception):
                # 如果是异常则格式化为 HealthStatus
                processed_results.append(HealthStatus(
                    service="未知服务",
                    status="error",
                    details=f"未知检查器发生错误: {str(res)}"
                ))
            # 如果不是异常则直接保存结果
            else:
                processed_results.append(res)

        # 返回最终健康状态列表
        return processed_results
