"""Coordinate native app updates with local skill work."""
import threading

class UpdateGate:
    def __init__(self):
        self.lock = threading.Lock()
        self.pending = False

    def author(self, generate, *args):
        with self.lock:
            if self.pending: raise RuntimeError('An app update is ready to install. Reopen after updating.')
            return generate(*args)

    def prepare(self, manager):
        with manager.lock:
            if manager.busy or manager.drafts:
                return {'ready': False, 'reason': 'Finish the skill job and install or discard its preview first.'}
            if not self.lock.acquire(blocking=False):
                return {'ready': False, 'reason': 'Waiting for description generation to finish.'}
            try:
                self.pending = True
                return {'ready': True}
            finally: self.lock.release()

    def resume(self):
        with self.lock: self.pending = False
