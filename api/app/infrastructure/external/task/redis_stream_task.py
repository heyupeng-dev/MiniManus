import asyncio
import logging
import uuid
from typing import Optional, Dict

from app.domain.external.message_queue import MessageQueue
from app.domain.external.task import Task, TaskRunner
from app.infrastructure.external.message_queue.redis_stream_message_queue import RedisStreamMessageQueue

logger = logging.getLogger(__name__)


class RedisStreamTask(Task):
    """基于 Redis Sream 的任务类"""

    # 定义一个类变量用于存储所有已注册的任务
    _task_registry: Dict[str, "RedisStreamTask"] = {}

    def __init__(self, task_runner: TaskRunner) -> None:
        """构造函数，创建任务并初始化任务运行器、任务 ID 和输入输出消息队列"""

        # 任务运行器：负责执行当前任务的具体业务逻辑
        self._task_runner = task_runner
        # 任务 ID：用于唯一标识当前任务
        self._id = str(uuid.uuid4())
        # 后台任务：保存当前任务对应的 asyncio.Task；None 表示尚未启动
        self._execution_task: asyncio.Task | None = None

        # 根据任务 ID 生成当前任务专属的输入和输出消息队列名称
        input_stream_name = f"task:input:{self._id}"
        output_stream_name = f"task:output:{self._id}"

        # 输入消息队列：用于向当前任务发送输入消息
        self._input_stream = RedisStreamMessageQueue(input_stream_name)
        # 输出消息队列：用于保存当前任务产生的输出消息
        self._output_stream = RedisStreamMessageQueue(output_stream_name)

        # 将当前任务保存到类级任务注册表中，之后可以通过任务 ID 找回这个 RedisStreamTask 实例
        RedisStreamTask._task_registry[self._id] = self

    def _cleanup_registry(self) -> None:
        """从当前进程的任务注册表中移除当前任务"""

        if self._id in RedisStreamTask._task_registry:
            del RedisStreamTask._task_registry[self._id]
            logger.info(f"任务[{self._id}]从注册中心移除")

    async def _on_task_done(self) -> None:
        """执行任务结束回调，并从任务注册表中移除当前任务。"""

        try:
            # 等待任务运行器完成结束回调
            await self._task_runner.on_done(self)

        except Exception:
            # 回调失败只记录日志，不让异常破坏后续清理流程
            logger.exception(
                f"任务[{self._id}]执行结束回调时发生异常"
            )

        finally:
            # 无论回调是否成功，都必须移除任务注册记录
            self._cleanup_registry()

    async def _execute_task(self) -> None:
        """执行当前任务，并统一处理取消、异常和结束清理"""

        try:
            # 将当前任务交给 TaskRunner 执行具体业务逻辑
            await self._task_runner.invoke(self)
        except asyncio.CancelledError:
            logger.info(f"任务[{self._id}]执行被取消")
            raise
        except Exception as e:
            logger.error(f"任务[{self._id}]执行出现异常: {str(e)}")

        # 无论成功、取消还是异常，最终都会执行任务结束回调
        finally:
            await self._on_task_done()

    async def invoke(self) -> None:
        """启动当前任务"""

        if self.done:
            self._execution_task = asyncio.create_task(self._execute_task())
            logger.info(f"任务[{self._id}]开始执行")

    def cancel(self) -> bool:
        """请求取消当前正在执行的任务"""
        if not self.done:
            # 让后台任务在下一个可取消的 await 位置收到 asyncio.CancelledError
            self._execution_task.cancel()
            logger.info(f"任务[{self._id}]已取消")

            # 取消请求发出后，立即移除当前任务的注册记录
            self._cleanup_registry()
            return True

        # 任务从未启动或者已经结束，不需要再发送取消请求，只需要确保任务没有残留在注册表中
        self._cleanup_registry()
        return True

    @property
    def input_stream(self) -> MessageQueue:
        """返回当前任务的输入消息队列"""
        return self._input_stream

    @property
    def output_stream(self) -> MessageQueue:
        """返回当前任务的输出消息队列"""
        return self._output_stream

    @property
    def id(self) -> str:
        """返回当前任务的 ID"""
        return self._id

    @property
    def done(self) -> bool:
        """判断当前任务是否没有在运行，如过未运行则返回 True，在运行则返回 False"""
        if self._execution_task is None:
            return True
        return self._execution_task.done()

    @classmethod
    def get(cls, task_id: str) -> Optional["Task"]:
        """根据任务 ID 从当前进程的注册表中查找任务"""
        return RedisStreamTask._task_registry.get(task_id)

    @classmethod
    def create(cls, task_runner: TaskRunner) -> "Task":
        """使用指定的 TaskRunner 创建并注册一个新任务"""
        return cls(task_runner)

    @classmethod
    async def destroy(cls) -> None:
        """取消所有任务，等待任务结束，并释放所有任务运行器资源。"""

        # 创建任务快照，后续修改注册表不会影响遍历
        tasks = list(cls._task_registry.values())

        # 清理任务注册表，进入销毁流程的任务不再允许被查找
        cls._task_registry.clear()

        # 先通知所有正在运行的任务停止
        for task in tasks:
            task.cancel()

        # 逐个等待任务结束，并释放对应运行器资源
        for task in tasks:
            execution_task = task._execution_task
            try:
                # 等待后台任务处理完取消请求和结束回调
                if execution_task is not None:
                    await execution_task
            except asyncio.CancelledError:
                pass
            except Exception:
                # 当前任务结束失败时记录异常，但继续销毁其他任务
                logger.exception(
                    f"等待任务[{task.id}]结束时发生异常"
                )
            try:
                # 无论任务结束过程是否异常，都尝试释放运行器资源
                await task._task_runner.destroy()
            except Exception:
                # 当前运行器销毁失败时记录异常，但不影响后续任务
                logger.exception(
                    f"销毁任务[{task.id}]的运行器时发生异常"
                )
