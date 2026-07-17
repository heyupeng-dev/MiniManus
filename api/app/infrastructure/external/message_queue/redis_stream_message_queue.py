import asyncio
import logging
import uuid
from typing import Any, Tuple, Optional, AsyncGenerator

from app.domain.external.message_queue import MessageQueue
from app.infrastructure.storage.redis import get_redis

logger = logging.getLogger(__name__)


class RedisStreamMessageQueue(MessageQueue):
    """基于 Redis Stream 实现的消息队列"""

    def __init__(self, stream_name: str) -> None:
        """构造函数，完成 Redis Stream 消息队列的初始化"""

        # Redis Stream 的名称
        self._stream_name = stream_name
        # Redis 客户端
        self._redis = get_redis()
        # 分布式锁的过期时间
        self._lock_expire_seconds = 10

    async def _acquire_lock(self, lock_key: str, timeout_seconds: int = 5) -> Optional[str]:
        """根据传递的 lock_key 尝试获取 Redis 分布式锁，成功返回锁值，失败返回 None"""

        # 生成一个唯一字符串，作为这次加锁的身份标识
        lock_value = str(uuid.uuid4())
        # 把超时时间保存到 end_time，用来控制循环多久后放弃获取分布式锁
        end_time = timeout_seconds

        # 只要还有剩余等待时间，就继续尝试获取锁
        while end_time > 0:
            # 调用 Redis 的 set 命令尝试写入锁，只有 key 不存在时才写入，保证同一时刻只有一个人拿到锁
            result = await self._redis.client.set(
                lock_key,
                lock_value,
                nx=True,
                ex=self._lock_expire_seconds,
            )

            # 如果设置成功，则返回锁的值
            if result:
                return lock_value

            # 如果没拿到锁，就异步等待 0.1 秒，并并剩余等待时间里扣掉 0.1 秒
            await asyncio.sleep(0.1)
            end_time -= 0.1

        # 如果超时还没拿到锁，就返回 None 表示加锁失败
        return None

    async def _release_lock(self, lock_key: str, lock_value: str) -> bool:
        """根据传递的 lock_key + lock_value 释放分布式锁"""

        # 定义 Lua 脚本，让释放锁的判断锁值和删除锁两个动作在 Redis 中原子执行
        release_script = """
        if redis.call("GET", KEYS[1]) == ARGV[1] then
            return redis.call("DEL", KEYS[1])
        else
            return 0
        end
        """

        # 开始捕获释放锁过程中的异常，避免释放失败影响主流程
        try:
            # 把 Lua 脚本注册成 Redis 可执行脚本
            script = self._redis.client.register_script(release_script)

            # 执行 Lua 脚本，keys 传锁 key，args 传当前调用者的锁值
            result = await script(keys=[lock_key], args=[lock_value])

            # Redis 删除成功返回 1，所以这里等于 1 则成功释放锁
            return result == 1

        # 如果释放锁过程中发生任何异常，就认为释放失败
        except Exception:
            return False

    async def put(self, message: Any) -> str:
        """往 Redis Stream 中添加一条消息并返回消息 ID"""

        logger.debug(f"往消息队列[{self._stream_name}]中添加一条消息: {message}")

        # 调用 xadd 把消息追加到 Redis Stream，字段名固定为 data
        return await self._redis.client.xadd(self._stream_name, {"data": message})

    async def get(self, start_id: str = None, block_ms: int = None) -> Tuple[str, Any]:
        """从 Redis Stream 中获取一条消息"""

        logger.debug(f"从消息队列[{self._stream_name}]中获取一条消息: {start_id}")

        # 判断调用方是否没有传入起始消息 ID
        if start_id is None:
            # 如果没有，就默认从 Redis Stream 的开头读取
            start_id = '0'

        # 调用 xread 从 Redis Stream 中读取消息
        messages = await self._redis.client.xread(
            # 读取指定 Stream 中大于该 ID 的消息
            {self._stream_name: start_id},
            # 最多读取一条消息
            count=1,
            block=block_ms,
        )

        # 检查 Redis 是否返回了任何 Stream 读取结果
        if not messages:
            return None, None

        # 检查返回的第一个 Stream 中是否真的包含消息
        stream_messages = messages[0][1]
        if not stream_messages:
            return None, None

        # 取出第一条消息，并拆分为消息 ID 和字段字典
        message_id, message_data = stream_messages[0]

        try:
            # 返回消息 ID 和 data 字段中的消息内容
            return message_id, message_data.get("data")
        except Exception as e:
            logger.error(f"从消息队列[{self._stream_name}]获取数据失败: {str(e)}")
            return None, None

    async def pop(self) -> Tuple[str, Any]:
        """从消息队列中获取第一条消息并删除"""

        logger.debug(f"从消息队列[{self._stream_name}]中弹出第一条消息")

        # 为当前 Stream 的 pop 操作生成专用分布式锁键，并尝试获得分布式锁
        lock_key = f"lock:{self._stream_name}:pop"
        lock_value = await self._acquire_lock(lock_key)
        if not lock_value:
            return None, None

        try:
            # 使用 xrange 获取 ID 最小、也就是最早的一条消息
            messages = await self._redis.client.xrange(
                self._stream_name,
                "-",
                "+",
                count=1
            )
            if not messages:
                return None, None

            # 拆分最早一条消息的 ID 和字段字典
            message_id, message_data = messages[0]

            # 根据消息 ID 从 Redis Stream 中删除这条消息
            await self._redis.client.xdel(
                self._stream_name,
                message_id
            )

            # 返回被删除消息的 ID 和 data 字段内容
            return message_id, message_data.get("data")
        except Exception as e:
            logger.error(f"解析消息队列[{self._stream_name}]出错: {str(e)}")
            return None
        finally:
            await self._release_lock(lock_key, lock_value)

    async def clear(self) -> None:
        """清除 Redis Stream 中的所有消息"""
        await self._redis.client.xtrim(self._stream_name, 0)

    async def is_empty(self) -> bool:
        """检查 Redis Stream 是否为空"""
        return await self.size() == 0

    async def size(self) -> int:
        """获取 Redis Stream 的长度"""
        return await self._redis.client.xlen(self._stream_name)

    async def delete_message(self, message_id: str) -> bool:
        """根据传递的消息 ID 从 Redis Stream 删除数据"""
        try:
            await self._redis.client.xdel(self._stream_name, message_id)
            return True
        except Exception:
            return False

    async def get_range(
            self,
            start_id: str = "-",
            end_id: str = "+",
            count: int = 100,
    ) -> AsyncGenerator[Tuple[str, Any], None]:
        """根据起点、终点 ID、数量，异步遍历消息"""
        # 使用 xrange 获取指定范围内的消息
        messages = await self._redis.client.xrange(
            self._stream_name,
            start_id,
            end_id,
            count=count
        )

        if not messages:
            return

        # 遍历每一条消息，并拆分消息 ID 和字段字典
        for message_id, message_data in messages:
            try:
                # 向调用方产出消息 ID 和 data 内容
                yield message_id, message_data.get("data")
            except Exception:
                continue

    async def get_latest_id(self) -> str:
        """获取 Redis Stream 中最新一条消息的 ID"""
        # 使用 xrevrange 按 ID 从大到小读取一条消息
        messages = await self._redis.client.xrevrange(
            self._stream_name,
            "+",
            "-",
            count=1)
        if not messages:
            return "0"

        # 第一条就是倒序查询得到的最新消息，返回它的 ID
        return messages[0][0]
