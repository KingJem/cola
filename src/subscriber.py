from collections import defaultdict
from typing import Dict, Set, Callable, Coroutine
import asyncio
from inspect import iscoroutinefunction

from src.exceptions import ReceiverTypeError


class Subscriber:

    def __init__(self):
        self._subscriber: Dict[str, Set[Callable[..., Coroutine]]] = defaultdict(set)
        # 跟踪派发出去的接收者任务,便于关闭时排空(否则末尾的统计/日志会丢失)
        self._tasks: Set[asyncio.Task] = set()

    def subscribe(
            self,
            receiver: Callable[..., Coroutine],
            *,
            event: str
    ) -> None:
        if not iscoroutinefunction(receiver):
            raise ReceiverTypeError(f"{receiver.__qualname__} must be a coroutine function.")
        self._subscriber[event].add(receiver)

    def unsubscribe(
            self,
            receiver: Callable[..., Coroutine],
            *,
            event: str
    ) -> None:
        self._subscriber[event].discard(receiver)

    async def notify(self, event: str, *args, **kwargs):
        for receiver in self._subscriber[event]:
            task = asyncio.create_task(receiver(*args, **kwargs))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

    async def drain(self):
        """等待所有已派发的接收者任务完成(关闭时保证统计/日志落地)。"""
        while self._tasks:
            await asyncio.gather(*tuple(self._tasks), return_exceptions=True)
