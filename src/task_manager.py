import asyncio
from asyncio import Task, Future, BoundedSemaphore as Semaphore
from typing import Set

from typing_extensions import Final


class TaskManager:

    def __init__(self, settings=None, *args, **kwargs):
        self.current_task: Final[Set] = set()
        concurrent_requests = settings.getint('CONCURRENT_REQUESTS', 16) if settings else 16
        self.sem = Semaphore(concurrent_requests)

    def create_task(self, coroutine) -> Task:
        task = asyncio.create_task(coroutine)
        self.current_task.add(task)

        def done_callback(_fut: Future):
            self.current_task.remove(task)
            self.sem.release()

        task.add_done_callback(done_callback)  # noqa
        return task

    def all_done(self):
        return len(self.current_task) == 0
