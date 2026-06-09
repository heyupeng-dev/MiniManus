import logging
import sys
from app.infrastructure.logging.logger import setup_logging
from core.config import get_settings

def demo_print(title, value):
    """把一个对象的值和类型都打印出来，方便观察 Python 对象。"""
    print(f"\n--- {title} ---", flush=True)
    print(f"值: {value!r}", flush=True)
    print(f"类型: {type(value)}", flush=True)

def demo_logging_data_flow():
    """用具体对象演示 setup_logging() 里 logging 配置的数据流。"""
    print("这个 demo 用来观察 setup_logging() 里每一类对象到底长什么样。", flush=True)
    print("建议在 api 目录运行：uv run python -m demo.logging_demo", flush=True)

    demo_print("1. logging 是一个模块对象，不是 Logger 实例", logging)
    demo_print("2. sys.stderr 是标准错误输出流，日志通常写到这里", sys.stderr)
    demo_print("3. setup_logging 是从正式日志配置模块导入的函数", setup_logging)

    settings = get_settings()
    demo_print("4. get_settings() 返回项目配置对象", settings)
    demo_print("5. settings.log_level 是从配置里读出的日志等级字符串", settings.log_level)

    root_logger = logging.getLogger()
    demo_print("6. logging.getLogger() 不传名字时返回根 Logger", root_logger)
    demo_print("7. root_logger.handlers 是处理器列表", root_logger.handlers)

    old_handlers = root_logger.handlers.copy()
    old_level = root_logger.level

    try:
        print("\n--- 8. root_logger.handlers.clear() 的效果 ---", flush=True)
        print(f"清空前 handlers 数量: {len(root_logger.handlers)}", flush=True)
        root_logger.handlers.clear()
        print(f"清空后 handlers 数量: {len(root_logger.handlers)}", flush=True)

        log_level = getattr(logging, settings.log_level)
        demo_print("9. getattr(logging, settings.log_level) 把日志等级字符串变成 logging 模块里的常量", log_level)
        print(f"日志等级数字 {log_level} 对应的名字: {logging.getLevelName(log_level)}", flush=True)

        demo_print("10. root_logger.setLevel(log_level) 前的 root_logger.level", root_logger.level)
        root_logger.setLevel(log_level)
        demo_print("11. root_logger.setLevel(log_level) 后的 root_logger.level", root_logger.level)

        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        demo_print("12. logging.Formatter(...) 创建格式化器对象", formatter)

        record = logging.LogRecord(
            name="demo.logger",
            level=logging.INFO,
            pathname=__file__,
            lineno=0,
            msg="这是一条还没输出、只是在内存里的日志消息",
            args=(),
            exc_info=None,
        )
        demo_print("13. LogRecord 是一条日志在内存里的数据对象", record)
        print(f"Formatter.format(record) 之后的字符串: {formatter.format(record)}", flush=True)

        console_handler = logging.StreamHandler(sys.stderr)
        demo_print("14. logging.StreamHandler(sys.stderr) 创建控制台输出处理器", console_handler)
        demo_print("15. console_handler.stream 指向真正要写入的输出流", console_handler.stream)

        console_handler.setFormatter(formatter)
        demo_print("16. console_handler.formatter 保存刚才创建的 formatter", console_handler.formatter)

        console_handler.setLevel(log_level)
        demo_print("17. console_handler.level 保存 handler 自己的日志等级", console_handler.level)

        root_logger.addHandler(console_handler)
        demo_print("18. root_logger.addHandler(console_handler) 后的 handlers 列表", root_logger.handlers)

        print("\n--- 19. 真正发一条日志，看数据流动 ---", flush=True)
        print("调用 root_logger.info(...)", flush=True)
        root_logger.info("这条日志会经过 root_logger -> console_handler -> formatter -> sys.stderr")

        print("\n--- 20. 命名 Logger 和根 Logger 的关系 ---", flush=True)
        named_logger = logging.getLogger("demo.logging")
        demo_print("命名 Logger", named_logger)
        print(f"named_logger.handlers: {named_logger.handlers}", flush=True)
        print(f"named_logger.parent: {named_logger.parent!r}", flush=True)
        print("它自己没有 handler 时，会把日志继续交给 parent/root_logger。", flush=True)
        named_logger.info("这条命名 logger 的日志最终也会走到 root_logger 的 handler")

    finally:
        root_logger.handlers.clear()
        root_logger.handlers.extend(old_handlers)
        root_logger.setLevel(old_level)

if __name__ == "__main__":
    demo_logging_data_flow()
