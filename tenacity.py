import time
from types import SimpleNamespace


class _Nap:
    def sleep(self, seconds):
        time.sleep(seconds)


nap = _Nap()


class StopAfterAttempt:
    def __init__(self, max_attempts):
        self.max_attempts = int(max_attempts)


def stop_after_attempt(max_attempts):
    return StopAfterAttempt(max_attempts)


class WaitExponential:
    def __init__(self, multiplier=1, min=0):
        self.multiplier = multiplier
        self.min = min

    def compute(self, attempt_number):
        return self.min + (self.multiplier * (2 ** (attempt_number - 1)))


def wait_exponential(multiplier=1, min=0):
    return WaitExponential(multiplier=multiplier, min=min)


def retry_if_exception(predicate):
    return predicate


class AttemptManager:
    def __init__(self, retrying, attempt_number):
        self.retrying = retrying
        self.retry_state = SimpleNamespace(attempt_number=attempt_number)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            return False
        should_retry = self.retrying.retry(exc_val) if callable(self.retrying.retry) else False
        if self.retry_state.attempt_number >= self.retrying.stop.max_attempts:
            return False
        if not should_retry:
            return False
        delay = 0
        if self.retrying.wait and hasattr(self.retrying.wait, "compute"):
            delay = self.retrying.wait.compute(self.retry_state.attempt_number)
        nap.sleep(delay)
        return True


class Retrying:
    def __init__(self, stop, wait=None, retry=None, reraise=False):
        self.stop = stop
        self.wait = wait
        self.retry = retry or (lambda exc: False)
        self.reraise = reraise
        self._attempt = 0

    def __iter__(self):
        return self

    def __next__(self):
        if self._attempt >= self.stop.max_attempts:
            raise StopIteration
        self._attempt += 1
        return AttemptManager(self, self._attempt)