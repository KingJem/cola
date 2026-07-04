import asyncio
from asyncio import Task, Future, Semaphore
from typing import Set

from typing_extensions import Final


class TaskManager:

    def __init__(self, settings=None, *args, **kwargs):
        self.current_task: Final[Set] = set()
        concurrent_requests = settings.getint('CONCURRENT_REQUESTS', 16) if settings else 16
        self.limit = concurrent_requests
        # 缩容时来不及回收的许可数;任务完成回调优先偿还欠账再释放
        self._debt = 0
        self.sem = Semaphore(concurrent_requests)

    def create_task(self, coroutine) -> Task:
        task = asyncio.create_task(coroutine)
        self.current_task.add(task)

        def done_callback(_fut: Future):
            self.current_task.remove(task)
            if self._debt > 0:
                self._debt -= 1
            else:
                self.sem.release()

        task.add_done_callback(done_callback)  # noqa
        return task

    def resize(self, new_limit: int):
        """热调整并发上限。扩容立即生效;缩容先扣空闲许可,
        不足部分记入欠账,由在途任务完成时逐步吸收。"""
        new_limit = max(1, int(new_limit))
        delta = new_limit - self.limit
        if delta > 0:
            offset = min(self._debt, delta)
            self._debt -= offset
            for _ in range(delta - offset):
                self.sem.release()
        elif delta < 0:
            shrink = -delta
            # Semaphore 无同步 acquire;_value>0 时扣减等价于一次不等待的 acquire
            while shrink and self.sem._value > 0:  # noqa
                self.sem._value -= 1  # noqa
                shrink -= 1
            self._debt += shrink
        self.limit = new_limit

    def all_done(self):
        return len(self.current_task) == 0
