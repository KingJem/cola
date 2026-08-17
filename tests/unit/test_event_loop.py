"""EVENT_LOOP 配置(cola/utils/loop.py)的回退与安装行为。"""
import asyncio

import pytest

from cola.utils.loop import install_event_loop


def test_default_and_asyncio_noop():
    assert install_event_loop(None) == 'asyncio'
    assert install_event_loop('') == 'asyncio'
    assert install_event_loop('asyncio') == 'asyncio'


def test_unknown_falls_back():
    assert install_event_loop('gevent') == 'asyncio'


def test_uvloop_installs_policy_when_available():
    uvloop = pytest.importorskip('uvloop')
    old_policy = asyncio.get_event_loop_policy()
    try:
        assert install_event_loop('uvloop') == 'uvloop'
        assert isinstance(asyncio.get_event_loop_policy(),
                          uvloop.EventLoopPolicy)
    finally:
        # 恢复默认策略,避免污染其他测试
        asyncio.set_event_loop_policy(old_policy)
