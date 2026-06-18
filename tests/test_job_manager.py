"""
JobManager 单元测试 — Phase 8 v5 救命药二:

验证:
1. create_scan_job 返 UUID4
2. dedup:5 个同 caller create 同一 kind scan   → 返同 job_id · attach_count 5
3. lifecycle:running → done · result 写入
4. failed:coro raise → state="failed" · error 写入
5. _gc_cleanup:TTL 老 done job   · 剔除 · running 不扔
6. unknown job_id 返 None
"""
import asyncio
import time
import uuid
import pytest
from core.job_manager import JobManager, jm as job_manager


@pytest.fixture(autouse=True)
def _reset_job_manager():
    """每个 测  reset  singleton state ·  跨 池 不 杂"""
    job_manager._jobs.clear()
    job_manager._active_scan_job_id = None
    yield
    job_manager._jobs.clear()
    job_manager._active_scan_job_id = None


def test_create_returns_uuid4():
    """create 后 返 job_id · UUID4 string"""
    async def runner():
        async def coro():
            return {"ok": True}

        jid = job_manager.create_scan_job(coro)
        assert isinstance(jid, str)
        # UUID4 hyphen format: 8-4-4-4-12
        parsed = uuid.UUID(jid)
        assert parsed.version == 4
        # let worker finish to avoid event loop warning
        await asyncio.sleep(0.05)

    asyncio.run(runner())


def test_dedup_three_concurrent_callers_return_same_job_id():
    """3 个 caller 接连 create 同 dedup_key   → 全部 dedup 到 running 那   job_id"""
    async def runner():
        async def slow_coro():
            await asyncio.sleep(0.3)
            return {"x": 1}

        # post-review fix #1:dedup_key  explicit · 同 key  deduped
        jid_1 = job_manager.create_scan_job(slow_coro, dedup_key="thread_A")
        jid_2 = job_manager.create_scan_job(slow_coro, dedup_key="thread_A")
        jid_3 = job_manager.create_scan_job(slow_coro, dedup_key="thread_A")
        assert jid_1 == jid_2 == jid_3

        job = job_manager.get(jid_1)
        assert job is not None
        assert job["state"] == "running"
        assert job["attach_count"] == 3
        # verify kind/kv
        assert job["kind"] == "scan_all"
        assert job["id"] == jid_1
        assert job["dedup_key"] == "thread_A"

        await asyncio.sleep(0.4)  # wait for worker completion
        assert job_manager.get(jid_1)["state"] == "done"

    asyncio.run(runner())


def test_dedup_different_keys_no_dedup():
    """不同 dedup_key  后 caller   不 dedup  ·  拆  独立 jobs"""
    async def runner():
        async def c():
            await asyncio.sleep(0.3)
            return None

        jid_a = job_manager.create_scan_job(c, dedup_key="theme_A")
        jid_b = job_manager.create_scan_job(c, dedup_key="theme_B")
        assert jid_a != jid_b

        await asyncio.sleep(0.4)
        assert job_manager.get(jid_a)["dedup_key"] == "theme_A"
        assert job_manager.get(jid_b)["dedup_key"] == "theme_B"

    asyncio.run(runner())


def test_lifecycle_running_to_done():
    """run → done; result + ts_finish OK"""
    async def runner():
        async def fast_coro():
            await asyncio.sleep(0.05)
            return {"marker": "DONE_OK"}

        jid = job_manager.create_scan_job(fast_coro)
        await asyncio.sleep(0.1)

        job = job_manager.get(jid)
        assert job["state"] == "done"
        assert job["result"] == {"marker": "DONE_OK"}
        assert job["ts_finished"] is not None
        assert job["ts_finished"] >= job["ts_started"]

    asyncio.run(runner())


def test_lifecycle_failed_captures_exception_message():
    """coro raise → state=failed + error msg"""
    async def runner():
        async def fail_coro():
            raise ValueError("upstream MT5 fail_simulated")

        jid = job_manager.create_scan_job(fail_coro)
        await asyncio.sleep(0.05)

        job = job_manager.get(jid)
        assert job["state"] == "failed"
        assert "upstream MT5 fail_simulated" in job["error"]

    asyncio.run(runner())


def test_gc_drops_old_done_jobs_but_keeps_running():
    """TTL 老 done job  → GC drop · running job 必 保"""
    # use short TTL for test
    job_manager._ttl_s = 1
    async def runner():
        async def quick_coro():
            await asyncio.sleep(0.02)
            return {"k": "v"}

        # finished quickly
        jid_done = job_manager.create_scan_job(quick_coro)
        await asyncio.sleep(0.05)
        assert job_manager.get(jid_done)["state"] == "done"

        # let TTL elapse
        await asyncio.sleep(1.5)
        job_manager._gc_cleanup()
        # 老 done job  已 drop (TTL=1s, ts_started 1.5s ago)
        assert job_manager.get(jid_done) is None

        # 兴 new job   running  必保
        async def slow_coro():
            await asyncio.sleep(10)
            return "x"
        jid_running = job_manager.create_scan_job(slow_coro)
        job_manager._gc_cleanup()
        assert job_manager.get(jid_running) is not None
        assert job_manager.get(jid_running)["state"] == "running"

    asyncio.run(runner())


def test_no_dedup_after_previous_finished():
    """dedup 仅在 active 那    · fulled 后      新  job   """
    async def runner():
        async def fast():
            await asyncio.sleep(0.02)
            return 1

        jid_1 = job_manager.create_scan_job(fast)
        await asyncio.sleep(0.1)
        assert job_manager.get(jid_1)["state"] == "done"
        assert job_manager._active_scan_job_id is None

        # 再调     → 不 dedup · 拼      不shoulddedup
        async def fast2():
            await asyncio.sleep(0.02)
            return 2

        jid_2 = job_manager.create_scan_job(fast2)
        assert jid_2 != jid_1  # new job
        await asyncio.sleep(0.1)
        assert job_manager.get(jid_2)["state"] == "done"

    asyncio.run(runner())


def test_get_unknown_returns_none():
    jm = JobManager()
    assert jm.get("nonexistent-uuid-1234567890") is None


def test_list_recent_returns_sorted_desc():
    """list_recent 按 ts_started desc"""
    async def runner():
        async def c():
            await asyncio.sleep(0.01)
            return None

        #  piv 1ms
        for _ in range(3):
            job_manager.create_scan_job(c)
            await asyncio.sleep(0.01)

        await asyncio.sleep(0.1)  # let workers finish

        recent = job_manager.list_recent(limit=10)
        assert len(recent) >= 3
        # sorted desc
        for i in range(len(recent) - 1):
            assert recent[i]["ts_started"] >= recent[i + 1]["ts_started"]

    asyncio.run(runner())
