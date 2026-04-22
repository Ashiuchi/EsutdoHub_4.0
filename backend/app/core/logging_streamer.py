import asyncio
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


class LogStreamer:
    """Singleton broadcast bus for SSE log/data streaming.

    Subscribers register asyncio.Queue instances. Messages are put_nowait'd
    into every queue; full queues silently drop the message to avoid blocking.
    The event loop is captured lazily on the first subscribe() call, which
    always happens inside an async context (FastAPI endpoint), avoiding the
    startup-time get_event_loop() race condition.
    """

    def __init__(self) -> None:
        self._subscribers: List[asyncio.Queue] = []
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def subscribe(self) -> asyncio.Queue:
        """Register a new SSE consumer queue. Must be called from async context."""
        if self._loop is None:
            self._loop = asyncio.get_running_loop()
            logger.debug("LogStreamer: event loop captured on first subscribe.")
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        self._subscribers.append(q)
        logger.debug(f"LogStreamer: subscriber added ({len(self._subscribers)} total)")
        return q

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        """Remove a consumer queue when the SSE connection closes."""
        try:
            self._subscribers.remove(queue)
            logger.debug(f"LogStreamer: subscriber removed ({len(self._subscribers)} remaining)")
        except ValueError:
            pass

    def broadcast(self, message: dict) -> None:
        """Put message on all subscriber queues (thread-safe)."""
        loop = self._loop
        if not loop or not loop.is_running():
            return
        for q in list(self._subscribers):
            loop.call_soon_threadsafe(q.put_nowait, message)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)


log_streamer = LogStreamer()


class _NoSelfLoopFilter(logging.Filter):
    """Prevents recursive logging and suppresses noisy library namespaces."""

    def filter(self, record: logging.LogRecord) -> bool:
        ignored_namespaces = (
            "app.core.logging_streamer",
            "uvicorn",
            "httpcore",
            "httpx",
            "sqlalchemy.engine",
        )
        return not any(record.name.startswith(ns) for ns in ignored_namespaces)


class StreamingLogHandler(logging.Handler):
    """Logging handler that forwards records to LogStreamer as JSON SSE events."""

    def __init__(self, streamer: LogStreamer) -> None:
        super().__init__()
        self.streamer = streamer
        self.addFilter(_NoSelfLoopFilter())

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.streamer.broadcast({
                "type": "log",
                "message": self.format(record),
                "level": record.levelname,
            })
        except Exception:
            self.handleError(record)


def setup_streaming_handler() -> None:
    """Attach StreamingLogHandler to the root logger.

    The event loop is captured lazily on first subscribe(), NOT here,
    because at startup time no async loop is running yet.
    """
    handler = StreamingLogHandler(log_streamer)
    handler.setLevel(logging.INFO)

    root_logger = logging.getLogger("")
    if root_logger.level > logging.INFO:
        root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)
    logger.info("LogStreamer: streaming handler attached to root logger (INFO+)")
