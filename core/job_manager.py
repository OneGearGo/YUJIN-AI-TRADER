"""
核心 job state manager — Phase 8 v5.1 救命药二 (post-review fix):

 设计原则:
   · 不用 fastapi.BackgroundTasks( 与 HTTP 响应绑定  ·  client 断连 task leak)
   · 全场 asyncio.create_task  ·  job  跨 HTTP request    · 独立守护
   · Job Deduplication(+ dedup_key  post-review fix?):
     5 个同 caller 同 dedup_key ·  并发起  同 job_id · attach_count++
     ? dedup_key  避免 silent drop 不同请求(can can may have different closure args)
   · Cache miss path 走 job_queue · hit path · 200 直接返
   · LRU 30 min GC    老 job   · memory 不漏
   · asyncio event loop 单线程 → dict access 原生 safe 不用 threading.Lock
   · Outer timeout (post-review fix):coro_factory hung 120s → job_state=failed + error_msg
     防止 dedup 锁死  · 避免 长 状态 running 占用 active_scan_job_id  拥塞避免

  singleton 重命名:`jm` (fight module/instance name clash on `from core import job_manager`)
"""
import asyncio
import time
import uuid
import logging
from typing import Dict, Any, Optional, Awaitable, Callable, List

logger = logging.getLogger(__name__)


class JobManager:
    """async-aware job state store + dispatch (singleton via `jm`)."""

    JOB_STATES = ("queued", "running", "done", "failed", "cancelled")
    JOB_TTL_S_DEFAULT = 1800  # 30 min
    WORKER_TIMEOUT_S = 120.0  # post-review fix #2: outer cap on hung coro

    def __init__(self, ttl_s: int = JOB_TTL_S_DEFAULT, worker_timeout_s: float = WORKER_TIMEOUT_S):
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._active_scan_job_id: Optional[str] = None
        self._ttl_s = ttl_s
        self._worker_timeout_s = worker_timeout_s
        self._lock_count = 0  # test introspection

    # ============================================================
    # create + dispatch (dedup + dedup_key aware)
    # ============================================================
    def create_scan_job(
        self,
        coro_factory: Callable[[], Awaitable[Any]],
        dedup_key: Optional[str] = None,
    ) -> str:
        """
        任 job 入队  dedup:  running 的同 kind + 同 dedup_key ·  返同 job_id   位  caller

        coro_factory: () -> Awaitable[Any]
          Job 内部  await 此 coro · coro 走 MT5 execution cache update
        dedup_key: None =  不 dedup · str = dedup  key
          ( 路由: dedup_key=f"scan:{len(symbols)}:{DATA_MODE}:{count}")

        post-review fix #1:dedup_key  比较 · 拒同 kind 但 不同 key 的   静默  drop
        """
        now = time.time()
        # 1. dedup: 同 kind scan job running + key  同 ·  返同 job_id
        if dedup_key is not None and self._active_scan_job_id:
            active = self._jobs.get(self._active_scan_job_id, {})
            if (
                active.get("state") == "running"
                and active.get("kind") == "scan_all"
                and active.get("dedup_key") == dedup_key
            ):
                active["attach_count"] = active.get("attach_count", 1) + 1
                logger.info(
                    "job_dedup: attach to active scan job_id=%s attach_count=%d key=%s",
                    self._active_scan_job_id, active["attach_count"], dedup_key,
                )
                return self._active_scan_job_id
        # 1b. 不同 dedup_key  · active 被 个 mark "stale" · 不再 dedup    仍 active 直至   完成
        # ( 鱼 吐   active 还是 多  Tibetan 后 · 鲑 中   )

        # 2. 新建
        job_id = str(uuid.uuid4())
        self._jobs[job_id] = {
            "id": job_id,
            "kind": "scan_all",
            "state": "running",
            "dedup_key": dedup_key,
            "ts_started": now,
            "ts_finished": None,
            "result": None,
            "error": None,
            "attach_count": 1,
            "_task": None,  # set after create_task
        }
        self._active_scan_job_id = job_id
        self._gc_cleanup(now)
        self._lock_count += 1  # test helper

        # 3. spawn user task · 与 HTTP request 独立
        task = asyncio.create_task(self._worker(job_id, coro_factory), name=f"scan_job_{job_id[:8]}")
        self._jobs[job_id]["_task"] = task  # NICE TO HAVE · 不 勿 Task GC

        return job_id

    async def _worker(self, job_id: str, coro_factory: Callable[[], Awaitable[Any]]) -> None:
        """
        Worker: outer timeout (post-review fix #2) · coro hung  120s mark failed.

        IMPORTANT:实际 coro 内部  copy_rates_async(timeout=10)  ·  hang  3⨁u  random=3 .
        Outer timeout  120s 设  ·  兜  览 hangs (  ·  scary  · env .)
        """
        job = self._jobs[job_id]
        try:
            try:
                res = await asyncio.wait_for(coro_factory(), timeout=self._worker_timeout_s)
                job["result"] = res
                job["state"] = "done"
            except asyncio.TimeoutError:
                job["error"] = f"job timeout after {self._worker_timeout_s}s"
                job["state"] = "failed"
                logger.error("job %s timeout after %.1fs", job_id[:8], self._worker_timeout_s)
            except Exception as e:
                job["error"] = str(e)
                job["state"] = "failed"
                logger.exception("job %s failed: %s", job_id[:8], e)
        finally:
            job["ts_finished"] = time.time()
            if self._active_scan_job_id == job_id:
                self._active_scan_job_id = None
            logger.info(
                "job %s exit state=%s duration=%.2fs",
                job_id[:8], job["state"], job["ts_finished"] - job["ts_started"],
            )

    # ============================================================
    # read-only API
    # ============================================================
    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        return self._jobs.get(job_id)

    def list_recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Returns recent jobs sorted ts_started desc."""
        items = [
            {k: v for k, v in j.items() if k != "_task"}  # strip task ref from JSON
            for j in self._jobs.values()
        ]
        return sorted(items, key=lambda j: j.get("ts_started", 0.0), reverse=True)[:limit]

    # ============================================================
    # GC:  TTL 老 job   ·  running 必 保
    # ============================================================
    def _gc_cleanup(self, now: Optional[float] = None) -> None:
        if now is None:
            now = time.time()
        before = len(self._jobs)
        keep = {
            jid: j for jid, j in self._jobs.items()
            if j.get("state") == "running" or (now - j.get("ts_started", now)) < self._ttl_s
        }
        self._jobs = keep
        after = len(self._jobs)
        if before != after:
            logger.info("job_gc: dropped %d · kept %d", before - after, after)


# ============================================================
# 进程级 singleton — routes import as `jm` to avoid module/instance name clash
# ============================================================
jm = JobManager()
