"""
SSE 实时行情流端点  单元测试 — Phase 8 v7:

  ·  GET /api/stream  返 SSE headers · first event:snapshot · data  health + symbol_data
  · data_pool  起点  · 后   tick  event(cold path,  cache not ready)
  · cancel_all_streams lifecycle  shutdown 中  cancel active
"""
import asyncio
import json
import pytest
from starlette.testclient import TestClient


@pytest.fixture
def client():
    """FastAPI TestClient for SSE endpoint tests."""
    from app import app
    return TestClient(app)


def test_stream_returns_sse_headers(client):
    """Test SSE endpoint emits text/event-stream content-type."""
    with client.stream("GET", "/api/stream") as response:
        assert response.status_code == 200
        ct = response.headers.get("content-type", "")
        assert "text/event-stream" in ct
        # read first event(s)
        text_iter = response.iter_text()
        first = next(text_iter)
        # SSE format: "event: snapshot\ndata: {...}\n\n"
        assert "event: snapshot" in first
        assert "data:" in first


def test_stream_snapshot_contains_health_and_data(client):
    """snapshot event payload includes health + data shape."""
    with client.stream("GET", "/api/stream") as response:
        text_iter = response.iter_text()
        first = next(text_iter)
        # Extract the data: payload (between "data:" and "\n\n")
        data_start = first.find("data:") + len("data:")
        data_end = first.find("\n\n", data_start)
        payload = first[data_start:data_end].strip()
        parsed = json.loads(payload)
        assert "health" in parsed
        assert "data" in parsed
        assert isinstance(parsed["data"], dict)
        # Each sym has 5 tf → shape {sym: {tf: dict}}
        for sym, tfs in list(parsed["data"].items())[:2]:
            for tf in ("M5", "M15", "H1", "H4", "D1"):
                if tf in tfs:
                    assert "rows" in tfs[tf]


def test_stream_with_pool_data_marks_ready(client, fresh_bridge, one_symbol):
    """When data_pool is initialized + warm, snapshot health has is_ready=True."""
    from core.data_pool import DataPool, shutdown_pool
    shutdown_pool()
    pool = DataPool(fresh_bridge, symbols=one_symbol)
    pool.start()
    try:
        assert pool.wait_ready(timeout=10)
        with client.stream("GET", "/api/stream") as response:
            text_iter = response.iter_text()
            first = next(text_iter)
            data_start = first.find("data:") + len("data:")
            data_end = first.find("\n\n", data_start)
            parsed = json.loads(first[data_start:data_end].strip())
            health = parsed["health"]
            assert health.get("is_ready") is True
            # XAUUSD data populated by data_pool
            xau = parsed["data"].get("XAUUSD", {})
            for tf in ("M5", "M15", "H1", "H4", "D1"):
                assert xau.get(tf, {}).get("valid") is True
    finally:
        pool.stop(timeout=5)


def test_stream_cold_path_when_data_pool_not_initialized(client):
    """If data_pool never initialized, snapshot has is_ready=False + empty rows."""
    from core.data_pool import shutdown_pool
    shutdown_pool()  # ensure pool is None
    with client.stream("GET", "/api/stream") as response:
        text_iter = response.iter_text()
        first = next(text_iter)
        data_start = first.find("data:") + len("data:")
        data_end = first.find("\n\n", data_start)
        parsed = json.loads(first[data_start:data_end].strip())
        assert parsed["health"].get("is_ready") is False
        # data has shape but empty rows per tf
        for sym, tfs in parsed["data"].items():
            for tf in ("M5", "M15", "H1", "H4", "D1"):
                if tf in tfs:
                    assert tfs[tf]["valid"] is False
                    assert tfs[tf]["rows"] == []


def test_stream_heartbeat_ping_fires_by_time_alone(client, monkeypatch):
    """v7.0.1 fix regression — ping must fire by elapsed time, NOT contingent on
    any `x-front-stream-ping` header (which no client sends → silent connect drop
    in 60s/30s proxies).

    Shorten intervals via monkeypatch so the test runs fast: TICK=0.1s, ping every
    0.2s (~2 ticks). Stream for ~0.45s → expect both `tick` AND `ping` events.
    """
    import api.routes_stream as rs
    monkeypatch.setattr(rs, "TICK_INTERVAL_S", 0.1)
    monkeypatch.setattr(rs, "HEARTBEAT_INTERVAL_S", 0.2)
    # Explicit: no header sent — header-based ping (the v7.0.0 bug) MUST NOT be required
    seen_events = []
    with client.stream("GET", "/api/stream") as response:
        assert response.status_code == 200
        import time as _t
        deadline = _t.time() + 0.6
        for chunk in response.iter_text():
            seen_events.extend(line for line in chunk.split("\n") if line.startswith("event:"))
            if _t.time() > deadline:
                break
    # Must have seen snapshot + at least one tick + at least one ping
    assert "event: snapshot" in seen_events, f"missing snapshot in {seen_events}"
    assert any("event: tick" in e for e in seen_events), f"no tick in {seen_events}"
    assert any("event: ping" in e for e in seen_events), f"no ping emitted → regression of v7.0.0 header-bug. seen={seen_events}"


async def test_cancel_all_streams_lifecycle():
    """async test: cancel_all_streams cleans up active generators."""
    from api.routes_stream import _active_streams, cancel_all_streams
    # Initially empty
    assert len(_active_streams) == 0

    # Simulate: spawn a dummy SSE-like task
    async def dummy_gen():
        try:
            await asyncio.sleep(60)
            yield  # generator semantics for compat
        except asyncio.CancelledError:
            raise

    task = asyncio.create_task(dummy_gen().__aiter__().__anext__())  # noqa
    _active_streams.append(task)
    assert len(_active_streams) == 1

    await cancel_all_streams()
    assert len(_active_streams) == 0
