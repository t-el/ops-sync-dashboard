from __future__ import annotations

import logging
import random
import time
from typing import Callable, TypeVar

import httpx

T = TypeVar("T")
log = logging.getLogger("ops.retry")


class TransientError(Exception):
    pass


class PermanentError(Exception):
    pass


def check_response(resp: httpx.Response, source: str) -> httpx.Response:
    if resp.status_code == 429 or resp.status_code >= 500:
        raise TransientError(f"{source} HTTP {resp.status_code}")
    if resp.status_code >= 400:
        raise PermanentError(f"{source} HTTP {resp.status_code}: {resp.text[:200]}")
    return resp


def with_retry(fn: Callable[[], T], *, attempts: int, base_delay: float, label: str,
               sleep: Callable[[float], None] = time.sleep, on_attempt: Callable[[int], None] | None = None) -> T:
    for attempt in range(1, attempts + 1):
        if on_attempt:
            on_attempt(attempt)
        try:
            return fn()
        except (TransientError, httpx.TransportError) as exc:
            if attempt == attempts:
                raise TransientError(f"{exc} (after {attempts} attempts)") from exc
            delay = min(60.0, base_delay * 2 ** (attempt - 1)) * random.uniform(0.5, 1.0)
            log.warning("transient failure, retrying", extra={"label": label, "attempt": attempt,
                                                              "next_delay_s": round(delay, 2), "error": str(exc)})
            sleep(delay)
    raise RuntimeError("unreachable")  # pragma: no cover
