"""Cola de URLs pendientes y visitadas."""

from collections import deque

from scraper_agent.utils.url_utils import normalize_url


class UrlFrontier:
    """Frontier BFS con deduplicación."""

    def __init__(
        self,
        seed: str,
        visited: list[str] | None = None,
        pending: list[str] | None = None,
        *,
        seed_queue: bool = True,
    ) -> None:
        self._visited: set[str] = {normalize_url(u) for u in (visited or [])}
        self._queue: deque[str] = deque()
        if pending:
            for url in pending:
                self.enqueue(url)
        elif seed_queue:
            self.enqueue(seed)

    @property
    def visited_count(self) -> int:
        return len(self._visited)

    def is_empty(self) -> bool:
        return len(self._queue) == 0

    def mark_visited(self, url: str) -> None:
        self._visited.add(normalize_url(url))

    def was_visited(self, url: str) -> bool:
        return normalize_url(url) in self._visited

    def enqueue(self, url: str, *, priority: bool = False) -> bool:
        """Añade URL si no fue visitada ni está en cola. priority=True va al frente."""
        normalized = normalize_url(url)
        if normalized in self._visited:
            return False
        if normalized in self._queue:
            return False
        if priority:
            self._queue.appendleft(normalized)
        else:
            self._queue.append(normalized)
        return True

    def enqueue_priority(self, url: str) -> bool:
        return self.enqueue(url, priority=True)

    def dequeue(self) -> str | None:
        if not self._queue:
            return None
        return self._queue.popleft()

    def snapshot(self) -> tuple[list[str], list[str]]:
        return sorted(self._visited), list(self._queue)
