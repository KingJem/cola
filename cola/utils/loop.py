"""事件循环选择。

EVENT_LOOP 配置为 'uvloop' 时安装 uvloop 事件循环策略(libuv 实现,
高并发下吞吐提升 15~27%,见 docs)。必须在 asyncio.run() 之前调用。

回退规则(均只告警不报错):
- Windows:uvloop 不支持,回退 asyncio
- 未安装 uvloop:提示 ``pip install cola[uvloop]``,回退 asyncio
- 未知取值:回退 asyncio
"""
import sys

from loguru import logger


def install_event_loop(name: str) -> str:
    """按配置安装事件循环策略,返回实际生效的实现名。"""
    if not name or name == 'asyncio':
        return 'asyncio'
    if name != 'uvloop':
        logger.warning(f"未知 EVENT_LOOP {name!r},回退 asyncio")
        return 'asyncio'
    if sys.platform == 'win32':
        logger.warning("uvloop 不支持 Windows,回退 asyncio")
        return 'asyncio'
    try:
        import uvloop
    except ImportError:
        logger.warning("EVENT_LOOP='uvloop' 但未安装 uvloop"
                       "(pip install cola[uvloop]),回退 asyncio")
        return 'asyncio'
    import asyncio
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    logger.info(f"事件循环: uvloop {uvloop.__version__}")
    return 'uvloop'
