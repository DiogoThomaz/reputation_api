import asyncio
import time
import unittest

from reputation_worker.task_manager import TaskManager


class TestTaskManager(unittest.IsolatedAsyncioTestCase):
    async def test_execute_tasks_runs_sync_and_async_jobs(self):
        manager = TaskManager(simultaneous_tasks=2)

        def sync_job(value):
            return value * 2

        async def async_job(value):
            await asyncio.sleep(0.01)
            return value + 1

        manager.add_task(sync_job, args=(2,))
        manager.add_task(async_job, args=(4,))

        results = await manager.execute_tasks()

        self.assertEqual(sorted(results), [4, 5])
        self.assertEqual(manager.pending_count(), 0)

    async def test_execute_tasks_respects_concurrency_limit(self):
        manager = TaskManager(simultaneous_tasks=2)

        current_running = 0
        max_running = 0

        async def tracked_job():
            nonlocal current_running, max_running
            current_running += 1
            max_running = max(max_running, current_running)
            await asyncio.sleep(0.03)
            current_running -= 1
            return "ok"

        for _ in range(6):
            manager.add_task(tracked_job)

        results = await manager.execute_tasks()

        self.assertEqual(len(results), 6)
        self.assertEqual(max_running, 2)


class TestTaskManagerSyncAPI(unittest.TestCase):
    def test_execute_sync_helper(self):
        manager = TaskManager(simultaneous_tasks=1)

        def sync_job():
            time.sleep(0.01)
            return "done"

        manager.add_task(sync_job)
        results = manager.execute()

        self.assertEqual(results, ["done"])


if __name__ == "__main__":
    unittest.main()
