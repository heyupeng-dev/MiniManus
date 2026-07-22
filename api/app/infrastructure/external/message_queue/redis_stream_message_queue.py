import asyncio
import logging
import uuid
from typing import Any, Tuple, Optional, AsyncGenerator, cast

from app.domain.external.message_queue import MessageQueue
from app.infrastructure.storage.redis import get_redis

logger = logging.getLogger(__name__)


class RedisStreamMessageQueue(MessageQueue):
    """基于 Redis Stream 实现的异步消息队列"""

    def __init__(self, stream_name: str) -> None:
        """绑定 Stream 名称并取得进程内共享的 Redis 客户端包装器"""

        # Stream 名称同时用于隔离队列数据和该队列的 pop 锁
        self._stream_name = stream_name
        # 实际连接由应用生命周期中的 get_redis().init() 完成
        self._redis = get_redis()
        # 锁自动过期可避免持有者异常退出后永久占用锁
        self._lock_expire_seconds = 10

    async def _acquire_lock(self, lock_key: str, timeout_seconds: int = 5) -> Optional[str]:
        """在等待期限内轮询获取 Redis 分布式锁"""

        # 唯一锁值用于在释放时确认当前调用者仍是锁的持有者
        lock_value = str(uuid.uuid4())
        # 记录剩余等待时间，而不是绝对截止时间
        end_time = timeout_seconds

        while end_time > 0:
            # SET NX 保证同一 lock_key 只能被一个客户端写入；EX 为锁设置兜底过期时间
            result = await self._redis.client.set(
                lock_key,
                lock_value,
                nx=True,
                ex=self._lock_expire_seconds,
            )

            if result:
                return lock_value

            # 短暂异步等待后重试，不阻塞事件循环中的其他协程
            await asyncio.sleep(0.1)
            end_time -= 0.1

        return None

    async def _release_lock(self, lock_key: str, lock_value: str) -> bool:
        """仅当锁仍属于当前调用者时释放分布式锁"""

        # Lua 将“校验锁所有权”和“删除锁”作为一个原子操作执行，避免锁过期并被其他客户端取得后，旧持有者误删新锁
        release_script = """
        if redis.call("GET", KEYS[1]) == ARGV[1] then
            return redis.call("DEL", KEYS[1])
        else
            return 0
        end
        """

        try:
            script = self._redis.client.register_script(release_script)

            # keys 和 args 分别映射到 Lua 脚本中的 KEYS[1] 和 ARGV[1]
            result = await script(keys=[lock_key], args=[lock_value])

            # DEL 返回 1 表示锁存在且已由当前调用者成功删除
            return result == 1

        except Exception:
            return False

    async def put(self, message: Any) -> str:
        """使用 XADD 追加消息，并返回 Redis 自动生成的消息 ID"""

        logger.debug(f"往消息队列[{self._stream_name}]中添加一条消息: {message}")

        message_id = await self._redis.client.xadd(
            self._stream_name,
            {"data": message},
        )

        if isinstance(message_id, bytes):
            return message_id.decode("utf-8")

        return message_id

    async def get(
            self,
            start_id: str = None,
            block_ms: int = None,
    ) -> Tuple[str, Any]:
        """读取 ID 严格大于 start_id 的一条消息"""

        logger.debug(f"从消息队列[{self._stream_name}]中获取一条消息: {start_id}")

        # 未指定读取位置时，默认从消息队列开头开始
        if start_id is None:
            start_id = '0'

        # 读取指定位置之后的一条消息
        messages = await self._redis.client.xread(
            {self._stream_name: start_id},
            count=1,
            block=block_ms,
        )

        if not messages:
            return None, None

        stream_messages = messages[0][1]
        if not stream_messages:
            return None, None

        message_id, message_data = stream_messages[0]

        try:
            return message_id, message_data.get("data")
        except Exception as e:
            logger.error(f"从消息队列[{self._stream_name}]获取数据失败: {str(e)}")
            return None, None

    async def pop(self) -> Tuple[str, Any]:
        """在分布式锁保护下取出并删除消息队列中最早的一条消息"""

        logger.debug(f"从消息队列[{self._stream_name}]中弹出第一条消息")

        # 为当前队列的 pop 操作加锁，防止多个程序同时取到同一条消息
        lock_key = f"lock:{self._stream_name}:pop"
        lock_value = await self._acquire_lock(lock_key)
        if not lock_value:
            return None, None

        try:
            # 从队列开头读取最早的一条消息，但此时还没有删除它
            messages = await self._redis.client.xrange(
                self._stream_name,
                "-",
                "+",
                count=1
            )
            if not messages:
                return None, None

            # 取出这条消息的 ID 和字段数据
            message_id, message_data = messages[0]

            # 根据消息 ID 将刚才读取到的消息从队列中删除
            await self._redis.client.xdel(
                self._stream_name,
                message_id
            )

            # 返回被删除消息的 ID 以及消息内容
            return cast(str, message_id), message_data.get("data")
        except Exception as e:
            logger.error(f"解析消息队列[{self._stream_name}]出错: {str(e)}")
            return None, None
        finally:
            # 无论读取成功、队列为空还是发生异常，最终都必须尝试释放锁
            await self._release_lock(lock_key, lock_value)

    async def clear(self) -> None:
        """清空当前消息队列中的全部消息"""

        # 将 Stream 的最大消息数量裁剪为 0，相当于清空全部消息
        await self._redis.client.xtrim(self._stream_name, 0)

    async def is_empty(self) -> bool:
        """判断当前消息队列是否为空"""

        return await self.size() == 0

    async def size(self) -> int:
        """返回当前消息队列中的消息数量"""

        return await self._redis.client.xlen(self._stream_name)

    async def delete_message(self, message_id: str) -> bool:
        """根据消息 ID 删除指定消息"""

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
        """读取指定 ID 范围内最多 count 条消息，并逐条返回消息 ID 和内容"""

        # 一次性读取指定 ID 范围内的消息
        messages = await self._redis.client.xrange(
            self._stream_name,
            start_id,
            end_id,
            count=count
        )

        if not messages:
            return

        # 逐条取出消息 ID 和字段数据，并返回给调用方
        for message_id, message_data in messages:
            try:
                # yield 每次返回一条消息，但不会结束当前函数
                yield cast(str, message_id), message_data.get("data")
            except Exception:
                continue

    async def get_latest_id(self) -> str:
        """返回当前消息队列中最新一条消息的 ID"""

        # 按消息 ID 从大到小查询，并且只读取第一条，因此得到的就是当前最新的消息
        messages = await self._redis.client.xrevrange(
            self._stream_name,
            "+",
            "-",
            count=1)

        if not messages:
            return "0"

        return cast(str, messages[0][0])
