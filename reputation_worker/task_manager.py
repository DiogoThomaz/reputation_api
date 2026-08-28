"""Execucao de tarefas sincronas/assincronas com limite de concorrencia."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any


class TaskManager:
    """Agenda tarefas sync/async e executa com limite de simultaneidade."""

    def __init__(self, simultaneous_tasks: int = 2) -> None:
        if simultaneous_tasks < 1:
            raise ValueError("simultaneous_tasks deve ser maior que zero")
        self.simultaneous_tasks = simultaneous_tasks
        self._tasks: list[tuple[Callable[..., Any], tuple, dict]] = []

    def add_task(
        self,
        fn: Callable[..., Any],
        args: tuple = (),
        kwargs: dict | None = None,
    ) -> None:
        self._tasks.append((fn, args, kwargs or {}))

    def pending_count(self) -> int:
        return len(self._tasks)

    async def execute_tasks(self) -> list[Any]:
        semaphore = asyncio.Semaphore(self.simultaneous_tasks)
        results: list[Any] = []

        async def run(fn: Callable[..., Any], args: tuple, kwargs: dict) -> Any:
            async with semaphore:
                result = fn(*args, **kwargs)
                if isinstance(result, Awaitable):
                    result = await result
                return result

        pending = [run(fn, args, kwargs) for fn, args, kwargs in self._tasks]
        self._tasks.clear()
        results = await asyncio.gather(*pending)
        return results

    def execute(self) -> list[Any]:
        return asyncio.run(self.execute_tasks())