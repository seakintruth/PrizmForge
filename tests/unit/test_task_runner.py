import unittest
from pathlib import Path

from task_runner import TaskRunner


class TestTaskRunner(unittest.TestCase):
    def test_demo_task(self):
        """
        Test the task runner with a demo script.
        References feedback #586: Use pathlib for cross-platform path resolution.
        """
        runner = TaskRunner()
        # Use pathlib to avoid hardcoded string path issues on different OS (Feedback #586)
        task_path = Path("tr") / "demo.py"
        runner.run(str(task_path))


if __name__ == "__main__":
    unittest.main()
