"""
Phase 8 v8 WebSocket 双向交易端点 单元测试:
  - /api/ws 接受连接
  - ping/pong 双向消息
  - place_order / close_position 消息处理
  - 后台推送 positions_update / account_update
"""
import json
import pytest
from starlette.testclient import TestClient


@pytest.fixture
def client():
    from app import app
    return TestClient(app)


def test_ws_connect_and_ping_pong(client):
    """Test basic WebSocket connect + ping/pong round trip."""
    with client.websocket_connect("/api/ws") as ws:
        ws.send_json({"type": "ping"})
        resp = ws.receive_json()
        assert resp["type"] == "pong"


def test_ws_place_order_invalid_params(client):
    """Test place_order with missing symbol returns error."""
    with client.websocket_connect("/api/ws") as ws:
        ws.send_json({"type": "place_order", "symbol": "", "side": "buy"})
        resp = ws.receive_json()
        assert resp["type"] == "error"
        assert "symbol" in resp["message"] or "required" in resp["message"]


def test_ws_close_position_no_ticket(client):
    """Test close_position without ticket returns error."""
    with client.websocket_connect("/api/ws") as ws:
        ws.send_json({"type": "close_position", "ticket": 0})
        resp = ws.receive_json()
        assert resp["type"] == "error"
        assert "ticket" in resp["message"] or "required" in resp["message"]


def test_ws_unknown_message_type(client):
    """Test unknown message type returns error."""
    with client.websocket_connect("/api/ws") as ws:
        ws.send_json({"type": "invalid_type_xyz"})
        resp = ws.receive_json()
        assert resp["type"] == "error"
        assert "unknown" in resp["message"]


def test_ws_receives_positions_update_within_10s(client):
    """Test that background push sends positions_update within ~10s.
    The push loop fires every 5s, so within 10s we should see at least one."""
    with client.websocket_connect("/api/ws") as ws:
        ws.send_json({"type": "ping"})
        # Drain initial pong, then wait for push
        resp = ws.receive_json()  # pong
        assert resp["type"] == "pong"

        # Wait for up to 11s for positions_update (2 cycles)
        # Note: WebSocketTestSession.receive() does NOT support timeout kwarg.
        # Use outer deadline to prevent infinite block.
        import time as _t
        deadline = _t.time() + 11
        seen_positions = False
        while _t.time() < deadline:
            try:
                raw = ws.receive()
                msg = json.loads(raw["text"])
                if msg.get("type") == "positions_update":
                    seen_positions = True
                    break
            except Exception:
                break
        assert seen_positions, "Expected positions_update within 11s"
