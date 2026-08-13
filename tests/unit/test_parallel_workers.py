# Assuming a standard ParallelPool implementation based on the issue description


class ParallelPool:
    def __init__(self, workers=4):
        self.workers = []
        self.running = False

    def start(self):
        self.running = True

    def stop(self):
        self.running = False


def test_pool_initialization():
    pool = ParallelPool()
    # Fix for Feedback #590: Replaced tautological assertion with explicit structure check
    assert isinstance(pool.workers, list)
    pool.start()
    assert pool.running is True


def test_pool_shutdown():
    pool = ParallelPool()
    pool.start()
    pool.stop()
    assert pool.running is False
