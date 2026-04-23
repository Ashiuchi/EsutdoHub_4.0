import asyncio
import logging
import pytest
from app.core.logging_streamer import LogStreamer, StreamingLogHandler, _NoSelfLoopFilter


@pytest.mark.asyncio
async def test_subscribe_returns_queue():
    streamer = LogStreamer()
    q = streamer.subscribe()
    assert q is not None
    assert isinstance(q, asyncio.Queue)


@pytest.mark.asyncio
async def test_subscribe_increments_count():
    streamer = LogStreamer()
    assert streamer.subscriber_count == 0
    streamer.subscribe()
    assert streamer.subscriber_count == 1
    streamer.subscribe()
    assert streamer.subscriber_count == 2


@pytest.mark.asyncio
async def test_subscribe_captures_event_loop():
    streamer = LogStreamer()
    assert streamer._loop is None
    streamer.subscribe()
    assert streamer._loop is not None


@pytest.mark.asyncio
async def test_unsubscribe_removes_queue():
    streamer = LogStreamer()
    q = streamer.subscribe()
    assert streamer.subscriber_count == 1
    streamer.unsubscribe(q)
    assert streamer.subscriber_count == 0


@pytest.mark.asyncio
async def test_unsubscribe_unknown_queue_is_noop():
    streamer = LogStreamer()
    q = asyncio.Queue()
    streamer.unsubscribe(q)  # should not raise


def test_broadcast_without_loop_is_noop():
    streamer = LogStreamer()
    # No loop captured yet — should not raise
    streamer.broadcast({"type": "test"})


@pytest.mark.asyncio
async def test_broadcast_delivers_to_subscriber():
    streamer = LogStreamer()
    q = streamer.subscribe()
    msg = {"type": "log", "message": "hello"}
    streamer.broadcast(msg)
    await asyncio.sleep(0)
    assert not q.empty()
    received = q.get_nowait()
    assert received == msg


@pytest.mark.asyncio
async def test_broadcast_delivers_to_multiple_subscribers():
    streamer = LogStreamer()
    q1 = streamer.subscribe()
    q2 = streamer.subscribe()
    streamer.broadcast({"type": "data"})
    await asyncio.sleep(0)
    assert not q1.empty()
    assert not q2.empty()


@pytest.mark.asyncio
async def test_broadcast_after_unsubscribe_not_delivered():
    streamer = LogStreamer()
    q = streamer.subscribe()
    streamer.unsubscribe(q)
    streamer.broadcast({"type": "test"})
    await asyncio.sleep(0)
    assert q.empty()


def test_no_self_loop_filter_blocks_own_namespace():
    f = _NoSelfLoopFilter()
    record = logging.LogRecord(
        "app.core.logging_streamer", logging.INFO, "", 0, "", (), None
    )
    assert not f.filter(record)


def test_no_self_loop_filter_blocks_uvicorn():
    f = _NoSelfLoopFilter()
    record = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, "", (), None)
    assert not f.filter(record)


def test_no_self_loop_filter_blocks_httpx():
    f = _NoSelfLoopFilter()
    record = logging.LogRecord("httpx", logging.INFO, "", 0, "", (), None)
    assert not f.filter(record)


def test_no_self_loop_filter_passes_app_namespace():
    f = _NoSelfLoopFilter()
    record = logging.LogRecord("app.services.ai_service", logging.INFO, "", 0, "", (), None)
    assert f.filter(record)


@pytest.mark.asyncio
async def test_streaming_handler_emit_broadcasts():
    streamer = LogStreamer()
    handler = StreamingLogHandler(streamer)
    q = streamer.subscribe()

    record = logging.LogRecord("app.test", logging.INFO, "", 0, "test message", (), None)
    handler.emit(record)

    await asyncio.sleep(0)
    assert not q.empty()
    msg = q.get_nowait()
    assert msg["type"] == "log"
    assert msg["level"] == "INFO"


def test_streaming_handler_filters_own_namespace():
    streamer = LogStreamer()
    handler = StreamingLogHandler(streamer)
    # The handler has _NoSelfLoopFilter attached — records from its own namespace
    # should be filtered before reaching emit's broadcast
    record = logging.LogRecord(
        "app.core.logging_streamer", logging.INFO, "", 0, "self-log", (), None
    )
    # The filter should block this record
    assert not handler.filters[0].filter(record)
